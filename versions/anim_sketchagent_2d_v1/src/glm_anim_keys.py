#!/usr/bin/env python3
"""Pose-to-pose: GLM draws a few keys; geometric inbetweens fill the gaps."""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from anim_interp import (
    anchored_names_from_parts,
    expand_timeline,
    interpolate_xml,
    pin_anchored_xml,
    render_xml,
)
from anim_prompts import (
    ANIM_DRAW_SYSTEM,
    ANIM_DRAW_SYSTEM_ANIMAL,
    KEY_PLAN_SYSTEM,
    KEY_PLAN_SYSTEM_ANIMAL,
    MAX_FRAMES,
    MAX_KEYS,
    MAX_PARTS,
    MIN_FRAMES,
    MIN_KEYS,
    MIN_PARTS,
    TASKS,
    key_count_bounds,
    key_draw_text,
    key_draw_user,
    key_plan_user,
)
from anim_assets import mint_task_assets, sheets_part_hints, sheets_xml_block, xml_part_names
from anim_reflect import reflect_key
from glm_anim_two_stage import overlay_ground, write_contact_sheet, write_gif
from mint_plans import plan_has_cells
from sa_render import convert_completion, extract_strokes_xml
from terra_client import call_glm, parse_json_obj


def _parts(plan: dict) -> list:
    return plan.get("parts") or plan.get("strokes") or []


def _part_range(task: dict) -> tuple[int, int]:
    lo, hi = task.get("part_range", (MIN_PARTS, MAX_PARTS))
    return int(lo), int(hi)


def _part_slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(name or "").lower())


def merge_sheet_parts(plan: dict, sheet_parts: list[dict], hi: int) -> dict:
    """Keep character-sheet ids canonical; only add extras (ground, leash, person_*)."""
    if not sheet_parts:
        return plan
    sheet_slugs = {_part_slug(p.get("name")) for p in sheet_parts}
    suffixes = set(sheet_slugs)
    for p in sheet_parts:
        name = str(p.get("name") or "")
        if "_" in name:
            suffixes.add(_part_slug(name.split("_", 1)[1]))
    extras = []
    seen = set(sheet_slugs)
    for p in _parts(plan):
        key = _part_slug(p.get("name"))
        if not key or key in seen or key in suffixes:
            continue
        extras.append(p)
        seen.add(key)
    plan["parts"] = (list(sheet_parts) + extras)[:hi]
    return plan


def validate_key_plan(
    plan: dict,
    n_keys: int | None,
    task: dict,
    pin_frames: int | None = None,
) -> dict:
    if plan_has_cells(plan):
        raise ValueError("plan contains grid cells")
    keys = plan.get("keys")
    gaps = plan.get("gaps")
    lo, hi = key_count_bounds(pin_frames)
    if not isinstance(keys, list) or not (lo <= len(keys) <= hi):
        raise ValueError(f"need {lo}–{hi} keys, got {0 if not isinstance(keys, list) else len(keys)}")
    if n_keys is not None and len(keys) != int(n_keys):
        raise ValueError(f"need exactly {n_keys} keys")
    n_keys = len(keys)
    if not isinstance(gaps, list) or len(gaps) != n_keys - 1:
        raise ValueError(f"need exactly {n_keys - 1} gaps")
    parts = _parts(plan)
    plo, phi = _part_range(task)
    if not isinstance(parts, list) or not (plo <= len(parts) <= phi):
        raise ValueError(f"need {plo}–{phi} parts")
    for i, g in enumerate(gaps):
        n = int(g.get("n_inbetween", 0))
        if not 1 <= n <= 10:
            raise ValueError(f"gap {i} n_inbetween={n} not in 1–10")
        g["n_inbetween"] = n
        g["ease"] = str(g.get("ease") or "linear")
        if g["ease"] not in {"linear", "smooth", "ease_out"}:
            g["ease"] = "linear"
        keys[i].setdefault("name", f"k{i+1}")
    keys[-1].setdefault("name", "end")
    n_frames = n_keys + sum(int(g["n_inbetween"]) for g in gaps)
    if pin_frames:
        need = int(pin_frames) - n_keys
        got = sum(int(g["n_inbetween"]) for g in gaps)
        if got != need:
            last = need - sum(int(g["n_inbetween"]) for g in gaps[:-1])
            if not 1 <= last <= 10:
                raise ValueError(f"cannot fit {pin_frames} frames: inbetweens={got} need={need}")
            gaps[-1]["n_inbetween"] = last
            print(f"  pinned last gap n_inbetween -> {last} for {pin_frames} frames", flush=True)
        n_frames = int(pin_frames)
    if not MIN_FRAMES <= n_frames <= MAX_FRAMES:
        raise ValueError(f"clip length {n_frames} not in {MIN_FRAMES}–{MAX_FRAMES}")
    action = str(plan.get("action") or "").strip()
    if len(action) < 40:
        raise ValueError("need a detailed action rewrite of the prompt")
    plan["parts"] = parts
    plan["keys"] = keys
    plan["gaps"] = gaps
    plan["n_frames"] = n_frames
    plan["action"] = action
    return plan


