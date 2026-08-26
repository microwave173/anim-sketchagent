#!/usr/bin/env python3
"""Still SketchAgent plan+draw for animal character sheets, then used by animation keys."""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

from anim_prompts import ANIMAL_PLAN_SYSTEM, ANIMAL_STILL_DRAW_SYSTEM, DOG_EXAMPLE, RABBIT_EXAMPLE, animal_still_user_prompt
from drawer_prompts import plan_text
from mint_plans import plan_has_cells, plan_user
from sa_render import CELL_RE, convert_completion, extract_strokes_xml
from terra_client import call_glm, parse_json_obj

ID_RE = re.compile(r"<id>(.*?)</id>", re.I | re.S)


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")


def prefix_stroke_ids(xml: str, prefix: str) -> str:
    pref = _slug(prefix)

    def repl(m: re.Match) -> str:
        slug = _slug(m.group(1))
        if not slug:
            slug = "part"
        if slug == pref or slug.startswith(pref + "_"):
            return f"<id>{slug}</id>"
        return f"<id>{pref}_{slug}</id>"

    return ID_RE.sub(repl, xml)


def xml_part_names(xml: str) -> list[str]:
    return [_slug(m.group(1)) for m in ID_RE.finditer(xml) if m.group(1).strip()]


def fit_animal_xml(
    xml: str,
    max_w: int = 18,
    max_h: int = 20,
    left_x: int = 7,
    feet_y: int = 46,
) -> str:
    """Shrink a still so the animal leaves travel room on a 50x50 grid."""
    pts = [(int(a), int(b)) for a, b in CELL_RE.findall(xml)]
    if not pts:
        return xml
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    min_x, max_x, min_y, max_y = min(xs), max(xs), min(ys), max(ys)
    w, h = max(1, max_x - min_x), max(1, max_y - min_y)
    s = min(1.0, max_w / w, max_h / h)
    if s >= 0.999 and min_x <= left_x + 1 and max_y >= feet_y - 1:
        return xml

    def repl(m: re.Match) -> str:
        x, y = int(m.group(1)), int(m.group(2))
        nx = max(1, min(50, round(left_x + (x - min_x) * s)))
        ny = max(1, min(50, round(feet_y + (y - max_y) * s)))
        return f"x{nx}y{ny}"

    return CELL_RE.sub(repl, xml)


def _fit_spec(spec: dict, xml: str) -> str:
    return fit_animal_xml(
        xml,
        max_w=int(spec.get("max_w", 18)),
        max_h=int(spec.get("max_h", 20)),
        left_x=int(spec.get("left_x", 7)),
        feet_y=int(spec.get("feet_y", 46)),
    )


SEED_XML = {
    "dog_example": extract_strokes_xml(DOG_EXAMPLE),
    "rabbit_example": extract_strokes_xml(RABBIT_EXAMPLE),
}


