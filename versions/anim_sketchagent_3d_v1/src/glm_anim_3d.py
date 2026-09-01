#!/usr/bin/env python3
"""3D pose-to-pose: GLM plans keys; incremental Path3D draws keys; GLM one-shot fills inbetweens."""
from __future__ import annotations

import argparse
import copy
import json
import re
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
ROOT = next(
    (parent for parent in HERE.parents if (parent / "versions" / "path3d_v1").exists()),
    HERE.parents[1],
)
PILOT = ROOT / "experiments" / "grpo_sa_pilot"
for p in (
    ROOT,
    ROOT / "versions" / "path3d_v1",
    ROOT / "versions" / "path3d_json_v1",
    ROOT / "versions" / "v1.4",
    ROOT / "versions" / "path3d_incremental_base_v1",
    PILOT,
    HERE,
):
    sp = str(p)
    if sp in sys.path:
        sys.path.remove(sp)
    sys.path.insert(0, sp)
if str(HERE) in sys.path:
    sys.path.remove(str(HERE))
sys.path.insert(0, str(HERE))

from glm_ds_roles import GlmDsEditor, GlmDsPlanner  # noqa: E402
from oneshot_glm import generate_scene, render_scene  # noqa: E402
from path3d.schema import Path3DScene  # noqa: E402
from path3d_json_agents.incremental import StructuredIncrementalPath3DLoop  # noqa: E402
from prompts import (  # noqa: E402
    KEY_PLAN_SYSTEM,
    MAX_FRAMES,
    MAX_KEYS,
    MIN_FRAMES,
    MIN_KEYS,
    TASKS,
    inbetween_oneshot_prompt,
    INBETWEEN_REASONING,
    key_count_bounds,
    key_draw_prompt,
    key_plan_user,
    people_scale_line,
)
from terra_client import call_sol, parse_json_obj  # noqa: E402


def plan_has_cells(plan: dict) -> bool:
    return bool(re.search(r"x\d+y\d+", json.dumps(plan, ensure_ascii=False), re.I))


def _part_ids(plan: dict) -> list[str]:
    return [str(item.get("id") or "").strip() for item in plan.get("parts") or [] if str(item.get("id") or "").strip()]


def _anchored_ids(plan: dict) -> list[str]:
    return [
        str(item.get("id") or "").strip()
        for item in plan.get("parts") or []
        if str(item.get("id") or "").strip() and str(item.get("motion") or "").lower() == "anchored"
    ]


def _belongs_to_part(stroke_id: str, part_id: str) -> bool:
    return stroke_id == part_id or stroke_id.startswith(part_id + "_")


def scene_contract_report(scene: dict, plan: dict, *, canonical_ids: set[str] | None = None) -> dict:
    ids = [str(item.get("id") or "").strip() for item in scene.get("strokes") or []]
    parts = _part_ids(plan)
    missing = [part_id for part_id in parts if part_id not in ids]
    unknown = [
        stroke_id
        for stroke_id in ids
        if stroke_id and not any(_belongs_to_part(stroke_id, part_id) for part_id in parts)
    ]
    canonical_missing = sorted((canonical_ids or set()) - set(ids))
    return {
        "ok": not missing and not canonical_missing,
        "stroke_count": len(ids),
        "missing_part_ids": missing,
        "canonical_missing": canonical_missing,
        "unknown_ids": unknown,
    }


def require_scene_contract(
    scene: dict,
    plan: dict,
    *,
    label: str,
    canonical_ids: set[str] | None = None,
) -> dict:
    report = scene_contract_report(scene, plan, canonical_ids=canonical_ids)
    if not report["ok"]:
        raise ValueError(
            f"{label} violates part-id contract: "
            f"missing={report['missing_part_ids']} canonical_missing={report['canonical_missing']}"
        )
    return report


def pin_anchored_scene(scene: dict, anchor_scene: dict, plan: dict) -> dict:
    """Copy all first-key strokes belonging to anchored plan parts into this scene."""
    anchored = _anchored_ids(plan)
    if not anchored:
        return copy.deepcopy(scene)
    source = [
        copy.deepcopy(item)
        for item in anchor_scene.get("strokes") or []
        if any(_belongs_to_part(str(item.get("id") or ""), part_id) for part_id in anchored)
    ]
    if not source:
        raise ValueError(f"first key is missing anchored strokes: {anchored}")
    kept = [
        copy.deepcopy(item)
        for item in scene.get("strokes") or []
        if not any(_belongs_to_part(str(item.get("id") or ""), part_id) for part_id in anchored)
    ]
    value = copy.deepcopy(scene)
    value["strokes"] = kept + source
    metadata = dict(value.get("metadata") or {})
    metadata["animation_anchors_pinned_from"] = "first_key"
    value["metadata"] = metadata
    return value


