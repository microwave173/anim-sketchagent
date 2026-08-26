from __future__ import annotations
from dataclasses import dataclass
from .schema import Sketch


@dataclass
class ValidationResult:
    valid: bool
    errors: list[str]


def validate_sketch(sketch: Sketch) -> ValidationResult:
    errors: list[str] = []
    if sketch.width <= 0 or sketch.height <= 0:
        errors.append("canvas dimensions must be positive")
    ids: set[str] = set()
    for stroke in sketch.strokes:
        if stroke.id in ids:
            errors.append(f"duplicate stroke id: {stroke.id}")
        ids.add(stroke.id)
        if not stroke.path.strip():
            errors.append(f"empty path: {stroke.id}")
        if not stroke.description.strip():
            errors.append(f"empty description: {stroke.id}")
    return ValidationResult(not errors, errors)


def validate_sketch3d(sketch) -> ValidationResult:
    errors: list[str] = []
    curves = getattr(sketch, "curves", None)
    if not curves:
        errors.append("3D sketch must contain at least one curve")
    for index, curve in enumerate(curves or []):
        points = getattr(curve, "control_points", curve)
        if len(points) != 4:
            errors.append(f"curve {index} must contain four control points")
        for point in points:
            if len(point) != 3 or not all(isinstance(value, (int, float)) for value in point):
                errors.append(f"curve {index} contains an invalid 3D point")
    return ValidationResult(not errors, errors)