def still_from_xml(spec: dict, xml: str, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    prefix = spec.get("prefix") or spec.get("id") or "animal"
    xml = _fit_spec(spec, prefix_stroke_ids(xml, prefix))
    wrapped = f"<answer><concept>{spec.get('concept', 'animal')}</concept>\n{xml}\n</answer>"
    png = out_dir / "still.png"
    rec = convert_completion(wrapped, png)
    (out_dir / "still.xml.txt").write_text(xml, encoding="utf-8")
    (out_dir / "still.raw.txt").write_text(wrapped, encoding="utf-8")
    names = xml_part_names(xml)
    print(f"  still {spec.get('id')} seeded strokes={rec.get('n_strokes')} names={names}", flush=True)
    if not rec.get("valid"):
        raise RuntimeError(f"seed still {spec.get('id')} failed: {rec.get('error')}")
    return {
        "id": spec.get("id"),
        "prefix": prefix,
        "xml": xml,
        "names": names,
        "n_strokes": rec.get("n_strokes"),
        "valid": True,
        "png": str(png),
        "seeded": True,
    }


def mint_still_asset(spec: dict, out_dir: Path, attempts: int = 3) -> dict:
    """Plan + draw one still animal, or reuse a frozen character-sheet XML."""
    seed_key = spec.get("seed")
    if seed_key:
        xml = SEED_XML.get(seed_key)
        if not xml:
            raise ValueError(f"unknown still seed {seed_key}")
        return still_from_xml(spec, xml, out_dir)
    if spec.get("seed_xml"):
        return still_from_xml(spec, spec["seed_xml"], out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    task = {
        "task_id": spec.get("id") or spec["concept"],
        "concept": spec["concept"],
        "prompt": spec["prompt"],
        "requirements": spec.get("requirements")
        or [
            {"description": f"recognizable {spec['concept']}"},
            {"description": spec.get("viewpoint", "side view facing right")},
            {
                "description": "ellipse body + circle head on the upper-front; then only species signatures; plump animals omit legs"
            },
            {
                "description": "SMALL: body about 10–14 cells wide, left third of the canvas, leave the right half empty for later motion"
            },
        ],
    }
    last_err = "no still"
    last_raw = ""
    for attempt in range(1, attempts + 1):
        plan_raw = call_glm(
            [
                {"role": "system", "content": ANIMAL_PLAN_SYSTEM},
                {"role": "user", "content": plan_user(task)},
            ],
            max_tokens=2048,
            temperature=0.4,
            reasoning_effort="low",
            timeout=180,
        )
        (out_dir / "plan.raw.txt").write_text(plan_raw, encoding="utf-8")
        try:
            plan = parse_json_obj(plan_raw)
            if not isinstance(plan.get("strokes"), list) or len(plan["strokes"]) < 4:
                raise ValueError("need >=4 still strokes")
            if plan_has_cells(plan):
                raise ValueError("still plan contains grid cells")
        except Exception as e:
            last_err = f"plan {type(e).__name__}: {e}"
            print(f"  still {spec.get('id')} attempt {attempt} {last_err}", flush=True)
            time.sleep(1)
            continue
        (out_dir / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
        raw = call_glm(
            [
                {"role": "system", "content": ANIMAL_STILL_DRAW_SYSTEM},
                {"role": "user", "content": animal_still_user_prompt(task, plan_text(plan))},
            ],
            max_tokens=4096,
            temperature=0.55,
            reasoning_effort="low",
            timeout=180,
        )
        last_raw = raw
        png = out_dir / "still.png"
        rec = convert_completion(raw, png)
        xml = extract_strokes_xml(raw)
        (out_dir / "still.raw.txt").write_text(raw, encoding="utf-8")
        if rec.get("valid") and xml:
            prefix = spec.get("prefix") or spec.get("id") or "animal"
            xml = _fit_spec(spec, prefix_stroke_ids(xml, prefix))
            wrapped = f"<answer><concept>{spec.get('concept', 'animal')}</concept>\n{xml}\n</answer>"
            rec = convert_completion(wrapped, png)
            if not rec.get("valid"):
                last_err = rec.get("error") or "refit still invalid"
                print(f"  still {spec.get('id')} attempt {attempt} refit rejected: {last_err}", flush=True)
                time.sleep(1)
                continue
            (out_dir / "still.xml.txt").write_text(xml, encoding="utf-8")
            names = xml_part_names(xml)
            print(
                f"  still {spec.get('id')} ok strokes={rec.get('n_strokes')} names={names[:8]}...",
                flush=True,
            )
            return {
                "id": spec.get("id"),
                "prefix": prefix,
                "xml": xml,
                "names": names,
                "n_strokes": rec.get("n_strokes"),
                "valid": True,
                "png": str(png),
            }
        last_err = rec.get("error") or f"valid={rec.get('valid')} strokes={rec.get('n_strokes')}"
        print(f"  still {spec.get('id')} attempt {attempt} rejected: {last_err}", flush=True)
        time.sleep(1)
    (out_dir / "still.raw.txt").write_text(last_raw, encoding="utf-8")
    raise RuntimeError(f"still asset {spec.get('id')} failed: {last_err}")


def mint_task_assets(task: dict, out_dir: Path) -> list[dict]:
    sheets = []
    for spec in task.get("assets") or []:
        print(f"== still asset {spec.get('id')} ==", flush=True)
        sheets.append(mint_still_asset(spec, out_dir / str(spec.get("id") or spec["concept"])))
    return sheets


def sheets_xml_block(sheets: list[dict]) -> str:
    blocks = []
    for s in sheets:
        blocks.append(f"--- character sheet '{s['id']}' (copy these named strokes; pose them) ---\n{s['xml']}")
    return "\n\n".join(blocks)


def sheets_part_hints(sheets: list[dict]) -> list[dict]:
    parts = []
    i = 1
    for s in sheets:
        for name in s.get("names") or []:
            parts.append(
                {
                    "id": f"a{i}",
                    "name": name,
                    "how": "from character sheet",
                    "motion": "moving",
                    "notes": f"must keep this {s['id']} part from the still",
                }
            )
            i += 1
    return parts
