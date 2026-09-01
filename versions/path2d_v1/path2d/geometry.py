from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .parser import parse_path2d
from .schema import Path2DStroke


@dataclass(frozen=True)
class SampledStroke:
    stroke: Path2DStroke
    polylines: tuple[np.ndarray, ...]


def _quadratic(p0: np.ndarray, p1: np.ndarray, p2: np.ndarray, steps: int) -> np.ndarray:
    t = np.linspace(0.0, 1.0, steps + 1)[:, None]
    return (1 - t) ** 2 * p0 + 2 * (1 - t) * t * p1 + t ** 2 * p2


def _cubic(p0: np.ndarray, p1: np.ndarray, p2: np.ndarray, p3: np.ndarray, steps: int) -> np.ndarray:
    t = np.linspace(0.0, 1.0, steps + 1)[:, None]
    return (1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * p1 + 3 * (1 - t) * t ** 2 * p2 + t ** 3 * p3


def sample_stroke(stroke: Path2DStroke, *, curve_steps: int = 16) -> SampledStroke:
    commands = parse_path2d(stroke.path)
    polylines: list[np.ndarray] = []
    current: np.ndarray | None = None
    start: np.ndarray | None = None
    points: list[np.ndarray] = []

    def flush() -> None:
        nonlocal points
        if len(points) >= 2:
            polylines.append(np.stack(points))
        points = []

    for item in commands:
        values = np.asarray(item.values, dtype=float)
        if item.command == "M":
            flush()
            current = values[:2]
            start = current.copy()
            points = [current.copy()]
        elif item.command == "L":
            current = values[:2]
            points.append(current.copy())
        elif item.command == "Q":
            if current is None:
                raise ValueError("Q requires a current point")
            segment = _quadratic(current, values[:2], values[2:4], curve_steps)
            points.extend(segment[1:])
            current = values[2:4]
        elif item.command == "C":
            if current is None:
                raise ValueError("C requires a current point")
            segment = _cubic(current, values[:2], values[2:4], values[4:6], curve_steps)
            points.extend(segment[1:])
            current = values[4:6]
        elif item.command == "Z":
            if start is not None and current is not None and not np.allclose(current, start):
                points.append(start.copy())
            current = start.copy() if start is not None else None
            flush()
            start = None
    flush()
    if not polylines:
        raise ValueError(f"stroke {stroke.id!r} contains no drawable segment")
    return SampledStroke(stroke, tuple(polylines))
