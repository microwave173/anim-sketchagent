from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Iterable

from .geometry import sample_stroke
from .parser import parse_path3d
from .patch import PatchValidation, Path3DPatch
from .schema import Path3DScene, Path3DStroke


_ID_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{0,63}")


@dataclass(frozen=True)
class Path3DPatchPolicy:
    max_additions: int = 6
    max_deletions: int = 12
    allow_empty_document: bool = False
    coordinate_limit: float = 10.0


class Path3DDocument:
    def __init__(
        self,
        prompt: str,
        strokes: Iterable[Path3DStroke] = (),
        *,
        retired_ids: Iterable[str] = (),
    ) -> None:
        self.prompt = prompt
        self.strokes = tuple(strokes)
        self.retired_ids = frozenset(str(item) for item in retired_ids)

    @property
    def stroke_ids(self) -> tuple[str, ...]:
        return tuple(item.id for item in self.strokes)

    def to_dict(self) -> dict:
        return {
            "prompt": self.prompt,
            "strokes": [vars(item) for item in self.strokes],
            "metadata": {"format": "path3d_v1", "axes": "+x right, +y depth, +z up"},
        }

    def to_scene(self) -> Path3DScene:
        if not self.strokes:
            raise ValueError("cannot create a renderable scene from an empty Path3D document")
        return Path3DScene(self.prompt, self.strokes, self.to_dict()["metadata"])

    def validate_patch(
        self,
        patch: Path3DPatch,
        policy: Path3DPatchPolicy | None = None,
        *,
        protected_ids: Iterable[str] = (),
    ) -> PatchValidation:
        policy = policy or Path3DPatchPolicy()
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
        if len(current) - len(set(deletes)) + len(additions) == 0 and not policy.allow_empty_document:
            errors.append("patch would leave the artifact empty")

        for item in additions:
            if not _ID_PATTERN.fullmatch(item.id):
                errors.append(f"invalid stroke ID: {item.id!r}")
            if re.search(r"(?:^|[\s,])[QC](?=[\s,])", item.path):
                errors.append(f"stroke {item.id!r} must use Q3/C3 instead of 2D Q/C commands")
            try:
                commands = parse_path3d(item.path)
                sample_stroke(item)
                coordinates = [value for command in commands for value in command.values]
                if not all(math.isfinite(value) for value in coordinates):
                    errors.append(f"stroke {item.id!r} has non-finite coordinates")
                elif any(abs(value) > policy.coordinate_limit for value in coordinates):
                    errors.append(
                        f"stroke {item.id!r} exceeds coordinate limit +/-{policy.coordinate_limit:g}"
                    )
            except Exception as exc:
                errors.append(f"stroke {item.id!r} has invalid Path3D: {type(exc).__name__}: {exc}")
        return PatchValidation(not errors, tuple(errors))

    def apply_patch(
        self,
        patch: Path3DPatch,
        policy: Path3DPatchPolicy | None = None,
        *,
        protected_ids: Iterable[str] = (),
    ) -> "Path3DDocument":
        validation = self.validate_patch(patch, policy, protected_ids=protected_ids)
        if not validation.valid:
            raise ValueError("; ".join(validation.errors))
        deleted = set(patch.delete_stroke_ids)
        strokes = [item for item in self.strokes if item.id not in deleted]
        strokes.extend(patch.add_strokes)
        return Path3DDocument(
            self.prompt,
            strokes,
            retired_ids=self.retired_ids | deleted,
        )
