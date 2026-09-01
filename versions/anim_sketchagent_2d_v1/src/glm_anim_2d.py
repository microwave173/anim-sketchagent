#!/usr/bin/env python3
"""2D pose-to-pose: DeepSeek flash one-shot keys and inbetweens (thinking on)."""
from __future__ import annotations

import argparse
import copy
import json
import shutil
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
ROOT = next(
    (parent for parent in HERE.parents if (parent / "versions" / "path2d_v1").exists()),
    HERE.parents[1],
)
PILOT = ROOT / "experiments" / "grpo_sa_pilot"
for p in (ROOT, ROOT / "versions" / "path2d_v1", PILOT, HERE):
    sp = str(p)
    if sp in sys.path:
        sys.path.remove(sp)
    sys.path.insert(0, sp)

from glm_ds_roles import GlmDsEditor, GlmDsPlanner  # noqa: E402
from incremental import Path2DIncrementalLoop  # noqa: E402
from key_reflect import review_key_experience, select_key_winner, should_redraw  # noqa: E402
from interp import (  # noqa: E402
    expand_timeline,
    frames_to_redraw,
    interpolate_scene,
    pin_anchored_scene,
    scene_contract_report,
)
from path2d.generator import SYSTEM_PROMPT  # noqa: E402
from path2d.geometry import sample_stroke  # noqa: E402
from path2d.parser import parse_path2d  # noqa: E402
from path2d.renderer import render_scene  # noqa: E402
from path2d.schema import Path2DScene  # noqa: E402
from prompts import (  # noqa: E402
    DRAWER_ORIENTATION,
    INBETWEEN_REASONING,
    KEY_PLAN_SYSTEM,
    MAX_FRAMES,
    MIN_FRAMES,
    TASKS,
    inbetween_oneshot_prompt,
    key_count_bounds,
    key_draw_prompt,
    key_plan_user,
)
from terra_client import call_deepseek, call_glm, call_sol, parse_json_obj  # noqa: E402

TEXT_MODEL = "gpt-5.6-sol"
PLAN_REASONING_EFFORT = "high"
DRAW_REASONING_EFFORT = "high"
KEY_REASONING_EFFORT = "high"
FIRST_KEY_REASONING_EFFORT = "high"
_GLM_MEDIUM_WARNED = False


def text_model_name() -> str:
    return TEXT_MODEL


def thinking_enabled() -> bool:
    return not TEXT_MODEL.startswith("deepseek")


def call_text(
    messages: list[dict],
    *,
    max_tokens: int,
    temperature: float = 0.4,
    timeout: int = 300,
    reasoning_effort: str | None = None,
) -> str:
    effort = reasoning_effort or DRAW_REASONING_EFFORT
    if TEXT_MODEL.startswith("deepseek"):
        return call_deepseek(
            messages,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=timeout,
            model=TEXT_MODEL,
            extra={"thinking": {"type": "disabled"}},
        )
    if TEXT_MODEL.startswith("glm"):
        glm_effort = effort
        if glm_effort == "medium":
            glm_effort = "low"
            global _GLM_MEDIUM_WARNED
            if not _GLM_MEDIUM_WARNED:
                print("  glm-5.3 thinking has no medium; using low instead of medium", flush=True)
                _GLM_MEDIUM_WARNED = True
        return call_glm(
            messages,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=timeout,
            reasoning_effort=glm_effort,
        )
    return call_sol(
        messages,
        max_tokens=max_tokens,
        temperature=temperature,
        timeout=timeout,
        reasoning_effort=effort,
        thinking=True,
    )

DRAWER_SYSTEM = (
    SYSTEM_PROMPT.replace(
        "Prefer L for limbs. Circles/heads may use several Q segments or a small octagon of L, then Z.",
        "Prefer Q/C for swinging or bent limbs, spines, tails, and rounded bodies. "
        "Heads and other circles MUST be round Q loops (four or more Q, then Z). "
        "Do not draw heads as polygons of L. "
        "Straight L is required for ground, poles, posts, flat edges, and rigid shafts.",
    ).rstrip()
    + "\n"
    + DRAWER_ORIENTATION
    + "\n"
)
INBETWEEN_DRAWER_SYSTEM = DRAWER_SYSTEM + INBETWEEN_REASONING + "\n"


def plan_has_cells(plan: dict) -> bool:
    blob = json.dumps(plan)
    return "x" in blob and "y" in blob and any(f"x{i}y" in blob for i in range(1, 51))


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
    plo, phi = task.get("part_range", (6, 18))
    if not isinstance(parts, list) or not (int(plo) <= len(parts) <= int(phi)):
        raise ValueError(f"need {plo}–{phi} parts")
    for p in parts:
        pid = str(p.get("id") or "").strip().lower()
        how = str(p.get("how") or "").strip().lower()
        if how == "joint" or pid in {"person_hip", "person_neck", "hip", "neck"}:
            raise ValueError(f"part {pid or p.get('id')!r} is a joint, not a drawable stroke")
    for i, g in enumerate(gaps):
        n = int(g.get("n_inbetween", 0))
        if not 1 <= n <= 10:
            raise ValueError(f"gap {i} n_inbetween={n} not in 1–10")
        g["n_inbetween"] = n
        g["ease"] = str(g.get("ease") or "linear")
        if g["ease"] not in {"linear", "smooth", "ease_out"}:
            g["ease"] = "linear"
        keys[i].setdefault("name", f"k{i+1}")
        for leak in ("parts", "strokes", "path"):
            keys[i].pop(leak, None)
    keys[-1].setdefault("name", "end")
    for leak in ("parts", "strokes", "path"):
        keys[-1].pop(leak, None)
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
    people_scale = str(plan.get("people_scale") or "").strip()
    if not people_scale:
        raise ValueError("need people_scale in the plan")
    layout_notes = str(plan.get("layout_notes") or "").strip()
    if not layout_notes:
        raise ValueError("need layout_notes with placement and travel span")
    plan["parts"] = parts
    plan["keys"] = keys
    plan["gaps"] = gaps
    plan["n_frames"] = n_frames
    plan["action"] = action
    plan["people_scale"] = people_scale
    plan["layout_notes"] = layout_notes
    return plan


