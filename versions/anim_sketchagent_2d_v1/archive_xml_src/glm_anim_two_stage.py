#!/usr/bin/env python3
"""GLM-5.3 two-stage SketchAgent walk cycle: one plan call, then one draw call per frame."""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from anim_prompts import (
    ANIM_DRAW_SYSTEM,
    ANIM_DRAW_SYSTEM_ANIMAL,
    ANIM_PLAN_SYSTEM,
    ANIM_PLAN_SYSTEM_ANIMAL,
    MAX_FRAMES,
    MAX_PARTS,
    MIN_FRAMES,
    MIN_PARTS,
    TASKS,
    anim_draw_user,
    anim_plan_text,
    anim_plan_user,
)
from mint_plans import plan_has_cells
from sa_render import convert_completion, extract_strokes_xml
from terra_client import call_glm, parse_json_obj


def _parts(plan: dict) -> list:
    return plan.get("parts") or plan.get("strokes") or []


def _part_range(task: dict) -> tuple[int, int]:
    lo, hi = task.get("part_range", (MIN_PARTS, MAX_PARTS))
    return int(lo), int(hi)


def validate_plan(plan: dict, n_frames: int, task: dict) -> dict:
    if plan_has_cells(plan):
        raise ValueError("plan contains grid cells")
    frames = plan.get("frames")
    if not isinstance(frames, list) or len(frames) != n_frames:
        raise ValueError(f"need exactly {n_frames} frames, got {len(frames) if isinstance(frames, list) else None}")
    parts = _parts(plan)
    lo, hi = _part_range(task)
    if not isinstance(parts, list) or not (lo <= len(parts) <= hi):
        raise ValueError(f"need {lo}–{hi} parts, got {len(parts) if isinstance(parts, list) else None}")
    plan["n_frames"] = n_frames
    plan["parts"] = parts
    return plan


def mint_anim_plan(task: dict, n_frames: int, attempts: int = 3) -> tuple[dict | None, str, str | None]:
    last_raw, last_err = "", None
    for attempt in range(1, attempts + 1):
        raw = call_glm(
            [
                {
                    "role": "system",
                    "content": ANIM_PLAN_SYSTEM_ANIMAL
                    if task.get("kind") == "animal"
                    else ANIM_PLAN_SYSTEM,
                },
                {"role": "user", "content": anim_plan_user(task, n_frames)},
            ],
            max_tokens=4096,
            temperature=0.4,
            reasoning_effort="low",
            timeout=180,
        )
        last_raw = raw
        try:
            plan = validate_plan(parse_json_obj(raw), n_frames, task)
            plan["task_id"] = task["task_id"]
            plan["planner"] = "glm-5.3-anim-two-stage"
            return plan, raw, None
        except Exception as e:
            last_err = f"attempt {attempt}: {type(e).__name__}: {e}"
            print(f"  plan {last_err}", flush=True)
            time.sleep(2)
    return None, last_raw, last_err