def expand_timeline(keys: list[dict], gaps: list[dict]) -> list[dict]:
    if len(gaps) != len(keys) - 1:
        raise ValueError("gaps must be one per key interval")
    timeline = []
    idx = 1
    for i, key in enumerate(keys):
        timeline.append({"i": idx, "kind": "key", "key_name": key["name"], "key": key})
        idx += 1
        if i == len(keys) - 1:
            break
        n = min(10, max(1, int(gaps[i].get("n_inbetween", 2))))
        ease_kind = str(gaps[i].get("ease", "linear"))
        for k in range(1, n + 1):
            timeline.append(
                {
                    "i": idx,
                    "kind": "inbetween",
                    "t": k / (n + 1),
                    "from": key["name"],
                    "to": keys[i + 1]["name"],
                    "ease": ease_kind,
                    "gap": i,
                }
            )
            idx += 1
    stamp_frame_span(timeline)
    return timeline


def stamp_frame_span(timeline: list[dict]) -> list[dict]:
    n_frames = len(timeline)
    next_key = None
    for slot in reversed(timeline):
        if slot.get("kind") == "key":
            next_key = slot["i"]
        slot["n_frames"] = n_frames
        slot["current_frame"] = slot["i"]
        slot["from_frame"] = slot["i"] - 1 if slot["i"] > 1 else None
        slot["to_frame"] = next_key
    return timeline


def validate_key_plan(plan: dict, n_keys: int | None, task: dict, pin_frames: int | None = None) -> dict:
    if plan_has_cells(plan):
        raise ValueError("plan contains grid cells")
    keys = plan.get("keys")
    gaps = plan.get("gaps")
    lo, hi = key_count_bounds(pin_frames)
    if not isinstance(keys, list) or not (lo <= len(keys) <= hi):
        raise ValueError(f"need {lo}–{hi} keys")
    if n_keys is not None and len(keys) != int(n_keys):
        raise ValueError(f"need exactly {n_keys} keys")
    n_keys = len(keys)
    if not isinstance(gaps, list) or len(gaps) != n_keys - 1:
        raise ValueError(f"need exactly {n_keys - 1} gaps")
    parts = plan.get("parts") or []
    plo, phi = task.get("part_range", (6, 20))
    if not isinstance(parts, list) or not (int(plo) <= len(parts) <= int(phi)):
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
        last = need - sum(int(g["n_inbetween"]) for g in gaps[:-1])
        if not 1 <= last <= 10:
            raise ValueError(f"cannot fit {pin_frames} frames")
        gaps[-1]["n_inbetween"] = last
        n_frames = int(pin_frames)
    if not MIN_FRAMES <= n_frames <= MAX_FRAMES:
        raise ValueError(f"clip length {n_frames} not in {MIN_FRAMES}–{MAX_FRAMES}")
    action = str(plan.get("action") or "").strip()
    if len(action) < 40:
        raise ValueError("need a detailed action rewrite")
    plan["parts"] = parts
    plan["keys"] = keys
    plan["gaps"] = gaps
    plan["n_frames"] = n_frames
    plan["action"] = action
    return plan


def mint_key_plan(task: dict, n_keys: int | None, pin_frames: int | None, suggested_frames: int) -> tuple[dict | None, str, str | None]:
    last_raw, last_err = "", None
    for attempt in range(1, 4):
        raw = call_sol(
            [
                {"role": "system", "content": KEY_PLAN_SYSTEM},
                {
                    "role": "user",
                    "content": key_plan_user(
                        task, n_keys, suggested_frames=suggested_frames, pin_frames=pin_frames
                    ),
                },
            ],
            max_tokens=8192,
            temperature=0.4,
            timeout=180,
        )
        last_raw = raw
        try:
            plan = validate_key_plan(parse_json_obj(raw), n_keys, task, pin_frames=pin_frames)
            plan["task_id"] = task["task_id"]
            plan["planner"] = "gpt-5.6-sol-pose-to-pose-3d"
            plan["people_scale"] = people_scale_line(task)
            return plan, raw, None
        except Exception as e:
            last_err = f"attempt {attempt}: {type(e).__name__}: {e}"
            print(f"  plan {last_err}", flush=True)
            time.sleep(2)
    return None, last_raw, last_err


