#!/usr/bin/env python3
"""After a key is drawn: look at the PNG, list defects, redraw the same pose."""
from __future__ import annotations

import json
from pathlib import Path

from anim_interp import parse_named_strokes, strokes_to_xml
from anim_prompts import ANIM_DRAW_SYSTEM, ANIM_DRAW_SYSTEM_ANIMAL, BLASTER_EXAMPLE
from drawer_prompts import CIRCLE, xml_tail
from sa_render import convert_completion, extract_strokes_xml
from terra_client import call_deepseek, call_glm, call_glm_vision, data_url, parse_json_obj

COMPASS = (
    (0.0, -1.0),
    (0.7, -0.7),
    (1.0, 0.0),
    (0.7, 0.7),
    (0.0, 1.0),
    (-0.7, 0.7),
    (-1.0, 0.0),
    (-0.7, -0.7),
    (0.0, -1.0),
)

GUN_NAMES = ("gun", "blast", "rifle", "pistol", "weapon")
HEAD_NAMES = ("head", "helmet")

REFLECT_SYSTEM = """You are a strict visual editor for sparse black-line stick-figure KEY frames.
Look at the PNG first, then the XML. Return JSON only. No markdown.

Pass only if ALL of these are true:
- Every person/animal HEAD looks like a ROUND CIRCLE (equal width and height). Beans, hearts, sausages, and wide ovals FAIL.
- A gun/blaster, if present, is a readable small gun (short body + barrel), not one dash continuing the arm.
- Named parts still match the pose (do not invent a new scene).

Ignore slight joint looseness. Ignore ground-line thickness. Do not ask for clothes or pupils.

Return:
{
  "ok": true,
  "issues": [
    {"part": "trooper_head", "problem": "wide bean", "fix": "rebuild as 8-compass circle, same center, width=height"}
  ]
}
ok=true only if issues is empty."""


def _cell(xml_point: tuple[float, float]) -> tuple[int, int]:
    return max(1, min(50, int(round(xml_point[0])))), max(1, min(50, int(round(xml_point[1]))))


def geometric_issues(xml: str) -> list[dict]:
    issues = []
    for s in parse_named_strokes(xml):
        name = s.name.lower()
        xs = [p[0] for p in s.points]
        ys = [p[1] for p in s.points]
        w = max(xs) - min(xs)
        h = max(ys) - min(ys)
        closed = len(s.points) >= 3 and s.points[0] == s.points[-1]
        if any(tok in name for tok in HEAD_NAMES):
            aspect = w / h if h >= 1 else 99.0
            if not closed or len(s.points) < 8:
                issues.append(
                    {
                        "part": s.name,
                        "problem": "head is not a closed 8-point circle",
                        "fix": "rebuild with 8 compass points + start cell, equal width and height",
                    }
                )
            elif not (0.82 <= aspect <= 1.22):
                issues.append(
                    {
                        "part": s.name,
                        "problem": f"head is a {w:.0f}x{h:.0f} bean/oval, not a circle",
                        "fix": "same center; make width equal height (~6 cells); 8 compass points",
                    }
                )
        if any(tok in name for tok in GUN_NAMES) and "arm" not in name:
            if len(s.points) <= 2:
                issues.append(
                    {
                        "part": s.name,
                        "problem": "gun is one dash, collinear with the arm",
                        "fix": "short body (small L or 4-point rectangle) plus a barrel sticking forward",
                    }
                )
    return issues


def vision_critique(
    png: Path,
    xml: str,
    task: dict,
    geo: list[dict],
    *,
    vision: str = "deepseek",
) -> dict:
    geo_txt = json.dumps(geo, ensure_ascii=False) if geo else "[]"
    prompt = f"""This is one KEY of: {task.get('concept', '')}
{task.get('prompt', '')}

Geometry tool already flagged:
{geo_txt}

XML:
{xml}

Look at the PNG. Confirm or add issues. Heads must be round circles. Guns must not be a single dash."""
    messages = [
        {"role": "system", "content": REFLECT_SYSTEM},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": data_url(png)}},
            ],
        },
    ]
    if vision in {"glm", "glm-4.5v", "zhipu"}:
        raw = call_glm_vision(messages, max_tokens=1200, temperature=0.1, timeout=180)
        backend = "glm-4.5v"
    else:
        raw = call_deepseek(messages, max_tokens=1200, temperature=0.1, timeout=180)
        backend = "deepseek-v4-flash-vision-exp"
    try:
        obj = parse_json_obj(raw)
    except Exception:
        obj = {"ok": not geo, "issues": list(geo), "parse_error": True, "raw": raw[:1500]}
    if not isinstance(obj.get("issues"), list):
        obj["issues"] = list(geo)
    seen = {(str(i.get("part")), str(i.get("problem"))) for i in obj["issues"] if isinstance(i, dict)}
    for g in geo:
        key = (g["part"], g["problem"])
        if key not in seen:
            obj["issues"].append(g)
    obj["ok"] = bool(obj.get("ok")) and not obj["issues"]
    obj["raw"] = raw
    obj["vision_backend"] = backend
    return obj


def _strokes_xml(strokes: list) -> str:
    wrapped = strokes_to_xml(strokes, "scene")
    return extract_strokes_xml(wrapped) or wrapped