def mint_key_plan(
    task: dict,
    n_keys: int | None,
    pin_frames: int | None,
    suggested_frames: int,
    fewshot: bool = True,
) -> tuple[dict | None, str, str | None]:
    last_raw, last_err = "", None
    extra = ""
    for attempt in range(1, 4):
        raw = call_text(
            [
                {"role": "system", "content": KEY_PLAN_SYSTEM},
                {
                    "role": "user",
                    "content": key_plan_user(
                        task, n_keys, suggested_frames=suggested_frames, pin_frames=pin_frames, fewshot=fewshot
                    )
                    + extra,
                },
            ],
            max_tokens=32768,
            temperature=0.4,
            timeout=360,
            reasoning_effort=PLAN_REASONING_EFFORT,
        )
        last_raw = raw
        try:
            plan = validate_key_plan(parse_json_obj(raw), n_keys, task, pin_frames=pin_frames)
            plan["task_id"] = task["task_id"]
            return plan, raw, None
        except Exception as exc:
            last_err = f"attempt {attempt}: {type(exc).__name__}: {exc}"
            print(f"  plan {last_err}", flush=True)
            extra = (
                f"\n\nYour previous reply was not valid plan JSON ({exc}). "
                "Reply with one JSON object only. No analysis."
            )
            time.sleep(2)
    return None, last_raw, last_err


