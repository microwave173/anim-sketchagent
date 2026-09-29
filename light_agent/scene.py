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

SVG_STROKE = "#000000"
SVG_STROKE_WIDTH = 4.0


def protocol(dim: int) -> str:
    if dim == 2:
        return ("Standard SVG path-data protocol: each stroke has exactly id, d, and description. "
                "The d value uses standard absolute SVG commands M, L, Q, C, and Z with ordinary spaces or commas, "
                "for example M 0 0 C 0.2 0.1 0.3 0.4 0.5 0.6. Do not use semicolons. "
                "The visible canvas spans [-1,1] on each axis, +x right and +y up; coordinates outside it are valid but clipped, "
                "so keep important geometry inside the visible canvas. The exported standard SVG supplies the y-axis transform. "
                "Repeat a command for every segment. Return full visible strokes per frame in the JSON envelope, not XML tags, code, or deltas. "
                "Do not output fill, color, opacity, or stroke-width: the validator and SVG exporter enforce fill=none, black ink, "
                "one immutable stroke width, and round caps/joins. Give every stroke a stable semantic id and a precise description of the part. "
                'Envelope: {"frames":[{"i":1,"strokes":[{"id":"actor_head","d":"M ... Z","description":"circular head"}]}]}.')
    syntax = ("M x y z L x y z Q3 cx cy cz x y z "
              "C3 c1x c1y c1z c2x c2y c2z x y z Z. Separate commands with spaces, never semicolons. "
              "+x right, +y depth, +z up. "
              "Use real depth, not flat 2D geometry.")
    return (f"Path3D protocol: {syntax} The primary visible world spans [-1,1] on each axis; coordinates outside it are valid, "
            "but projected geometry may be clipped, so keep important geometry visible. "
            "Absolute commands only; repeat the command for every segment. "
            "Each stroke has id, path, description. Return full visible strokes per frame; no code or deltas. "
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
            path_value = stroke.get("d") if dim == 2 else stroke.get("path")
            # Keep old 2D checkpoints readable while making `d` the public schema.
            if dim == 2 and not isinstance(path_value, str):
                path_value = stroke.get("path")
            item = {"id": stroke.get("id"), "path": path_value,
                    "description": stroke.get("description")}
            if not all(isinstance(v, str) and v.strip() for v in item.values()):
                field = "d" if dim == 2 else "path"
                raise ValueError(f"Stroke id/{field}/description must be nonempty strings")
            if allowed_ids is not None and item["id"] not in allowed_ids:
                raise ValueError(f"Unregistered stroke id: {item['id']}")
            commands = parse(item["path"])
            if any(not math.isfinite(v) for cmd in commands for v in cmd.values):
                raise ValueError(f"Non-finite coordinates on {item['id']}")
            # Style is renderer-owned in both dimensions. Model-provided style is ignored.
            item.update(stroke=SVG_STROKE, stroke_width=SVG_STROKE_WIDTH, opacity=1.0)
            clean.append(item)
        scene = cls.from_dict({"strokes": clean}, prompt=prompt)
        result[frame["i"]] = {"i": frame["i"], "strokes": scene.to_dict()["strokes"]}
    return result


def public_frames(frames: dict[int, dict], dim: int) -> list[dict]:
    """Serialize internal scenes to the stable external geometry schema."""
    output = []
    for index in sorted(frames):
        strokes = []
        for stroke in frames[index]["strokes"]:
            if dim == 2:
                strokes.append({"id": stroke["id"], "d": stroke["path"],
                                "description": stroke["description"]})
            else:
                strokes.append({key: stroke[key] for key in ("id", "path", "description")})
        output.append({"i": index, "strokes": strokes})
    return output


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