def snap_heads_to_circles(xml: str) -> str:
    """Last-mile: replace non-round head strokes with a compass circle at the same center."""
    strokes = parse_named_strokes(xml)
    if not strokes:
        return xml
    for s in strokes:
        if not any(tok in s.name.lower() for tok in HEAD_NAMES):
            continue
        xs = [p[0] for p in s.points]
        ys = [p[1] for p in s.points]
        w, h = max(xs) - min(xs), max(ys) - min(ys)
        aspect = w / h if h >= 1 else 99.0
        if 0.82 <= aspect <= 1.22 and len(s.points) >= 8:
            continue
        cx = sum(xs) / len(xs)
        cy = sum(ys) / len(ys)
        r = max(3, round(max(w, h) / 2) or 3)
        s.points = [tuple(map(float, _cell((cx + dx * r, cy + dy * r)))) for dx, dy in COMPASS]
        s.t_values = [i / 8 for i in range(9)]
    return _strokes_xml(strokes)


def enrich_gun_stroke(xml: str) -> str:
    """If a gun is still two points, turn it into a tiny L-body + barrel."""
    strokes = parse_named_strokes(xml)
    if not strokes:
        return xml
    for s in strokes:
        name = s.name.lower()
        if not any(tok in name for tok in GUN_NAMES) or "arm" in name:
            continue
        if len(s.points) > 2:
            continue
        (x1, y1), (x2, y2) = s.points[0], s.points[-1]
        back_x, back_y = _cell((x1, y1))
        tip_x, tip_y = _cell((x2, y2))
        body = 2 if tip_x >= back_x else -2
        s.points = [
            (float(back_x), float(back_y - 1)),
            (float(back_x), float(back_y + 1)),
            (float(back_x + body), float(back_y + 1)),
            (float(back_x + body), float(back_y)),
            (float(tip_x), float(tip_y)),
        ]
        s.t_values = [0.0, 0.25, 0.5, 0.75, 1.0]
    return _strokes_xml(strokes)


def fix_user(task: dict, xml: str, issues: list[dict], key_name: str) -> str:
    lines = []
    for i in issues:
        if not isinstance(i, dict):
            continue
        lines.append(f"- {i.get('part', '?')}: {i.get('problem', '')}. Fix: {i.get('fix', '')}")
    blob = "\n".join(lines) or "- heads round; gun has a body"
    return f"""Redraw KEY '{key_name}' of: {task.get('concept', '')}

A visual reflection failed. Keep the SAME <id> names, same pose, same placement.
Fix ONLY the listed defects. Do not restage the shot.

Defects:
{blob}

Head recipe (copy geometry, keep the old center):
{CIRCLE}

Gun recipe (body + barrel, not one dash):
{BLASTER_EXAMPLE}

Current XML (reuse ids; replace the bad strokes):
{xml}

{xml_tail(task.get('concept', 'scene'))}"""


def redraw_from_critique(
    task: dict,
    xml: str,
    issues: list[dict],
    key_name: str,
    png_path: Path,
) -> tuple[dict, str | None]:
    system = ANIM_DRAW_SYSTEM_ANIMAL if task.get("kind") == "animal" else ANIM_DRAW_SYSTEM
    raw = call_glm(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": fix_user(task, xml, issues, key_name)},
        ],
        max_tokens=3072,
        temperature=0.25,
        reasoning_effort="low",
        timeout=180,
    )
    rec = convert_completion(raw, png_path)
    new_xml = extract_strokes_xml(raw)
    return rec, new_xml


def reflect_key(
    task: dict,
    xml: str,
    png_path: Path,
    key_name: str,
    concept: str,
    out_json: Path | None = None,
    vision: str = "deepseek",
) -> tuple[str, dict]:
    """Look, maybe redraw, then snap remaining head/gun defects."""
    geo = geometric_issues(xml)
    try:
        critique = vision_critique(png_path, xml, task, geo, vision=vision)
    except Exception as e:
        critique = {"ok": not geo, "issues": list(geo), "vision_error": f"{type(e).__name__}: {e}"}
    issues = [i for i in (critique.get("issues") or []) if isinstance(i, dict)]
    critique["geometric"] = geo
    applied = xml
    if issues:
        print(f"  reflect {key_name}: {len(issues)} issue(s) — redraw", flush=True)
        rec, new_xml = redraw_from_critique(task, xml, issues, key_name, png_path)
        critique["redraw_valid"] = bool(rec.get("valid"))
        critique["redraw_error"] = rec.get("error")
        if rec.get("valid") and new_xml:
            applied = new_xml
        else:
            print(f"  reflect redraw rejected: {rec.get('error')}; keep original + snaps", flush=True)
    else:
        print(f"  reflect {key_name}: ok", flush=True)
    applied = snap_heads_to_circles(applied)
    applied = enrich_gun_stroke(applied)
    leftover = geometric_issues(applied)
    critique["leftover"] = leftover
    critique["ok"] = not leftover
    if out_json:
        dump = {k: v for k, v in critique.items() if k != "raw"}
        dump["raw"] = (critique.get("raw") or "")[:4000]
        out_json.write_text(json.dumps(dump, ensure_ascii=False, indent=2), encoding="utf-8")
    wrapped = f"<answer><concept>{concept}</concept>{applied}</answer>"
    rec = convert_completion(wrapped, png_path)
    if not rec.get("valid"):
        print(f"  reflect snap render failed: {rec.get('error')}; keep pre-snap xml", flush=True)
        return xml, critique
    return applied, critique
