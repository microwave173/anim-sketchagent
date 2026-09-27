"""Reuse the existing geometry protocol without importing legacy agents."""
from __future__ import annotations

import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
for dim in (2, 3):
    sys.path.insert(0, str(ROOT / f"versions/path{dim}d_v1"))

from path2d.parser import parse_path2d
from path2d.schema import Path2DScene
from path3d.parser import parse_path3d
from path3d.schema import Path3DScene


def protocol(dim: int) -> str:
    syntax = ("M x y; L x y; Q cx cy x y; C c1x c1y c2x c2y x y; Z. +x right, +y up."
              if dim == 2 else
              "M x y z; L x y z; Q3 cx cy cz x y z; C3 c1x c1y c1z c2x c2y c2z x y z; Z. +x right, +y depth, +z up. Use real depth, not flat 2D geometry.")
    return (f"Path{dim}D protocol: {syntax} All coordinates including controls are in [-1,1]. "
            "Absolute commands only; repeat the command for every segment. "
            "Each stroke has id, path, description. Return full visible strokes per frame; no code, deltas or SVG tags. "
            "Do not output style fields; the renderer applies black lines on white. "
            'Envelope: {"frames":[{"i":1,"strokes":[{"id":"actor_head","path":"M ...","description":"head"}]}]}.')


def validate_batch(value: dict, wanted: list[int], dim: int, prompt: str,
                   allowed_ids: set[str] | None = None) -> dict[int, dict]:
    raw = value.get("frames")
    if not isinstance(raw, list) or [frame.get("i") for frame in raw] != wanted:
        raise ValueError(f"Expected exactly frame indices {wanted}")
    result = {}
    cls, parse = (Path2DScene, parse_path2d) if dim == 2 else (Path3DScene, parse_path3d)
    for frame in raw:
        if type(frame["i"]) is not int:
            raise ValueError("Frame indices must be integers")
        strokes = frame.get("strokes")
        if not isinstance(strokes, list) or not strokes:
            raise ValueError(f"Frame {frame['i']} has no visible strokes")
        clean = []
        for stroke in strokes:
            item = {key: stroke.get(key) for key in ("id", "path", "description")}
            if not all(isinstance(v, str) and v.strip() for v in item.values()):
                raise ValueError("Stroke id/path/description must be nonempty strings")
            if allowed_ids is not None and item["id"] not in allowed_ids:
                raise ValueError(f"Unregistered stroke id: {item['id']}")
            commands = parse(item["path"])
            if any(not math.isfinite(v) or abs(v) > 1 for cmd in commands for v in cmd.values):
                raise ValueError(f"Out-of-bounds coordinates on {item['id']}")
            clean.append(item)
        scene = cls.from_dict({"strokes": clean}, prompt=prompt)
        result[frame["i"]] = {"i": frame["i"], "strokes": scene.to_dict()["strokes"]}
    return result


def static_anchor(frames: dict[int, dict], static_ids: list[str]) -> dict[str, dict]:
    if not isinstance(static_ids, list) or not all(isinstance(i, str) for i in static_ids):
        raise ValueError("static_ids must be a list of scenery IDs")
    if len(static_ids) != len(set(static_ids)):
        raise ValueError("Duplicate static_ids")
    first = frames[min(frames)]
    strokes = {stroke["id"]: stroke for stroke in first["strokes"]}
    if set(static_ids) - set(strokes):
        raise ValueError("Fixed scenery must exist in the first key")
    return {i: strokes[i] for i in static_ids}


def pin_static(frame: dict, anchor: dict[str, dict]) -> dict:
    # Visibility of moving/transient objects is never forced back on.
    return {"i": frame["i"], "strokes": [s for s in frame["strokes"] if s["id"] not in anchor] + list(anchor.values())}