def generate_key_scene(
    user_content: str,
    *,
    system: str | None = None,
    reasoning_effort: str | None = None,
) -> tuple[Path2DScene, str]:
    last_raw, last_err = "", None
    prompt = user_content
    effort = reasoning_effort or DRAW_REASONING_EFFORT
    for _attempt in range(1, 3):
        raw = call_text(
            [
                {"role": "system", "content": system or DRAWER_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            max_tokens=65536,
            temperature=0.4,
            timeout=300,
            reasoning_effort=effort,
        )
        last_raw = raw
        try:
            scene = Path2DScene.from_dict(parse_json_obj(raw), prompt=user_content[:240])
            for stroke in scene.strokes:
                parse_path2d(stroke.path)
                sample_stroke(stroke)
            return scene, raw
        except Exception as exc:
            last_err = exc
            prompt = (
                "Repair the JSON so it is one valid Path2D scene "
                "(keys: prompt, strokes with id/path/description). Return JSON only.\n"
                f"{raw[:12000]}"
            )
            time.sleep(1)
    raise ValueError(f"Path2D key failed: {last_err}") from last_err


def generate_inbetween(
    prompt: str,
    plan: dict,
    anchor_scene: dict,
    dest: Path,
    *,
    canonical_ids: set[str],
    attempts: int = 2,
) -> tuple[dict, str, dict, int]:
    last_error: Exception | None = None
    last_raw = ""
    user_content = prompt
    dest.mkdir(parents=True, exist_ok=True)
    for attempt in range(1, attempts + 1):
        try:
            scene, last_raw = generate_key_scene(user_content, system=INBETWEEN_DRAWER_SYSTEM)
            value = pin_anchored_scene(scene.to_dict(), anchor_scene, plan)
            report = scene_contract_report(value, plan, canonical_ids=canonical_ids)
            if not report["ok"]:
                raise ValueError(
                    f"inbetween attempt {attempt} violates part-id contract: "
                    f"missing={report['missing_part_ids']} canonical_missing={report['canonical_missing']}"
                )
            (dest / f"attempt_{attempt:02d}.raw.txt").write_text(last_raw, encoding="utf-8")
            return value, last_raw, report, attempt
        except Exception as exc:
            last_error = exc
            (dest / f"attempt_{attempt:02d}.raw.txt").write_text(last_raw or str(exc), encoding="utf-8")
            user_content = (
                prompt
                + "\n\nThe previous attempt violated the animation identity contract. "
                + f"Repair it: {exc}. Reuse every exact part id; do not rename. Return one complete Path2D JSON."
            )
    raise ValueError(f"inbetween contract failed after {attempts} attempts: {last_error}") from last_error


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


def save_scene(scene: dict, dest: Path, *, width: int, height: int) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    obj = Path2DScene.from_dict(scene)
    (dest / "scene.json").write_text(obj.to_json(), encoding="utf-8")
    png = dest / "view.png"
    render_scene(obj, png, width=width, height=height)
    return png


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


def load_frame_scenes(out: Path, n_frames: int) -> dict[int, dict]:
    drawn: dict[int, dict] = {}
    for i in range(1, n_frames + 1):
        path = out / "frames" / f"f{i:02d}" / "scene.json"
        if path.exists():
            drawn[i] = json.loads(path.read_text(encoding="utf-8"))
    return drawn


def archive_frame_dir(dest: Path) -> Path | None:
    scene_path = dest / "scene.json"
    if not scene_path.exists():
        return None
    stamp = time.strftime("%Y%m%d_%H%M%S")
    hist = dest / "history" / stamp
    hist.mkdir(parents=True, exist_ok=True)
    for name in (
        "scene.json",
        "view.png",
        "raw.txt",
        "contract.json",
        "draw_prompt.txt",
        "redraw_prompt.txt",
    ):
        src = dest / name
        if src.exists():
            shutil.copy2(src, hist / name)
    return hist


def resolve_redraw_out(from_run: Path, out_arg: str | None) -> Path:
    if not out_arg:
        return from_run
    dest = Path(out_arg)
    if not dest.is_absolute():
        dest = HERE / dest
    if dest.resolve() == from_run.resolve():
        return from_run
    if dest.exists():
        raise SystemExit(f"--out already exists: {dest}")
    shutil.copytree(from_run, dest)
    print(f"  copied run {from_run} -> {dest}", flush=True)
    return dest


def rebuild_clip_previews(
    out: Path,
    timeline: list[dict],
    *,
    width: int,
    height: int,
    gif_ms: int,
) -> tuple[Path, Path]:
    pngs: list[Path] = []
    labels: list[str] = []
    for slot in timeline:
        i = int(slot["i"])
        dest = out / "frames" / f"f{i:02d}"
        scene_path = dest / "scene.json"
        if not scene_path.exists():
            raise SystemExit(f"missing {scene_path}; cannot rebuild clip")
        scene = json.loads(scene_path.read_text(encoding="utf-8"))
        png = save_scene(scene, dest, width=width, height=height)
        pngs.append(png)
        if slot.get("kind") == "key":
            labels.append(f"f{i}K:{slot.get('key_name')}"[:12])
        else:
            labels.append(f"f{i}")
    gif = out / "clip.gif"
    sheet = out / "contact_sheet.png"
    for path in (gif, sheet):
        if path.exists():
            path.unlink()
    write_gif(pngs, gif, duration_ms=gif_ms)
    write_contact_sheet(pngs, sheet, labels=labels)
    print(f"  rebuilt {gif} frames={len(pngs)} gif_ms={gif_ms}", flush=True)
    print(f"  rebuilt {sheet}", flush=True)
    return gif, sheet


def draw_inbetween_slot(
    plan: dict,
    slot: dict,
    prev: dict,
    nxt: dict,
    dest: Path,
    *,
    canonical_ids: set[str],
    anchor_scene: dict,
    n_frames: int,
    fix_note: str = "",
) -> tuple[dict, dict, str, int]:
    i = int(slot["i"])
    print(
        f"== oneshot inbetween frame {i}/{n_frames} from={i - 1} "
        f"to_key={slot.get('to_frame')} ({slot['to']}) ==",
        flush=True,
    )
    t1 = time.time()
    prompt = inbetween_oneshot_prompt(plan, slot, prev, nxt, fix_note=fix_note)
    prompt += (
        "\n\nCROSS-KEY IDENTITY CONTRACT:\n"
        f"Include every canonical stroke id exactly once: {sorted(canonical_ids or [])}.\n"
    )
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "draw_prompt.txt").write_text(prompt, encoding="utf-8")
    scene, raw, report, generation_attempt = generate_inbetween(
        prompt,
        plan,
        anchor_scene,
        dest,
        canonical_ids=canonical_ids or set(),
    )
    (dest / "raw.txt").write_text(raw, encoding="utf-8")
    (dest / "contract.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    label = f"f{i - 1}->k{slot.get('to_frame')}"
    print(
        f"  inbetween {round(time.time() - t1, 2)}s strokes={report['stroke_count']} "
        f"attempt={generation_attempt}",
        flush=True,
    )
    return scene, report, label, generation_attempt


def run_single_frame_redraw(
    *,
    out: Path,
    plan: dict,
    task: dict,
    key_scenes: dict,
    anchor_scene: dict,
    canonical_ids: set[str],
    frame_i: int,
    cascade: bool,
    fix_note: str,
    use_lerp: bool,
    width: int,
    height: int,
    gif_ms: int,
    t_wall: float,
    key_rows: list,
) -> None:
    timeline = expand_timeline(plan["keys"], plan["gaps"])
    want = frames_to_redraw(timeline, frame_i, cascade)
    n_frames = len(timeline)
    drawn = load_frame_scenes(out, n_frames)
    for slot in timeline:
        if slot.get("kind") == "key":
            i = int(slot["i"])
            if i not in drawn:
                drawn[i] = copy.deepcopy(key_scenes[slot["key_name"]])
    print(
        f"== redraw frames {want} cascade={cascade} note={bool(str(fix_note or '').strip())} "
        f"-> {out} ==",
        flush=True,
    )
    redraw_rows: list[dict] = []
    for i in want:
        slot = timeline[i - 1]
        dest = out / "frames" / f"f{i:02d}"
        hist = archive_frame_dir(dest)
        generation_attempt = 0
        if hist:
            print(f"  archived f{i:02d} -> {hist}", flush=True)
        if slot["kind"] == "key":
            name = str(slot["key_name"])
            key = slot["key"]
            key_i = next(
                idx for idx, item in enumerate(plan["keys"], 1) if str(item.get("name")) == name
            )
            n_keys = len(plan["keys"])
            prev_scene = None
            prev_name = ""
            if key_i > 1:
                prev_name = str(plan["keys"][key_i - 2]["name"])
                prev_scene = key_scenes[prev_name]
            prompt = key_draw_prompt(
                plan,
                key,
                key_i,
                n_keys,
                prev_scene=prev_scene,
                prev_name=prev_name,
                fix_note=fix_note if i == frame_i else fix_note,
            )
            key_dir = out / "keys" / f"{key_i:02d}_{name}"
            key_dir.mkdir(parents=True, exist_ok=True)
            (key_dir / "redraw_prompt.txt").write_text(prompt, encoding="utf-8")
            key_effort = FIRST_KEY_REASONING_EFFORT if key_i == 1 else KEY_REASONING_EFFORT
            print(f"== oneshot key redraw {key_i}/{n_keys} {name} effort={key_effort} ==", flush=True)
            t1 = time.time()
            last_error = ""
            accepted = None
            report = None
            for attempt in range(1, 3):
                try:
                    scene_obj, raw = generate_key_scene(
                        prompt if attempt == 1 else prompt + f"\nRepair previous: {last_error}",
                        reasoning_effort=key_effort,
                    )
                    attempt_dir = key_dir / f"redraw_{time.strftime('%Y%m%d_%H%M%S')}_{attempt:02d}"
                    attempt_dir.mkdir(parents=True, exist_ok=True)
                    (attempt_dir / "raw.txt").write_text(raw, encoding="utf-8")
                    value = scene_obj.to_dict()
                    if anchor_scene:
                        value = pin_anchored_scene(value, anchor_scene, plan)
                    report = scene_contract_report(value, plan, canonical_ids=canonical_ids)
                    if not report["ok"]:
                        raise ValueError(f"id contract {report}")
                    accepted = value
                    generation_attempt = attempt
                    break
                except Exception as exc:
                    last_error = str(exc)
                    print(f"  key {name} redraw attempt {attempt} rejected: {exc}", flush=True)
            if accepted is None or report is None:
                raise SystemExit(f"redraw key {name} failed: {last_error}")
            final_dir = key_dir / "final"
            save_scene(accepted, final_dir, width=width, height=height)
            (final_dir / "contract.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
            key_scenes[name] = accepted
            scene = accepted
            label = f"K:{name}"
            print(
                f"  key {name} {round(time.time() - t1, 2)}s redraw strokes={report['stroke_count']}",
                flush=True,
            )
        elif use_lerp:
            scene = interpolate_scene(
                key_scenes[slot["from"]],
                key_scenes[slot["to"]],
                float(slot["t"]),
                ease_kind=str(slot.get("ease") or "linear"),
                plan=plan,
            )
            scene = pin_anchored_scene(scene, anchor_scene, plan)
            report = scene_contract_report(scene, plan, canonical_ids=canonical_ids)
            label = f"i{slot['from'][:1]}-{slot['to'][:1]}"
        else:
            prev = drawn.get(i - 1)
            if prev is None:
                raise SystemExit(f"missing FROM frame {i - 1} under {out / 'frames'}")
            nxt = key_scenes[slot["to"]]
            note = str(fix_note or "").strip()
            if note and i != frame_i:
                note = note + " Continue from the corrected previous frame; keep the same height and build."
            scene, report, label, generation_attempt = draw_inbetween_slot(
                plan,
                slot,
                prev,
                nxt,
                dest,
                canonical_ids=canonical_ids or set(),
                anchor_scene=anchor_scene,
                n_frames=n_frames,
                fix_note=note,
            )
        png = save_scene(scene, dest, width=width, height=height)
        (dest / "contract.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        drawn[i] = copy.deepcopy(scene)
        redraw_rows.append(
            {
                "i": i,
                "kind": slot["kind"],
                "label": label,
                "strokes": report["stroke_count"],
                "attempt": generation_attempt,
                "archived": str(hist) if hist else None,
            }
        )
        print(f"  frame {i} {label} strokes={report['stroke_count']} png={png}", flush=True)

    gif, sheet = rebuild_clip_previews(
        out, timeline, width=width, height=height, gif_ms=gif_ms
    )
    prev_summary = {}
    summary_path = out / "summary.json"
    if summary_path.exists():
        try:
            prev_summary = json.loads(summary_path.read_text(encoding="utf-8"))
        except Exception:
            prev_summary = {}
    history = list(prev_summary.get("redraws") or [])
    rec = {
        "frame": frame_i,
        "frames": want,
        "cascade": cascade,
        "note": str(fix_note or "").strip(),
        "wall_seconds": round(time.time() - t_wall, 2),
        "rows": redraw_rows,
    }
    history.append(rec)
    summary = dict(prev_summary)
    summary.update(
        {
            "ok": True,
            "task_id": task.get("task_id") or plan.get("task_id"),
            "n_frames": n_frames,
            "gif": str(gif),
            "contact_sheet": str(sheet),
            "gif_ms": gif_ms,
            "key_rows": key_rows or prev_summary.get("key_rows"),
            "last_redraw": rec,
            "redraws": history,
            "wall_seconds": rec["wall_seconds"],
        }
    )
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"wrote {gif} and {sheet} redraw frames={want} ok=True wall_seconds={rec['wall_seconds']}",
        flush=True,
    )


def draw_key_incremental(
    prompt: str,
    out_dir: Path,
    *,
    max_rounds: int,
    width: int,
    height: int,
    initial_scene: dict | None = None,
):
    loop = Path2DIncrementalLoop(
        output_dir=out_dir,
        planner=GlmDsPlanner(),
        editor=GlmDsEditor(),
        max_rounds=max_rounds,
        max_patch_attempts=3,
        max_additions_per_patch=48,
        width=width,
        height=height,
    )
    return loop.run(prompt, initial_scene=initial_scene)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", default="bounce", choices=sorted(TASKS))
    ap.add_argument(
        "--model",
        default="gpt-5.6-sol",
        choices=("gpt-5.6-sol", "deepseek-v4-flash", "glm-5.3"),
        help="Planner/drawer backend. Default stays gpt-5.6-sol.",
    )
    ap.add_argument(
        "--plan-effort",
        default="high",
        choices=("low", "medium", "high"),
        help="Thinking strength for the plan rewrite.",
    )
    ap.add_argument(
        "--draw-effort",
        default="high",
        choices=("low", "medium", "high"),
        help="Thinking strength for inbetweens.",
    )
    ap.add_argument(
        "--key-effort",
        default=None,
        choices=("low", "medium", "high"),
        help="Thinking strength for keys after the first. Default: same as --draw-effort.",
    )
    ap.add_argument(
        "--first-key-effort",
        default="high",
        choices=("low", "medium", "high"),
        help="Thinking strength for the first key only (default high).",
    )
    ap.add_argument("--keys", type=int, default=3)
    ap.add_argument("--frames", type=int, default=None)
    ap.add_argument("--gif-ms", type=int, default=None)
    ap.add_argument("--width", type=int, default=512)
    ap.add_argument("--height", type=int, default=512)
    ap.add_argument("--out", default=None)
    ap.add_argument(
        "--no-fewshot",
        action="store_true",
        help="No task staging, no JSON schema example, no previous-key path dump",
    )
    ap.add_argument(
        "--lerp",
        action="store_true",
        help="Geometric lerp inbetweens instead of GLM one-shot (old 2D path)",
    )
    ap.add_argument("--max-rounds", type=int, default=4, help="incremental rounds per key (with --incremental-keys)")
    ap.add_argument("--key-attempts", type=int, default=2, help="full incremental retries if a key breaks the id contract")
    ap.add_argument(
        "--incremental-keys",
        action="store_true",
        help="Vision incremental keys instead of one-shot",
    )
    ap.add_argument(
        "--key-reflect",
        action="store_true",
        help="Look at each oneshot key, write caution rules, and redraw once (off by default)",
    )
    ap.add_argument(
        "--plan",
        default=None,
        help="Load an existing plan.json instead of minting a new plan",
    )
    ap.add_argument(
        "--plan-only",
        action="store_true",
        help="Stop after the action/plan rewrite; do not draw keys or inbetweens",
    )
    ap.add_argument(
        "--keys-only",
        action="store_true",
        help="Draw key poses then stop; skip inbetweens and the full clip",
    )
    ap.add_argument(
        "--from-run",
        default=None,
        help="Reuse an existing run: load plan+keys, draw inbetweens only",
    )
    ap.add_argument(
        "--redraw-frame",
        type=int,
        default=None,
        metavar="N",
        help="With --from-run: redraw only 1-based frame N, then rebuild clip.gif. Does not remint the plan.",
    )
    ap.add_argument(
        "--redraw-cascade",
        action="store_true",
        help="With --redraw-frame: also redraw later inbetweens in the same gap (until the next key).",
    )
    ap.add_argument(
        "--redraw-note",
        default="",
        help="Extra hard instruction for --redraw-frame, e.g. 'cat is flattened; keep FROM height'.",
    )
    ap.add_argument(
        "--rebuild-clip",
        action="store_true",
        help="With --from-run: re-render every frame PNG from scene.json and rewrite clip.gif + contact_sheet.png. No model calls.",
    )
    args = ap.parse_args()
    global TEXT_MODEL, PLAN_REASONING_EFFORT, DRAW_REASONING_EFFORT, KEY_REASONING_EFFORT, FIRST_KEY_REASONING_EFFORT
    TEXT_MODEL = str(args.model)
    PLAN_REASONING_EFFORT = str(args.plan_effort)
    DRAW_REASONING_EFFORT = str(args.draw_effort)
    KEY_REASONING_EFFORT = str(args.key_effort or args.draw_effort)
    FIRST_KEY_REASONING_EFFORT = str(args.first_key_effort)
    if args.redraw_frame is not None and not args.from_run:
        raise SystemExit("--redraw-frame requires --from-run pointing at an existing clip folder")
    if args.rebuild_clip and not args.from_run and args.redraw_frame is None:
        raise SystemExit("--rebuild-clip requires --from-run pointing at an existing clip folder")
    t_wall = time.time()
    task = TASKS[args.task]
    suggested_frames = int(task.get("target_frames") or 12)
    pin_frames = int(args.frames) if args.frames is not None else None
    n_keys = int(args.keys) if args.keys is not None else None
    gif_ms = int(args.gif_ms if args.gif_ms is not None else task.get("gif_ms", 80))
    stamp = time.strftime("%Y%m%d_%H%M%S")
    use_oneshot_keys = not bool(args.incremental_keys)
    use_key_reflect = bool(use_oneshot_keys) and bool(args.key_reflect)
    key_scenes: dict[str, dict] = {}
    key_rows: list[dict] = []
    canonical_ids: set[str] | None = None
    anchor_scene = None

    if args.from_run:
        out = Path(args.from_run)
        if not out.is_absolute():
            out = HERE / out
        plan_path = out / "plan.json"
        if not plan_path.exists():
            raise SystemExit(f"--from-run missing {plan_path}")
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        task_id = str(plan.get("task_id") or task["task_id"])
        for spec in TASKS.values():
            if spec.get("task_id") == task_id:
                task = spec
                gif_ms = int(args.gif_ms if args.gif_ms is not None else task.get("gif_ms", 80))
                break
        n_keys = len(plan.get("keys") or [])
        key_scenes, anchor_scene, canonical_ids = load_run_keys(out, plan)
        key_rows = [{"name": k.get("name"), "ok": True, "loaded": True} for k in plan["keys"]]
        print(
            f"== from-run {out} model={text_model_name()} "
            f"thinking={'on' if thinking_enabled() else 'off'} "
            f"plan_effort={PLAN_REASONING_EFFORT} draw_effort={DRAW_REASONING_EFFORT} "
            f"first_key_effort={FIRST_KEY_REASONING_EFFORT} key_effort={KEY_REASONING_EFFORT} "
            f"keys={[k.get('name') for k in plan['keys']]} frames={plan.get('n_frames')} "
            f"inbetween={'lerp' if args.lerp else 'oneshot'} ==",
            flush=True,
        )
        print(f"    {plan.get('action')}", flush=True)
    else:
        out = Path(args.out) if args.out else HERE / "outputs" / f"{task['task_id']}_{stamp}"
        if not out.is_absolute():
            out = HERE / out
        out.mkdir(parents=True, exist_ok=True)
        print(
            f"== path2d key plan {task['task_id']} model={text_model_name()} "
            f"thinking={'on' if thinking_enabled() else 'off'} "
            f"plan_effort={PLAN_REASONING_EFFORT} draw_effort={DRAW_REASONING_EFFORT} "
            f"first_key_effort={FIRST_KEY_REASONING_EFFORT} key_effort={KEY_REASONING_EFFORT} n_keys={n_keys} fewshot={not args.no_fewshot} "
            f"keys={'plan-only' if args.plan_only else ('oneshot' if use_oneshot_keys else f'incremental/{args.max_rounds}')} "
            f"reflect={'on' if use_key_reflect else 'off'} "
            f"inbetween={'skip' if (args.plan_only or args.keys_only) else ('lerp' if args.lerp else 'oneshot')} -> {out} ==",
            flush=True,
        )
        t0 = time.time()
        if args.plan:
            plan_path = Path(args.plan)
            if not plan_path.is_absolute():
                plan_path = HERE / plan_path
            plan_raw = plan_path.read_text(encoding="utf-8")
            try:
                plan = validate_key_plan(parse_json_obj(plan_raw), n_keys, task, pin_frames=pin_frames)
                plan["task_id"] = task["task_id"]
                plan_err = None
            except Exception as exc:
                plan, plan_err = None, f"{type(exc).__name__}: {exc}"
            print(f"  loaded plan {plan_path}", flush=True)
        else:
            plan, plan_raw, plan_err = mint_key_plan(
                task, n_keys, pin_frames, suggested_frames, fewshot=not args.no_fewshot
            )
        (out / "plan.raw.txt").write_text(plan_raw, encoding="utf-8")
        if plan is None:
            (out / "summary.json").write_text(json.dumps({"ok": False, "plan_error": plan_err}, indent=2), encoding="utf-8")
            raise SystemExit(1)
        (out / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
        (out / "action.txt").write_text(plan["action"] + "\n", encoding="utf-8")
        n_keys = len(plan["keys"])
        print(
            f"  plan {round(time.time()-t0, 2)}s {n_keys} keys, {plan['n_frames']} frames "
            f"{[k.get('name') for k in plan['keys']]}",
            flush=True,
        )
        print(f"    {plan['action']}", flush=True)
        layout = str(plan.get("layout_notes") or "").strip()
        if layout:
            print(f"    layout: {layout}", flush=True)
        if args.plan_only:
            summary = {
                "ok": True,
                "pipeline": "plan_only",
                "models": {"plan": text_model_name()},
                "task_id": task["task_id"],
                "n_keys": n_keys,
                "n_frames": plan.get("n_frames"),
                "action": plan.get("action"),
                "people_scale": plan.get("people_scale"),
                "layout_notes": plan.get("layout_notes"),
                "parts": plan.get("parts"),
                "keys": plan.get("keys"),
                "gaps": plan.get("gaps"),
                "wall_seconds": round(time.time() - t_wall, 2),
            }
            (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"wrote {out / 'action.txt'} plan-only wall_seconds={summary['wall_seconds']}", flush=True)
            return

        prev_scene = None
        prev_name = ""
        for i, key in enumerate(plan["keys"], 1):
            name = str(key["name"])
            key_dir = out / "keys" / f"{i:02d}_{name}"
            prompt = key_draw_prompt(
                plan, key, i, n_keys, prev_scene=prev_scene, prev_name=prev_name
            )
            key_dir.mkdir(parents=True, exist_ok=True)
            (key_dir / "draw_prompt.txt").write_text(prompt, encoding="utf-8")
            key_effort = FIRST_KEY_REASONING_EFFORT if i == 1 else KEY_REASONING_EFFORT
            print(
                f"== {'oneshot' if use_oneshot_keys else 'incremental'} key {i}/{n_keys} {name} "
                f"effort={key_effort} ==",
                flush=True,
            )
            t1 = time.time()
            last_error = ""
            accepted = None
            contract = None
            result_status = "oneshot"
            accepted_attempt = 0
            n_attempts = 2 if use_oneshot_keys else max(1, int(args.key_attempts))
            for attempt in range(1, n_attempts + 1):
                try:
                    if use_oneshot_keys:
                        scene_obj, raw = generate_key_scene(
                            prompt if attempt == 1 else prompt + f"\nRepair previous: {last_error}",
                            reasoning_effort=key_effort,
                        )
                        value = scene_obj.to_dict()
                        attempt_dir = key_dir / f"attempt_{attempt:02d}"
                        attempt_dir.mkdir(parents=True, exist_ok=True)
                        (attempt_dir / "raw.txt").write_text(raw, encoding="utf-8")
                    else:
                        result = draw_key_incremental(
                            prompt,
                            key_dir / f"attempt_{attempt:02d}",
                            max_rounds=args.max_rounds,
                            width=args.width,
                            height=args.height,
                            initial_scene=prev_scene,
                        )
                        scene_path = key_dir / f"attempt_{attempt:02d}" / "final" / "scene.json"
                        if not scene_path.exists() or result.status == "failed":
                            raise ValueError(
                                f"incremental status={result.status}, scene_exists={scene_path.exists()}"
                            )
                        value = json.loads(scene_path.read_text(encoding="utf-8"))
                        result_status = result.status
                    if anchor_scene:
                        value = pin_anchored_scene(value, anchor_scene, plan)
                    contract = scene_contract_report(value, plan, canonical_ids=canonical_ids)
                    if not contract["ok"]:
                        raise ValueError(f"id contract {contract}")
                    accepted = value
                    accepted_attempt = attempt
                    break
                except Exception as exc:
                    last_error = str(exc)
                    print(f"  key {name} attempt {attempt} rejected: {exc}", flush=True)
                    time.sleep(1)
            if accepted is None:
                (out / "summary.json").write_text(
                    json.dumps({"ok": False, "key_error": name, "error": last_error}, indent=2), encoding="utf-8"
                )
                raise SystemExit(1)
            reflect_info: dict = {"enabled": use_key_reflect}
            if use_key_reflect:
                draft_dir = key_dir / "draft"
                save_scene(accepted, draft_dir, width=args.width, height=args.height)
                print(f"  key {name} look→experience", flush=True)
                try:
                    experience, exp_raw = review_key_experience(
                        draft_dir / "view.png",
                        plan=plan,
                        key=key,
                        key_i=i,
                        n_keys=n_keys,
                    )
                    (key_dir / "experience.json").write_text(
                        json.dumps(experience, ensure_ascii=False, indent=2), encoding="utf-8"
                    )
                    (key_dir / "experience.raw.txt").write_text(exp_raw, encoding="utf-8")
                    reflect_info["experience"] = experience
                    if not should_redraw(experience):
                        result_status = "oneshot_ok"
                        reflect_info["skipped_redraw"] = True
                        print(f"  key {name} experience ok; keep draft", flush=True)
                    else:
                        redraw_prompt = key_draw_prompt(
                            plan,
                            key,
                            i,
                            n_keys,
                            prev_scene=None,
                            prev_name="",
                            experience=experience,
                        )
                        (key_dir / "redraw_prompt.txt").write_text(redraw_prompt, encoding="utf-8")
                        print(f"  key {name} redraw from experience", flush=True)
                        scene_obj, raw = generate_key_scene(redraw_prompt, reasoning_effort=key_effort)
                        redraw_value = scene_obj.to_dict()
                        if anchor_scene:
                            redraw_value = pin_anchored_scene(redraw_value, anchor_scene, plan)
                        redraw_contract = scene_contract_report(
                            redraw_value, plan, canonical_ids=canonical_ids
                        )
                        if not redraw_contract["ok"]:
                            raise ValueError(f"redraw id contract {redraw_contract}")
                        redraw_dir = key_dir / "redraw"
                        redraw_dir.mkdir(parents=True, exist_ok=True)
                        (redraw_dir / "raw.txt").write_text(raw, encoding="utf-8")
                        save_scene(redraw_value, redraw_dir, width=args.width, height=args.height)
                        winner, reason, select_raw = select_key_winner(
                            draft_dir / "view.png",
                            redraw_dir / "view.png",
                            plan=plan,
                            key=key,
                        )
                        (key_dir / "select.json").write_text(
                            json.dumps({"winner": winner, "reason": reason}, ensure_ascii=False, indent=2),
                            encoding="utf-8",
                        )
                        if select_raw:
                            (key_dir / "select.raw.txt").write_text(select_raw, encoding="utf-8")
                        reflect_info["winner"] = winner
                        reflect_info["select_reason"] = reason
                        if winner == "redraw":
                            accepted = redraw_value
                            contract = redraw_contract
                            result_status = "oneshot_redraw"
                        else:
                            result_status = "oneshot_draft"
                        print(f"  key {name} select={winner}", flush=True)
                except Exception as exc:
                    reflect_info["error"] = str(exc)
                    result_status = "oneshot_reflect_failed"
                    print(f"  key {name} reflect failed, keep draft: {exc}", flush=True)
            final_dir = key_dir / "final"
            save_scene(accepted, final_dir, width=args.width, height=args.height)
            (final_dir / "contract.json").write_text(json.dumps(contract, indent=2), encoding="utf-8")
            key_scenes[name] = accepted
            prev_scene = copy.deepcopy(accepted)
            prev_name = name
            if anchor_scene is None:
                anchor_scene = copy.deepcopy(accepted)
                canonical_ids = {str(s.get("id") or "") for s in accepted.get("strokes") or [] if s.get("id")}
            key_rows.append(
                {
                    "name": name,
                    "ok": True,
                    "status": result_status,
                    "attempt": accepted_attempt,
                    "seconds": round(time.time() - t1, 2),
                    "contract": contract,
                    "reflect": reflect_info,
                }
            )
            print(
                f"  key {name} {key_rows[-1]['seconds']}s status={result_status} "
                f"strokes={contract['stroke_count']}",
                flush=True,
            )

    if args.redraw_frame is not None:
        if args.plan_only or args.keys_only:
            raise SystemExit("--redraw-frame cannot combine with --plan-only or --keys-only")
        out = resolve_redraw_out(out, args.out)
        key_scenes, anchor_scene, canonical_ids = load_run_keys(out, plan)
        run_single_frame_redraw(
            out=out,
            plan=plan,
            task=task,
            key_scenes=key_scenes,
            anchor_scene=anchor_scene,
            canonical_ids=canonical_ids or set(),
            frame_i=int(args.redraw_frame),
            cascade=bool(args.redraw_cascade),
            fix_note=str(args.redraw_note or ""),
            use_lerp=bool(args.lerp),
            width=args.width,
            height=args.height,
            gif_ms=gif_ms,
            t_wall=t_wall,
            key_rows=key_rows,
        )
        return

    if args.rebuild_clip:
        if args.plan_only or args.keys_only:
            raise SystemExit("--rebuild-clip cannot combine with --plan-only or --keys-only")
        out = resolve_redraw_out(out, args.out)
        timeline = expand_timeline(plan["keys"], plan["gaps"])
        gif, sheet = rebuild_clip_previews(
            out, timeline, width=args.width, height=args.height, gif_ms=gif_ms
        )
        summary_path = out / "summary.json"
        summary = {}
        if summary_path.exists():
            try:
                summary = json.loads(summary_path.read_text(encoding="utf-8"))
            except Exception:
                summary = {}
        summary.update(
            {
                "ok": True,
                "rebuild_clip": True,
                "n_frames": len(timeline),
                "gif": str(gif),
                "contact_sheet": str(sheet),
                "gif_ms": gif_ms,
                "wall_seconds": round(time.time() - t_wall, 2),
            }
        )
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(
            f"wrote {gif} and {sheet} rebuild-clip n_frames={len(timeline)} "
            f"ok=True wall_seconds={summary['wall_seconds']}",
            flush=True,
        )
        return

    if args.keys_only and not args.from_run:
        pngs = []
        labels = []
        for i, key in enumerate(plan["keys"], 1):
            name = str(key["name"])
            pngs.append(out / "keys" / f"{i:02d}_{name}" / "final" / "view.png")
            labels.append(f"K:{name}"[:12])
        gif = out / "clip.gif"
        sheet = out / "contact_sheet.png"
        key_gif_ms = max(gif_ms, 400)
        write_gif(pngs, gif, duration_ms=key_gif_ms)
        write_contact_sheet(pngs, sheet, labels=labels)
        summary = {
            "ok": True,
            "pipeline": "plan_oneshot_keys_only",
            "keys_only": True,
            "models": {"plan": text_model_name(), "keys": text_model_name()},
            "thinking": thinking_enabled(),
            "plan_effort": PLAN_REASONING_EFFORT,
            "draw_effort": DRAW_REASONING_EFFORT,
            "first_key_effort": FIRST_KEY_REASONING_EFFORT,
            "key_effort": KEY_REASONING_EFFORT,
            "task_id": task["task_id"],
            "n_keys": n_keys,
            "n_frames": n_keys,
            "gif_ms": key_gif_ms,
            "action": plan.get("action"),
            "people_scale": plan.get("people_scale"),
            "layout_notes": plan.get("layout_notes"),
            "gaps": plan["gaps"],
            "key_rows": key_rows,
            "gif": str(gif),
            "contact_sheet": str(sheet),
            "wall_seconds": round(time.time() - t_wall, 2),
        }
        (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"wrote {gif} keys_only n_keys={n_keys} ok=True wall_seconds={summary['wall_seconds']}", flush=True)
        return

    timeline = expand_timeline(plan["keys"], plan["gaps"])
    pngs = []
    labels = []
    frame_rows = []
    use_lerp = bool(args.lerp)
    drawn: dict[int, dict] = {}
    n_frames = len(timeline)
    for slot in timeline:
        i = slot["i"]
        dest = out / "frames" / f"f{i:02d}"
        generation_attempt = 0
        if slot["kind"] == "key":
            scene = key_scenes[slot["key_name"]]
            label = f"K:{slot['key_name']}"
            report = scene_contract_report(scene, plan, canonical_ids=canonical_ids)
        elif use_lerp:
            scene = interpolate_scene(
                key_scenes[slot["from"]],
                key_scenes[slot["to"]],
                float(slot["t"]),
                ease_kind=str(slot.get("ease") or "linear"),
                plan=plan,
            )
            scene = pin_anchored_scene(scene, anchor_scene, plan)
            label = f"i{slot['from'][:1]}-{slot['to'][:1]}"
            report = scene_contract_report(scene, plan, canonical_ids=canonical_ids)
        else:
            prev = drawn.get(i - 1) or key_scenes[slot["from"]]
            nxt = key_scenes[slot["to"]]
            scene, report, label, generation_attempt = draw_inbetween_slot(
                plan,
                slot,
                prev,
                nxt,
                dest,
                canonical_ids=canonical_ids or set(),
                anchor_scene=anchor_scene,
                n_frames=n_frames,
            )
        png = save_scene(scene, dest, width=args.width, height=args.height)
        drawn[i] = copy.deepcopy(scene)
        pngs.append(png)
        labels.append(label[:12])
        frame_rows.append(
            {
                "i": i,
                "kind": slot["kind"],
                "label": label,
                "strokes": report["stroke_count"],
                "attempt": generation_attempt,
                "from_frame": slot.get("from_frame"),
                "to_frame": slot.get("to_frame"),
                "contract": report,
            }
        )
        print(f"  frame {i} {label} strokes={report['stroke_count']}", flush=True)

    gif = out / "clip.gif"
    sheet = out / "contact_sheet.png"
    write_gif(pngs, gif, duration_ms=gif_ms)
    write_contact_sheet(pngs, sheet, labels=labels)
    summary = {
        "ok": True,
        "pipeline": (
            "plan_keys_path2d_lerp"
            if args.lerp
            else (
                "plan_oneshot_keys_reflect_inbetweens"
                if use_oneshot_keys and use_key_reflect
                else "plan_oneshot_keys_oneshot_inbetweens"
                if use_oneshot_keys
                else "plan_keys_incremental_inbetweens_oneshot"
            )
        ),
        "models": {
            "plan_and_oneshot_inbetween": text_model_name(),
            "keys": text_model_name(),
            "key_experience_select": text_model_name() if use_key_reflect else None,
        },
        "key_reflect": use_key_reflect,
        "thinking": thinking_enabled(),
        "plan_effort": PLAN_REASONING_EFFORT,
        "draw_effort": DRAW_REASONING_EFFORT,
        "first_key_effort": FIRST_KEY_REASONING_EFFORT,
        "key_effort": KEY_REASONING_EFFORT,
        "from_run": bool(args.from_run),
        "fewshot": not args.no_fewshot,
        "task_id": task["task_id"],
        "n_keys": n_keys,
        "n_frames": len(timeline),
        "gif_ms": gif_ms,
        "action": plan.get("action"),
        "people_scale": plan.get("people_scale"),
        "layout_notes": plan.get("layout_notes"),
        "gaps": plan["gaps"],
        "key_rows": key_rows,
        "frame_rows": frame_rows,
        "gif": str(gif),
        "contact_sheet": str(sheet),
        "wall_seconds": round(time.time() - t_wall, 2),
    }
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {gif} frames={len(timeline)} ok=True wall_seconds={summary['wall_seconds']}", flush=True)


if __name__ == "__main__":
    main()
