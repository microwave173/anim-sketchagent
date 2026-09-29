"""Render completed ablation responses while recording, rather than rejecting, bounds overflow."""
from __future__ import annotations

import gzip
import json
import math
from pathlib import Path
import sys
import time

PROJECT = Path("/root/autodl-tmp/anim-sketchagent")
sys.path.insert(0, str(PROJECT / "light_agent"))

from provider import json_object
import scene
from path2d.parser import parse_path2d
from path2d.schema import Path2DScene
from render import export
from scene import SVG_STROKE, SVG_STROKE_WIDTH, public_frames

ROOT = PROJECT / "outputs/storyboard_naive_ablation_60f"
PROMPT = ("Create a short silent cartoon in an exaggerated slapstick style: a cat sets a clever trap "
          "for a mouse, but the mouse outsmarts the cat and the trap backfires. Make the setup and payoff "
          "visually clear. No captions.")


def write(path: Path, value) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def decode(out: Path) -> tuple[dict[int, dict], list[dict]]:
    raw = gzip.open(out / "one_shot_response.txt.gz", "rt", encoding="utf-8").read()
    value = json_object(raw)
    if [frame.get("i") for frame in value.get("frames", [])] != list(range(1, 61)):
        raise ValueError("Expected exactly frames 1..60")
    result = {}
    overflow = []
    for frame in value["frames"]:
        strokes = []
        for stroke in frame.get("strokes", []):
            item = {"id": stroke.get("id"), "path": stroke.get("d"),
                    "description": stroke.get("description")}
            if not all(isinstance(field, str) and field.strip() for field in item.values()):
                raise ValueError(f"Frame {frame['i']} has invalid stroke fields")
            commands = parse_path2d(item["path"])
            maximum = max(abs(number) for command in commands for number in command.values)
            if not math.isfinite(maximum):
                raise ValueError(f"Non-finite coordinates on {item['id']}")
            if maximum > 1:
                overflow.append({"frame": frame["i"], "id": item["id"], "max_abs_coordinate": maximum})
            item.update(stroke=SVG_STROKE, stroke_width=SVG_STROKE_WIDTH, opacity=1.0)
            strokes.append(item)
        parsed = Path2DScene.from_dict({"strokes": strokes}, prompt=PROMPT)
        result[frame["i"]] = {"i": frame["i"], "strokes": parsed.to_dict()["strokes"]}
    return result, overflow


def render_one(name: str) -> dict:
    out = ROOT / name
    started = time.perf_counter()
    frames, overflow = decode(out)
    animation = {
        "dimension": 2,
        "frame_ms": 120,
        "generation_protocol": "naive_one_shot_v2_shared_drawer",
        "conditioning": "storyboard" if name == "storyboard_naive" else "original_prompt_only",
        "validation": "finite SVG coordinates; out-of-viewBox coordinates recorded and naturally clipped",
        "bounds_overflow": overflow,
        "frames": public_frames(frames, 2),
        "geometry_format": "standard_svg_path_data",
        "svg_coordinate_system": "viewBox coordinates centered on [-1,1]; geometry outside the viewBox is clipped",
        "svg_style": {"fill": "none", "stroke": SVG_STROKE,
                      "stroke_width": "fixed by presentation.json",
                      "stroke_linecap": "round", "stroke_linejoin": "round"},
    }
    write(out / "animation.json", animation)
    export(frames, out, 2, 120, 640, PROMPT)
    summary = {
        "ok": True,
        "n_frames": len(frames),
        "overflow_strokes": len(overflow),
        "max_abs_coordinate": max((item["max_abs_coordinate"] for item in overflow), default=1.0),
        "overflow": overflow,
        "render_seconds": round(time.perf_counter() - started, 3),
    }
    write(out / "permissive_render.json", summary)
    return summary


def main() -> None:
    summary = {name: render_one(name) for name in ("ordinary_naive", "storyboard_naive")}
    write(ROOT / "permissive_render_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