def mint_key_plan(
    task: dict,
    n_keys: int | None = None,
    suggested_frames: int | None = None,
    pin_frames: int | None = None,
    attempts: int = 3,
) -> tuple[dict | None, str, str | None]:
    last_raw, last_err = "", None
    for attempt in range(1, attempts + 1):
        raw = call_glm(
            [
                {
                    "role": "system",
                    "content": KEY_PLAN_SYSTEM_ANIMAL
                    if task.get("kind") == "animal"
                    else KEY_PLAN_SYSTEM,
                },
                {
                    "role": "user",
                    "content": key_plan_user(
                        task, n_keys, suggested_frames=suggested_frames, pin_frames=pin_frames
                    ),
                },
            ],
            max_tokens=3072,
            temperature=0.4,
            reasoning_effort="low",
            timeout=180,
        )
        last_raw = raw
        try:
            plan = validate_key_plan(parse_json_obj(raw), n_keys, task, pin_frames=pin_frames)
            plan["task_id"] = task["task_id"]
            plan["planner"] = "glm-5.3-pose-to-pose"
            return plan, raw, None
        except Exception as e:
            last_err = f"attempt {attempt}: {type(e).__name__}: {e}"
            print(f"  plan {last_err}", flush=True)
            time.sleep(2)
    return None, last_raw, last_err


def draw_key(
    task: dict,
    plan: dict,
    key: dict,
    key_i: int,
    n_keys: int,
    prev_xml: str | None,
    png_path: Path,
    attempts: int = 3,
    asset_xml: str | None = None,
    required_ids: list[str] | None = None,
) -> tuple[dict, str]:
    layout = key_draw_text(plan, key, key_i, n_keys)
    last_raw, last_rec = "", {"valid": False, "error": "no draw"}
    system = ANIM_DRAW_SYSTEM_ANIMAL if task.get("kind") == "animal" or asset_xml else ANIM_DRAW_SYSTEM
    need = {re.sub(r"[^a-z0-9]+", "", n.lower()) for n in (required_ids or []) if n}
    for attempt in range(1, attempts + 1):
        raw = call_glm(
            [
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": key_draw_user(
                        task, layout, key.get("name", f"k{key_i}"), prev_xml, asset_xml=asset_xml
                    ),
                },
            ],
            max_tokens=3072,
            temperature=0.45,
            reasoning_effort="low",
            timeout=180,
        )
        last_raw = raw
        rec = convert_completion(raw, png_path)
        last_rec = rec
        n = rec.get("n_strokes") or 0
        intact_ok = rec.get("intact") or task.get("allow_detached_prop")
        n_min, n_max = _part_range(task)
        xml = extract_strokes_xml(raw)
        names_ok = True
        if need and xml:
            got = {re.sub(r"[^a-z0-9]+", "", n.lower()) for n in xml_part_names(xml)}
            hit = len(need & got)
            names_ok = hit >= max(3, int(0.6 * len(need)))
            if not names_ok:
                rec["error"] = f"sheet ids {hit}/{len(need)} (need {sorted(need)[:6]}...)"
        if rec.get("valid") and intact_ok and names_ok and n_min - 2 <= n <= n_max + 1:
            rec["attempt"] = attempt
            return rec, raw
        why = rec.get("error") or f"valid={rec.get('valid')} intact={rec.get('intact')} strokes={n}"
        print(f"  key {key.get('name')} attempt {attempt} rejected: {why}", flush=True)
        time.sleep(1)
    last_rec["attempt"] = attempts
    return last_rec, last_raw


