from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from svgpathtools import parse_path

from sketch_agent.schema import Sketch, Stroke
from sketch_agent.svg import render_svg

from .schema import PatchValidation, StrokePatch


_ID_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{0,63}")


@dataclass(frozen=True)
class PatchPolicy:
    max_additions: int = 6
    max_deletions: int = 12
    allow_empty_document: bool = False
    require_no_fill: bool = False
    coordinate_tolerance: float = 2.0


class SVGDocument:
    def __init__(self, sketch: Sketch, *, retired_ids: Iterable[str] = ()) -> None:
        self.sketch = Sketch.from_dict(sketch.to_dict())
        self.retired_ids = frozenset(str(item) for item in retired_ids)

    @property
    def stroke_ids(self) -> tuple[str, ...]:
        return tuple(item.id for item in self.sketch.strokes)

    def to_svg(self) -> str:
        return render_svg(self.sketch)

    def validate_patch(
        self,
        patch: StrokePatch,
        policy: PatchPolicy | None = None,
        *,
        protected_ids: Iterable[str] = (),
    ) -> PatchValidation:
        policy = policy or PatchPolicy()
        errors: list[str] = []
        current = set(self.stroke_ids)
        deletes = list(patch.delete_stroke_ids)
        additions = list(patch.add_strokes)
        add_ids = [item.id for item in additions]

        if not deletes and not additions:
            errors.append("patch must add or delete at least one stroke")
        if len(deletes) > policy.max_deletions:
            errors.append(f"patch deletes {len(deletes)} strokes; maximum is {policy.max_deletions}")
        if len(additions) > policy.max_additions:
            errors.append(f"patch adds {len(additions)} strokes; maximum is {policy.max_additions}")
        if len(deletes) != len(set(deletes)):
            errors.append("delete_stroke_ids contains duplicates")
        missing = sorted(set(deletes) - current)
        if missing:
            errors.append("cannot delete missing stroke IDs: " + ", ".join(missing))
        protected_deleted = sorted(set(deletes) & set(protected_ids))
        if protected_deleted:
            errors.append("cannot delete Planner-protected stroke IDs: " + ", ".join(protected_deleted))
        if len(add_ids) != len(set(add_ids)):
            errors.append("add_strokes contains duplicate IDs")
        forbidden = sorted(set(add_ids) & (current | self.retired_ids))
        if forbidden:
            errors.append("new stroke IDs must never reuse current or retired IDs: " + ", ".join(forbidden))
        remaining_count = len(current) - len(set(deletes)) + len(additions)
        if remaining_count == 0 and not policy.allow_empty_document:
            errors.append("patch would leave the artifact empty")

        for item in additions:
            if not _ID_PATTERN.fullmatch(item.id):
                errors.append(f"invalid stroke ID: {item.id!r}")
            if not item.description.strip():
                errors.append(f"stroke {item.id!r} requires a description")
            if not item.path.strip():
                errors.append(f"stroke {item.id!r} requires path data")
                continue
            if policy.require_no_fill and item.fill.strip().lower() != "none":
                errors.append(f"stroke {item.id!r} must use fill='none' in outline-only mode")
            if not (0 < float(item.stroke_width) <= 64):
                errors.append(f"stroke {item.id!r} has invalid stroke_width")
            if not (0 <= float(item.opacity) <= 1):
                errors.append(f"stroke {item.id!r} has invalid opacity")
            try:
                path = parse_path(item.path)
                xmin, xmax, ymin, ymax = path.bbox()
                tol = policy.coordinate_tolerance
                if xmin < -tol or ymin < -tol or xmax > self.sketch.width + tol or ymax > self.sketch.height + tol:
                    errors.append(
                        f"stroke {item.id!r} is outside canvas bounds: "
                        f"bbox=({xmin:.1f},{ymin:.1f})-({xmax:.1f},{ymax:.1f})"
                    )
            except Exception as exc:
                errors.append(f"stroke {item.id!r} has invalid SVG path: {type(exc).__name__}: {exc}")
        return PatchValidation(not errors, tuple(errors))

    def apply_patch(
        self,
        patch: StrokePatch,
        policy: PatchPolicy | None = None,
        *,
        protected_ids: Iterable[str] = (),
    ) -> "SVGDocument":
        validation = self.validate_patch(patch, policy, protected_ids=protected_ids)
        if not validation.valid:
            raise ValueError("; ".join(validation.errors))
        deleted = set(patch.delete_stroke_ids)
        strokes = [item for item in self.sketch.strokes if item.id not in deleted]
        strokes.extend(Stroke.from_dict(item.to_dict()) for item in patch.add_strokes)
        sketch = Sketch(self.sketch.width, self.sketch.height, strokes, dict(self.sketch.metadata))
        retired = self.retired_ids | deleted
        return SVGDocument(sketch, retired_ids=retired)