def label_frame(im: Image.Image, text: str) -> Image.Image:
    rgb = im.convert("RGB")
    draw = ImageDraw.Draw(rgb)
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None
    draw.rectangle((4, 4, 4 + 8 * max(6, len(text)), 20), fill="white")
    draw.text((6, 6), text[:18], fill="black", font=font)
    return rgb


def write_gif(paths: list[Path], out: Path, duration_ms: int = 80) -> None:
    frames = [label_frame(Image.open(p), f"f{i+1}") for i, p in enumerate(paths)]
    frames[0].save(out, save_all=True, append_images=frames[1:], duration=duration_ms, loop=0)


def write_contact_sheet(paths: list[Path], out: Path, labels: list[str] | None = None) -> None:
    labels = labels or [f"f{i+1}" for i in range(len(paths))]
    images = [label_frame(Image.open(p), labels[i] if i < len(labels) else f"f{i+1}") for i, p in enumerate(paths)]
    w, h = images[0].size
    gap = 8
    n = len(images)
    cols = 8 if n >= 12 else n
    rows = (n + cols - 1) // cols
    sheet = Image.new("RGB", (w * cols + gap * (cols - 1), h * rows + gap * (rows - 1)), "white")
    for i, im in enumerate(images):
        r, c = divmod(i, cols)
        sheet.paste(im, (c * (w + gap), r * (h + gap)))
    sheet.save(out)


def draw_key_incremental(prompt: str, out_dir: Path, *, max_rounds: int, width: int, height: int):
    loop = StructuredIncrementalPath3DLoop(
        output_dir=out_dir,
        planner=GlmDsPlanner(),
        editor=GlmDsEditor(),
        max_rounds=max_rounds,
        max_patch_attempts=3,
        max_additions_per_patch=48,
    )
    return loop.run(prompt, width=width, height=height)


def load_run_keys(out: Path, plan: dict) -> tuple[dict[str, dict], dict, set[str]]:
    key_scenes: dict[str, dict] = {}
    for i, key in enumerate(plan.get("keys") or [], 1):
        name = str(key.get("name") or "")
        path = out / "keys" / f"{i:02d}_{name}" / "final" / "scene.json"
        if not path.exists():
            raise FileNotFoundError(f"missing accepted key scene: {path}")
        key_scenes[name] = json.loads(path.read_text(encoding="utf-8"))
    first_name = str(plan["keys"][0]["name"])
    anchor = copy.deepcopy(key_scenes[first_name])
    canonical = {
        str(item.get("id") or "").strip()
        for item in anchor.get("strokes") or []
        if str(item.get("id") or "").strip()
    }
    return key_scenes, anchor, canonical


