from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageColor, ImageDraw

from .geometry import sample_stroke
from .schema import Path2DScene


def world_to_pixel(points: np.ndarray, width: int, height: int, *, margin: float = 0.08) -> np.ndarray:
    scale = min(width, height) * (0.5 - margin)
    pixels = np.empty_like(points)
    pixels[:, 0] = width / 2.0 + points[:, 0] * scale
    pixels[:, 1] = height / 2.0 - points[:, 1] * scale
    return pixels


def render_scene(scene: Path2DScene, out_path: Path, *, width: int = 512, height: int = 512) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    for stroke in scene.strokes:
        sampled = sample_stroke(stroke)
        color = ImageColor.getrgb(stroke.stroke)
        width_px = max(1, int(round(float(stroke.stroke_width))))
        for line in sampled.polylines:
            pix = world_to_pixel(line, width, height)
            xy = [(float(x), float(y)) for x, y in pix]
            if len(xy) == 1:
                x, y = xy[0]
                draw.ellipse((x - 1, y - 1, x + 1, y + 1), fill=color)
            else:
                draw.line(xy, fill=color, width=width_px, joint="curve")
    image.save(out_path)
    return out_path