def load_replay_keys(replay: Path, keys: list) -> dict[str, str]:
    xmls: dict[str, str] = {}
    for i, key in enumerate(keys, 1):
        name = str(key["name"])
        path = replay / f"key_{i:02d}_{name}.xml.txt"
        if not path.exists():
            matches = sorted(replay.glob(f"key_{i:02d}_*.xml.txt"))
            if not matches:
                raise SystemExit(f"replay missing {path}")
            path = matches[0]
        xmls[name] = path.read_text(encoding="utf-8")
    return xmls


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", default="serve", choices=sorted(TASKS))
    ap.add_argument(
        "--keys",
        type=int,
        default=None,
        help=f"pin key count ({MIN_KEYS}–{MAX_KEYS}). Default: planner chooses (≥{MIN_KEYS})",
    )
    ap.add_argument(
        "--frames",
        type=int,
        default=None,
        help=f"pin total clip length ({MIN_FRAMES}–{MAX_FRAMES}). Default: planner chooses; ~12 is only a hint",
    )
    ap.add_argument("--gif-ms", type=int, default=None)
    ap.add_argument("--replay", default=None, help="reuse key XML from a previous run; skip GLM draw")
    ap.add_argument("--no-reflect", action="store_true", help="skip vision reflection after each key")
    ap.add_argument(
        "--vision",
        default="deepseek",
        choices=["deepseek", "glm"],
        help="vision model for key reflection only (not inbetweens)",
    )
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    task = TASKS[args.task]
    suggested_frames = int(task.get("target_frames") or 12)
    pin_frames = int(args.frames) if args.frames is not None else None
    if pin_frames is not None and not MIN_FRAMES <= pin_frames <= MAX_FRAMES:
        raise SystemExit(f"--frames must be {MIN_FRAMES}–{MAX_FRAMES}")
    lo, hi = key_count_bounds(pin_frames)
    n_keys = int(args.keys) if args.keys is not None else None
    if n_keys is not None and not lo <= n_keys <= hi:
        raise SystemExit(f"--keys must be {lo}–{hi} for this frame budget")
    gif_ms = int(args.gif_ms if args.gif_ms is not None else task.get("gif_ms", 180))

    stamp = time.strftime("%Y%m%d_%H%M%S")
    out = Path(args.out) if args.out else HERE / "outputs" / f"glm53_keys_{task['task_id']}_{stamp}"
    keys_dir = out / "keys"
    frames_dir = out / "frames"
    keys_dir.mkdir(parents=True, exist_ok=True)
    frames_dir.mkdir(parents=True, exist_ok=True)

    keys_label = n_keys if n_keys is not None else f"auto {lo}–{hi}"
    frames_label = pin_frames if pin_frames is not None else f"auto ~{suggested_frames}"
    print(f"== key plan {task['task_id']} n_keys={keys_label} frames={frames_label} reflect={not args.no_reflect} vision={args.vision} -> {out} ==", flush=True)
    t0 = time.time()
    if args.replay:
        replay = Path(args.replay)
        plan = json.loads((replay / "plan.json").read_text(encoding="utf-8"))
        plan = validate_key_plan(plan, n_keys, task, pin_frames=pin_frames)
        n_keys = len(plan["keys"])
        plan_raw = (replay / "plan.raw.txt").read_text(encoding="utf-8") if (replay / "plan.raw.txt").exists() else ""
        plan_err = None
        plan_s = round(time.time() - t0, 2)
        (out / "plan.raw.txt").write_text(plan_raw, encoding="utf-8")
        (out / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  replay keys from {replay} {plan_s}s", flush=True)
        key_xml = load_replay_keys(replay, plan["keys"])
        concept = plan.get("concept") or task["concept"]
        key_rows = []
        for i, key in enumerate(plan["keys"], 1):
            name = str(key["name"])
            xml = key_xml[name]
            png = keys_dir / f"{i:02d}_{name}.png"
            rec = render_xml(f"<answer><concept>{concept}</concept>{xml}</answer>", png)
            if rec.get("valid"):
                overlay_ground(png)
            if rec.get("valid") and xml and not args.no_reflect:
                xml, _critique = reflect_key(
                    task,
                    xml,
                    png,
                    name,
                    concept,
                    out_json=out / f"key_{i:02d}_{name}.reflect.json",
                    vision=args.vision,
                )
                rec = render_xml(f"<answer><concept>{concept}</concept>{xml}</answer>", png)
                if rec.get("valid"):
                    overlay_ground(png)
                key_xml[name] = xml
            (out / f"key_{i:02d}_{name}.xml.txt").write_text(xml, encoding="utf-8")
            key_rows.append({"name": name, "valid": rec.get("valid"), "n_strokes": rec.get("n_strokes"), "seconds": 0, "error": rec.get("error"), "replay": True, "reflect": not args.no_reflect})
            print(f"  replay key {name} valid={rec.get('valid')} strokes={rec.get('n_strokes')}", flush=True)
    else:
        task = dict(task)
        asset_xml = None
        sheets: list = []
        if task.get("assets"):
            sheets = mint_task_assets(task, out / "assets")
            asset_xml = sheets_xml_block(sheets)
            hints = sheets_part_hints(sheets)
            task["sheet_part_names"] = [p["name"] for p in hints]
            lo, hi = _part_range(task)
            n_sheet = len(task["sheet_part_names"])
            task["part_range"] = (min(lo, max(MIN_PARTS, n_sheet)), min(MAX_PARTS, max(hi, n_sheet + 4)))
        plan, plan_raw, plan_err = mint_key_plan(
            task, n_keys, suggested_frames=suggested_frames, pin_frames=pin_frames
        )
        plan_s = round(time.time() - t0, 2)
        if plan is not None and sheets:
            _, hi = _part_range(task)
            plan = merge_sheet_parts(plan, sheets_part_hints(sheets), hi)
        (out / "plan.raw.txt").write_text(plan_raw, encoding="utf-8")
        if plan is not None:
            (out / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
            action = str(plan.get("action") or "").strip()
            if action:
                (out / "action.txt").write_text(action + "\n", encoding="utf-8")
        print(f"  plan {plan_s}s ok={plan is not None} {plan_err or ''}", flush=True)
        if plan is None:
            (out / "summary.json").write_text(json.dumps({"ok": False, "plan_error": plan_err}, indent=2), encoding="utf-8")
            raise SystemExit(1)
        n_keys = len(plan["keys"])
        print(
            f"  planner chose {n_keys} keys, {plan.get('n_frames')} frames: "
            f"{[k.get('name') for k in plan['keys']]} gaps={[g.get('n_inbetween') for g in plan['gaps']]}",
            flush=True,
        )
        action = str(plan.get("action") or "").strip()
        if action:
            print("  action:", flush=True)
            for line in action.splitlines() or [action]:
                print(f"    {line}", flush=True)

        key_xml = {}
        key_rows = []
        prev_xml = None
        concept = plan.get("concept") or task["concept"]
        for i, key in enumerate(plan["keys"], 1):
            name = str(key["name"])
            png = keys_dir / f"{i:02d}_{name}.png"
            print(f"== draw key {i}/{n_keys} {name} ==", flush=True)
            t1 = time.time()
            rec, raw = draw_key(
                task,
                plan,
                key,
                i,
                n_keys,
                prev_xml,
                png,
                asset_xml=asset_xml,
                required_ids=task.get("sheet_part_names"),
            )
            draw_s = round(time.time() - t1, 2)
            (out / f"key_{i:02d}_{name}.raw.txt").write_text(raw, encoding="utf-8")
            xml = extract_strokes_xml(raw)
            if rec.get("valid") and xml and key_xml:
                xml = pin_anchored_xml(
                    xml,
                    next(iter(key_xml.values())),
                    extra=anchored_names_from_parts(_parts(plan)),
                )
                rec = render_xml(f"<answer><concept>{concept}</concept>{xml}</answer>", png)
            if xml:
                (out / f"key_{i:02d}_{name}.xml.txt").write_text(xml, encoding="utf-8")
            reflected = False
            if rec.get("valid") and xml:
                overlay_ground(png)
                if not args.no_reflect:
                    xml, critique = reflect_key(
                        task,
                        xml,
                        png,
                        name,
                        concept,
                        out_json=out / f"key_{i:02d}_{name}.reflect.json",
                        vision=args.vision,
                    )
                    reflected = True
                    (out / f"key_{i:02d}_{name}.xml.txt").write_text(xml, encoding="utf-8")
                    overlay_ground(png)
                key_xml[name] = xml
                prev_xml = xml
            print(
                f"  draw {draw_s}s valid={rec.get('valid')} intact={rec.get('intact')} "
                f"strokes={rec.get('n_strokes')} reflect={reflected}",
                flush=True,
            )
            key_rows.append(
                {
                    "name": name,
                    "valid": rec.get("valid"),
                    "n_strokes": rec.get("n_strokes"),
                    "seconds": draw_s,
                    "error": rec.get("error"),
                    "reflect": reflected,
                }
            )

    if len(key_xml) != n_keys:
        (out / "summary.json").write_text(
            json.dumps({"ok": False, "error": "missing keys", "key_rows": key_rows}, indent=2),
            encoding="utf-8",
        )
        raise SystemExit(1)

    timeline = expand_timeline(plan["keys"], plan["gaps"])
    pngs = []
    labels = []
    frame_rows = []
    for slot in timeline:
        i = slot["i"]
        png = frames_dir / f"f{i:02d}.png"
        if slot["kind"] == "key":
            xml = key_xml[slot["key_name"]]
            rec = render_xml(f"<answer><concept>{concept}</concept>{xml}</answer>", png)
            label = f"K:{slot['key_name']}"
        else:
            xml = interpolate_xml(
                key_xml[slot["from"]],
                key_xml[slot["to"]],
                float(slot["t"]),
                concept,
                ease_kind=str(slot.get("ease") or "linear"),
                extra=anchored_names_from_parts(_parts(plan)),
            )
            (out / f"f{i:02d}.xml.txt").write_text(xml, encoding="utf-8")
            rec = render_xml(xml, png)
            label = f"i{slot['from'][:1]}-{slot['to'][:1]}"
        if rec.get("valid"):
            overlay_ground(png)
            pngs.append(png)
            labels.append(label[:12])
        print(f"  frame {i} {label} valid={rec.get('valid')} strokes={rec.get('n_strokes')}", flush=True)
        frame_rows.append({"i": i, "kind": slot["kind"], "label": label, "valid": rec.get("valid"), "error": rec.get("error")})

    gif = out / "clip.gif"
    sheet = out / "contact_sheet.png"
    if pngs:
        write_gif(pngs, gif, duration_ms=gif_ms)
        write_contact_sheet(pngs, sheet, labels=labels, cols=8 if len(pngs) >= 12 else None)
        print(f"wrote {gif} and {sheet} gif_ms={gif_ms}", flush=True)

    summary = {
        "model": "glm-5.3",
        "pipeline": "pose_to_pose_keys_plus_lerp_reflect",
        "task_id": task["task_id"],
        "n_keys": n_keys,
        "n_frames": len(timeline),
        "suggested_frames": suggested_frames,
        "pin_frames": pin_frames,
        "action": plan.get("action"),
        "gif_ms": gif_ms,
        "plan_seconds": plan_s,
        "replay": args.replay,
        "reflect": not args.no_reflect,
        "vision": None if args.no_reflect else args.vision,
        "gaps": plan["gaps"],
        "key_rows": key_rows,
        "frame_rows": frame_rows,
        "ok": all(r.get("valid") for r in frame_rows) and len(pngs) == len(timeline),
        "gif": str(gif) if pngs else None,
        "contact_sheet": str(sheet) if pngs else None,
    }
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {out / 'summary.json'} ok={summary['ok']} frames={summary['n_frames']}", flush=True)


if __name__ == "__main__":
    main()