def generate_inbetween(
    prompt: str,
    plan: dict,
    anchor_scene: dict,
    dest: Path,
    *,
    canonical_ids: set[str],
    attempts: int = 2,
) -> tuple[Path3DScene, str, dict, int]:
    last_error: Exception | None = None
    last_raw = ""
    user_content = prompt
    dest.mkdir(parents=True, exist_ok=True)
    for attempt in range(1, attempts + 1):
        try:
            scene, last_raw = generate_scene(user_content, extra_system=INBETWEEN_REASONING)
            value = pin_anchored_scene(scene.to_dict(), anchor_scene, plan)
            report = require_scene_contract(
                value,
                plan,
                label=f"inbetween attempt {attempt}",
                canonical_ids=canonical_ids,
            )
            (dest / f"attempt_{attempt:02d}.raw.txt").write_text(last_raw, encoding="utf-8")
            return Path3DScene.from_dict(value, prompt=plan.get("concept", "")), last_raw, report, attempt
        except Exception as exc:
            last_error = exc
            (dest / f"attempt_{attempt:02d}.raw.txt").write_text(last_raw or str(exc), encoding="utf-8")
            user_content = (
                prompt
                + "\n\nThe previous attempt violated the animation identity contract. "
                + f"Repair it: {exc}. Reuse every exact part id and every canonical stroke id; "
                + "do not add another person or rename with _new/_emerge/_2. Return one complete Path3D JSON."
            )
    raise ValueError(f"inbetween contract failed after {attempts} attempts: {last_error}") from last_error


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", default="tabledrop", choices=sorted(TASKS))
    ap.add_argument("--keys", type=int, default=None)
    ap.add_argument("--frames", type=int, default=None)
    ap.add_argument("--max-rounds", type=int, default=4, help="incremental rounds per key")
    ap.add_argument("--key-attempts", type=int, default=2, help="full incremental retries if a key breaks the id contract")
    ap.add_argument("--keys-only", action="store_true", help="draw key poses then stop; skip inbetweens and full clip")
    ap.add_argument(
        "--from-run",
        type=Path,
        default=None,
        help="reuse an existing keys-only (or completed) run: load plan+keys, draw incremental inbetweens only",
    )
    ap.add_argument("--gif-ms", type=int, default=None)
    ap.add_argument("--width", type=int, default=512)
    ap.add_argument("--height", type=int, default=512)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    t_wall = time.time()
    task = TASKS[args.task]
    suggested_frames = int(task.get("target_frames") or 12)
    pin_frames = int(args.frames) if args.frames is not None else None
    lo, hi = key_count_bounds(pin_frames)
    n_keys = int(args.keys) if args.keys is not None else None
    if n_keys is not None and not lo <= n_keys <= hi:
        raise SystemExit(f"--keys must be {lo}–{hi}")
    gif_ms = int(args.gif_ms if args.gif_ms is not None else task.get("gif_ms", 80))
    stamp = time.strftime("%Y%m%d_%H%M%S")

    if args.from_run is not None:
        out = args.from_run if args.from_run.is_absolute() else HERE / args.from_run
        plan_path = out / "plan.json"
        if not plan_path.exists():
            raise SystemExit(f"--from-run missing {plan_path}")
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        task_id = str(plan.get("task_id") or task["task_id"])
        if task_id in TASKS:
            task = TASKS[task_id] if task_id in TASKS else task
        # task_id is anim3d_pillar_peek, TASKS keys are pillar_peek
        for name, spec in TASKS.items():
            if spec.get("task_id") == task_id:
                task = spec
                gif_ms = int(args.gif_ms if args.gif_ms is not None else task.get("gif_ms", 80))
                break
        plan["people_scale"] = people_scale_line(plan) if plan.get("people_scale") else people_scale_line(task)
        n_keys = len(plan.get("keys") or [])
        key_scenes, anchor_scene, canonical_ids = load_run_keys(out, plan)
        for name, scene in key_scenes.items():
            require_scene_contract(scene, plan, label=f"loaded key {name}", canonical_ids=canonical_ids)
        key_rows = [{"name": k["name"], "ok": True, "loaded": True} for k in plan["keys"]]
        print(
            f"== from-run {out} keys={ [k.get('name') for k in plan['keys']] } "
            f"frames={plan.get('n_frames')} incremental inbetweens ==",
            flush=True,
        )
        print("  action:", flush=True)
        print(f"    {plan.get('action')}", flush=True)
    else:
        out = Path(args.out) if args.out else HERE / "outputs" / f"anim3d_{task['task_id']}_{stamp}"
        out.mkdir(parents=True, exist_ok=True)

        print(
            f"== 3d key plan {task['task_id']} n_keys={n_keys or f'auto {lo}–{hi}'} "
            f"frames={pin_frames or f'auto ~{suggested_frames}'} -> {out} ==",
            flush=True,
        )
        t0 = time.time()
        plan, plan_raw, plan_err = mint_key_plan(task, n_keys, pin_frames, suggested_frames)
        (out / "plan.raw.txt").write_text(plan_raw, encoding="utf-8")
        if plan is None:
            (out / "summary.json").write_text(json.dumps({"ok": False, "plan_error": plan_err}, indent=2), encoding="utf-8")
            raise SystemExit(1)
        (out / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
        (out / "action.txt").write_text(plan["action"] + "\n", encoding="utf-8")
        n_keys = len(plan["keys"])
        print(
            f"  plan {round(time.time()-t0, 2)}s {n_keys} keys, {plan['n_frames']} frames "
            f"{[k.get('name') for k in plan['keys']]} gaps={[g.get('n_inbetween') for g in plan['gaps']]}",
            flush=True,
        )
        print("  action:", flush=True)
        print(f"    {plan['action']}", flush=True)

        key_scenes = {}
        key_rows = []
        anchor_scene = None
        canonical_ids = None
        prev_scene = None
        prev_name = ""
        for i, key in enumerate(plan["keys"], 1):
            name = str(key["name"])
            key_dir = out / "keys" / f"{i:02d}_{name}"
            key_dir.mkdir(parents=True, exist_ok=True)
            prompt = key_draw_prompt(
                plan, key, i, n_keys, prev_scene=prev_scene, prev_name=prev_name
            )
            (key_dir / "draw_prompt.txt").write_text(prompt, encoding="utf-8")
            print(f"== incremental key {i}/{n_keys} {name} ==", flush=True)
            t1 = time.time()
            result = None
            accepted_scene = None
            contract = None
            last_error = ""
            accepted_attempt = 0
            for attempt in range(1, max(1, int(args.key_attempts)) + 1):
                attempt_dir = key_dir / f"attempt_{attempt:02d}"
                try:
                    result = draw_key_incremental(
                        prompt,
                        attempt_dir,
                        max_rounds=args.max_rounds,
                        width=args.width,
                        height=args.height,
                    )
                    scene_path = attempt_dir / "final" / "scene.json"
                    if not scene_path.exists() or result.status == "failed":
                        raise ValueError(f"incremental status={result.status}, scene_exists={scene_path.exists()}")
                    value = json.loads(scene_path.read_text(encoding="utf-8"))
                    if anchor_scene is not None:
                        value = pin_anchored_scene(value, anchor_scene, plan)
                    contract = require_scene_contract(
                        value,
                        plan,
                        label=f"key {name} attempt {attempt}",
                        canonical_ids=canonical_ids,
                    )
                    accepted_scene = value
                    accepted_attempt = attempt
                    break
                except Exception as exc:
                    last_error = f"{type(exc).__name__}: {exc}"
                    print(f"  key {name} attempt {attempt} rejected: {last_error}", flush=True)
            ok = accepted_scene is not None and result is not None
            if ok and accepted_scene is not None:
                if anchor_scene is None:
                    anchor_scene = copy.deepcopy(accepted_scene)
                    canonical_ids = {
                        str(item.get("id") or "").strip()
                        for item in accepted_scene.get("strokes") or []
                        if str(item.get("id") or "").strip()
                    }
                key_scenes[name] = accepted_scene
                prev_scene = copy.deepcopy(accepted_scene)
                prev_name = name
                scene = Path3DScene.from_dict(accepted_scene, prompt=plan.get("concept", ""))
                rec = render_scene(scene, key_dir / "final", width=args.width, height=args.height, normalize=False)
                (key_dir / "final" / "contract.json").write_text(
                    json.dumps(contract, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            print(
                f"  key {name} {round(time.time()-t1, 2)}s "
                f"status={result.status if result else 'failed'} "
                f"rev={result.best_revision if result else None} "
                f"rounds={result.rounds_completed if result else 0} attempt={accepted_attempt}",
                flush=True,
            )
            key_rows.append(
                {
                    "name": name,
                    "ok": ok,
                    "status": result.status if result else "failed",
                    "best_revision": result.best_revision if result else None,
                    "attempt": accepted_attempt,
                    "contract": contract,
                    "prior_attempt_error": last_error or None,
                    "seconds": round(time.time() - t1, 2),
                }
            )
            if not ok:
                (out / "summary.json").write_text(
                    json.dumps({"ok": False, "error": f"key {name} failed", "key_rows": key_rows}, indent=2),
                    encoding="utf-8",
                )
                raise SystemExit(1)

        if args.keys_only:
            pngs = []
            labels = []
            sheets = []
            for i, key in enumerate(plan["keys"], 1):
                name = str(key["name"])
                key_final = out / "keys" / f"{i:02d}_{name}" / "final" / "views"
                pngs.append(key_final / "view_perspective.png")
                labels.append(f"K:{name}"[:12])
                sheets.append(key_final / "contact_sheet.png")
            gif = out / "clip.gif"
            sheet = out / "contact_sheet.png"
            write_gif(pngs, gif, duration_ms=max(gif_ms, 400))
            write_contact_sheet(pngs, sheet, labels=labels)
            summary = {
                "ok": True,
                "pipeline": "plan_keys_incremental_only",
                "keys_only": True,
                "models": {
                    "plan": "gpt-5.6-sol",
                    "incremental_visual_review_and_edit": "gpt-5.6-sol",
                },
                "id_rename_rule": "ANIM_EDITOR_SYSTEM_PROMPT",
                "fixed_world_framing": True,
                "anchored_part_ids": _anchored_ids(plan),
                "canonical_stroke_ids": sorted(canonical_ids),
                "task_id": task["task_id"],
                "n_keys": n_keys,
                "n_frames": n_keys,
                "gif_ms": max(gif_ms, 400),
                "action": plan.get("action"),
                "key_rows": key_rows,
                "key_contact_sheets": [str(p) for p in sheets],
                "gif": str(gif),
                "contact_sheet": str(sheet),
                "wall_seconds": round(time.time() - t_wall, 2),
            }
            (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
            print(
                f"wrote {gif} keys_only n_keys={n_keys} ok=True wall_seconds={summary['wall_seconds']}",
                flush=True,
            )
            return

    if anchor_scene is None or canonical_ids is None:
        raise SystemExit("no accepted key scene")

    timeline = expand_timeline(plan["keys"], plan["gaps"])
    frames_dir = out / "frames"
    frames_dir.mkdir(exist_ok=True)
    pngs: list[Path] = []
    labels: list[str] = []
    frame_rows = []
    drawn: dict[int, dict] = {}
    n_frames = len(timeline)
    for slot in timeline:
        i = slot["i"]
        dest = frames_dir / f"f{i:02d}"
        dest.mkdir(exist_ok=True)
        contract = None
        generation_attempt = 0
        if slot["kind"] == "key":
            scene = Path3DScene.from_dict(key_scenes[slot["key_name"]], prompt=plan.get("concept", ""))
            contract = require_scene_contract(
                scene.to_dict(),
                plan,
                label=f"timeline key {slot['key_name']}",
                canonical_ids=canonical_ids,
            )
            rec = render_scene(scene, dest, width=args.width, height=args.height, normalize=False)
            label = f"K:{slot['key_name']}"
            drawn[i] = copy.deepcopy(scene.to_dict())
        else:
            prev = drawn.get(i - 1) or key_scenes[slot["from"]]
            nxt = key_scenes[slot["to"]]
            print(
                f"== oneshot inbetween frame {i}/{n_frames} from={i-1} to_key={slot.get('to_frame')} ({slot['to']}) ==",
                flush=True,
            )
            t1 = time.time()
            prompt = inbetween_oneshot_prompt(plan, slot, prev, nxt)
            prompt += (
                "\n\nCROSS-KEY IDENTITY CONTRACT:\n"
                f"Include every canonical stroke id exactly once: {sorted(canonical_ids)}.\n"
            )
            scene, raw, contract, generation_attempt = generate_inbetween(
                prompt,
                plan,
                anchor_scene,
                dest,
                canonical_ids=canonical_ids,
            )
            (dest / "raw.txt").write_text(raw, encoding="utf-8")
            (dest / "contract.json").write_text(
                json.dumps(contract, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            rec = render_scene(scene, dest, width=args.width, height=args.height, normalize=False)
            label = f"f{i-1}->k{slot.get('to_frame')}"
            drawn[i] = copy.deepcopy(scene.to_dict())
            print(
                f"  inbetween {round(time.time()-t1, 2)}s strokes={rec['stroke_count']} "
                f"attempt={generation_attempt}",
                flush=True,
            )
        png = Path(rec["perspective"])
        pngs.append(png)
        labels.append(label[:12])
        frame_rows.append(
            {
                "i": i,
                "kind": slot["kind"],
                "label": label,
                "strokes": rec["stroke_count"],
                "attempt": generation_attempt,
                "from_frame": slot.get("from_frame"),
                "to_frame": slot.get("to_frame"),
                "contract": contract,
            }
        )

    gif = out / "clip.gif"
    sheet = out / "contact_sheet.png"
    write_gif(pngs, gif, duration_ms=gif_ms)
    write_contact_sheet(pngs, sheet, labels=labels)
    summary = {
        "ok": True,
        "pipeline": "plan_keys_incremental_inbetweens_oneshot",
        "models": {
            "plan_and_oneshot_inbetween": "gpt-5.6-sol",
            "incremental_key_visual_review_and_edit": "gpt-5.6-sol",
        },
        "reflection": False,
        "fixed_world_framing": True,
        "anchored_part_ids": _anchored_ids(plan),
        "canonical_stroke_ids": sorted(canonical_ids),
        "task_id": task["task_id"],
        "n_keys": n_keys,
        "n_frames": len(timeline),
        "gif_ms": gif_ms,
        "action": plan.get("action"),
        "gaps": plan["gaps"],
        "key_rows": key_rows,
        "frame_rows": frame_rows,
        "gif": str(gif),
        "contact_sheet": str(sheet),
        "wall_seconds": round(time.time() - t_wall, 2),
    }
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"wrote {gif} frames={len(timeline)} ok=True wall_seconds={summary['wall_seconds']}",
        flush=True,
    )


if __name__ == "__main__":
    main()
