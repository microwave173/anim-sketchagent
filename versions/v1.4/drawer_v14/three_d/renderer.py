from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageColor, ImageDraw

from .geometry import SampledStroke, normalize_strokes, sample_stroke
from .schema import Path3DScene


@dataclass(frozen=True)
class Camera:
    name: str
    position: tuple[float, float, float]
    target: tuple[float, float, float] = (0.0, 0.0, 0.0)
    up: tuple[float, float, float] = (0.0, 0.0, 1.0)
    focal: float = 2.6


DEFAULT_CAMERAS = (
    Camera("front", (0.0, -3.6, 0.15)),
    Camera("side", (3.6, 0.0, 0.15)),
    Camera("top", (0.01, -0.01, 3.8), up=(0.0, 1.0, 0.0)),
    Camera("perspective", (2.8, -3.2, 2.4)),
)


def _camera_coordinates(points: np.ndarray, camera: Camera) -> np.ndarray:
    position = np.asarray(camera.position, dtype=float)
    target = np.asarray(camera.target, dtype=float)
    up_hint = np.asarray(camera.up, dtype=float)
    forward = target - position
    forward /= np.linalg.norm(forward)
    right = np.cross(forward, up_hint)
    right /= np.linalg.norm(right)
    up = np.cross(right, forward)
    relative = points - position
    return np.stack((relative @ right, relative @ up, relative @ forward), axis=1)


def _project(points: np.ndarray, camera: Camera, width: int, height: int, margin: float) -> tuple[np.ndarray, np.ndarray]:
    camera_points = _camera_coordinates(points, camera)
    depth = np.maximum(camera_points[:, 2], 1e-4)
    projected = camera.focal * camera_points[:, :2] / depth[:, None]
    scale = min(width, height) * (0.5 - margin)
    pixels = np.empty_like(projected)
    pixels[:, 0] = width / 2.0 + projected[:, 0] * scale
    pixels[:, 1] = height / 2.0 - projected[:, 1] * scale
    return pixels, depth


def _rgba(color: str, opacity: float) -> tuple[int, int, int, int]:
    rgb = ImageColor.getrgb(color)
    return rgb[0], rgb[1], rgb[2], round(255 * opacity)


def render_view(
    scene: Path3DScene,
    camera: Camera,
    output_path: str | Path,
    *,
    width: int = 512,
    height: int = 512,
    supersample: int = 3,
    margin: float = 0.12,
) -> Path:
    sampled = normalize_strokes(tuple(sample_stroke(stroke) for stroke in scene.strokes))
    render_width, render_height = width * supersample, height * supersample
    layers: list[tuple[float, SampledStroke, np.ndarray]] = []
    for item in sampled:
        for line in item.polylines:
            pixels, depths = _project(line, camera, render_width, render_height, margin)
            layers.append((float(depths.mean()), item, pixels))
    layers.sort(key=lambda layer: layer[0], reverse=True)

    image = Image.new("RGBA", (render_width, render_height), "white")
    draw = ImageDraw.Draw(image, "RGBA")
    for _, item, pixels in layers:
        coordinates = [(float(x), float(y)) for x, y in pixels]
        line_width = max(1, round(item.stroke.stroke_width * supersample))
        draw.line(
            coordinates,
            fill=_rgba(item.stroke.stroke, item.stroke.opacity),
            width=line_width,
            joint="curve",
        )
    image = image.convert("RGB").resize((width, height), Image.Resampling.LANCZOS)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)
    return output


def render_scene_views(
    scene: Path3DScene,
    output_dir: str | Path,
    *,
    width: int = 512,
    height: int = 512,
    cameras: tuple[Camera, ...] = DEFAULT_CAMERAS,
) -> tuple[Path, ...]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    paths = tuple(
        render_view(scene, camera, output / f"view_{camera.name}.png", width=width, height=height)
        for camera in cameras
    )
    _contact_sheet(paths, output / "contact_sheet.png", width=width, height=height)
    return paths


def _contact_sheet(paths: tuple[Path, ...], output: Path, *, width: int, height: int) -> None:
    sheet = Image.new("RGB", (width * 2, height * 2), "white")
    draw = ImageDraw.Draw(sheet)
    for index, path in enumerate(paths[:4]):
        image = Image.open(path).convert("RGB")
        x = (index % 2) * width
        y = (index // 2) * height
        sheet.paste(image, (x, y))
        draw.rectangle((x + 8, y + 8, x + 132, y + 34), fill="white")
        draw.text((x + 14, y + 12), path.stem.removeprefix("view_"), fill="#111111")
    sheet.save(output)