def draw_frame(
    task: dict,
    plan: dict,
    frame_i: int,
    prev_xml: str | None,
    png_path: Path,
    attempts: int = 3,
) -> tuple[dict, str]:
    n_frames = int(plan["n_frames"])
    layout = anim_plan_text(plan, frame_i)
    last_raw, last_rec = "", {"valid": False, "error": "no draw"}
    for attempt in range(1, attempts + 1):
        raw = call_glm(
            [
                {
                    "role": "system",
                    "content": ANIM_DRAW_SYSTEM_ANIMAL
                    if task.get("kind") == "animal"
                    else ANIM_DRAW_SYSTEM,
                },
                {
                    "role": "user",
                    "content": anim_draw_user(task, layout, frame_i, n_frames, prev_xml),
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
        lo, hi = _part_range(task)
        intact_ok = rec.get("intact") or task.get("allow_detached_prop")
        if rec.get("valid") and intact_ok and lo - 2 <= n <= hi + 1:
            rec["attempt"] = attempt
            return rec, raw
        why = rec.get("error") or f"valid={rec.get('valid')} intact={rec.get('intact')} strokes={n}"
        print(f"  frame {frame_i} attempt {attempt} rejected: {why}", flush=True)
        time.sleep(1)
    last_rec["attempt"] = attempts
    return last_rec, last_raw


def overlay_ground(png_path: Path) -> None:
    img = Image.open(png_path).convert("RGB")
    draw = ImageDraw.Draw(img)
    y = int(img.height * 0.82)
    draw.line([(int(img.width * 0.06), y), (int(img.width * 0.94), y)], fill=(180, 180, 180), width=3)
    img.save(png_path)


def label_frame(img: Image.Image, text: str) -> Image.Image:
    canvas = img.convert("RGB")
    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 22)
    except OSError:
        font = ImageFont.load_default()
    draw.rectangle([(8, 8), (140, 40)], fill="white")
    draw.text((14, 12), text, fill="black", font=font)
    return canvas


def write_contact_sheet(paths: list[Path], out: Path, cols: int | None = None, labels: list[str] | None = None) -> None:
    labels = labels or [f"f{i+1}" for i in range(len(paths))]
    images = [label_frame(Image.open(p), labels[i] if i < len(labels) else f"f{i+1}") for i, p in enumerate(paths)]
    w, h = images[0].size
    gap = 8
    n = len(images)
    cols = cols or (6 if n > 8 else n)
    rows = (n + cols - 1) // cols
    sheet = Image.new("RGB", (w * cols + gap * (cols - 1), h * rows + gap * (rows - 1)), "white")
    for i, im in enumerate(images):
        r, c = divmod(i, cols)
        sheet.paste(im, (c * (w + gap), r * (h + gap)))
    sheet.save(out)


def write_gif(paths: list[Path], out: Path, duration_ms: int = 280) -> None:
    frames = [label_frame(Image.open(p), f"f{i+1}") for i, p in enumerate(paths)]
    frames[0].save(
        out,
        save_all=True,
        append_images=frames[1:],
        duration=duration_ms,
        loop=0,
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", default="serve", choices=sorted(TASKS))
    ap.add_argument("--frames", type=int, default=None)
    ap.add_argument("--gif-ms", type=int, default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    task = TASKS[args.task]
    n_frames = int(args.frames if args.frames is not None else task.get("target_frames") or 12)
    if not (MIN_FRAMES <= n_frames <= MAX_FRAMES):
        raise SystemExit(f"--frames must be {MIN_FRAMES}–{MAX_FRAMES}")
    gif_ms = int(args.gif_ms if args.gif_ms is not None else task.get("gif_ms", 220))

    stamp = time.strftime("%Y%m%d_%H%M%S")
    out = Path(args.out) if args.out else HERE / "outputs" / f"glm53_naive_{task['task_id']}_{stamp}"
    frames_dir = out / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    print(f"== plan {task['task_id']} n={n_frames} -> {out} ==", flush=True)
    t0 = time.time()
    plan, plan_raw, plan_err = mint_anim_plan(task, n_frames)
    plan_s = round(time.time() - t0, 2)
    (out / "plan.raw.txt").write_text(plan_raw, encoding="utf-8")
    if plan is not None:
        (out / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  plan {plan_s}s ok={plan is not None} {plan_err or ''}", flush=True)
    if plan is None:
        (out / "summary.json").write_text(
            json.dumps({"ok": False, "plan_error": plan_err}, indent=2),
            encoding="utf-8",
        )
        raise SystemExit(1)

    rows = []
    prev_xml = None
    pngs: list[Path] = []
    for i in range(1, n_frames + 1):
        png = frames_dir / f"f{i:02d}.png"
        print(f"== draw frame {i}/{n_frames} ==", flush=True)
        t1 = time.time()
        rec, raw = draw_frame(task, plan, i, prev_xml, png)
        draw_s = round(time.time() - t1, 2)
        (out / f"f{i:02d}.raw.txt").write_text(raw, encoding="utf-8")
        xml = extract_strokes_xml(raw)
        if xml:
            (out / f"f{i:02d}.xml.txt").write_text(xml, encoding="utf-8")
        if rec.get("valid"):
            overlay_ground(png)
            pngs.append(png)
            prev_xml = xml
        print(
            f"  draw {draw_s}s valid={rec.get('valid')} intact={rec.get('intact')} "
            f"strokes={rec.get('n_strokes')} attempt={rec.get('attempt')}",
            flush=True,
        )
        if rec.get("error"):
            print(f"  render: {rec['error']}", flush=True)
        rows.append(
            {
                "frame": i,
                "draw_seconds": draw_s,
                "valid": rec.get("valid"),
                "intact": rec.get("intact"),
                "n_strokes": rec.get("n_strokes"),
                "attempt": rec.get("attempt"),
                "error": rec.get("error"),
            }
        )

    gif = out / "clip.gif"
    sheet = out / "contact_sheet.png"
    if pngs:
        write_gif(pngs, gif, duration_ms=gif_ms)
        write_contact_sheet(pngs, sheet)
        print(f"wrote {gif} and {sheet} gif_ms={gif_ms}", flush=True)

    summary = {
        "model": "glm-5.3",
        "pipeline": "naive_full_draw_every_frame",
        "task_id": task["task_id"],
        "n_frames": n_frames,
        "gif_ms": gif_ms,
        "plan_seconds": plan_s,
        "plan_n_parts": len(_parts(plan)),
        "ok": all(r.get("valid") for r in rows) and len(pngs) == n_frames,
        "rows": rows,
        "gif": str(gif) if pngs else None,
        "contact_sheet": str(sheet) if pngs else None,
    }
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {out / 'summary.json'} ok={summary['ok']}", flush=True)


if __name__ == "__main__":
    main()
