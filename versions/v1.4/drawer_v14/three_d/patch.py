from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

from .schema import Path3DStroke


@dataclass(frozen=True)
class Path3DPatch:
    delete_stroke_ids: tuple[str, ...] = ()
    add_strokes: tuple[Path3DStroke, ...] = ()
    summary: str = ""

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Path3DPatch":
        return cls(
            tuple(str(item) for item in value.get("delete_stroke_ids", [])),
            tuple(Path3DStroke.from_dict(item) for item in value.get("add_strokes", [])),
            str(value.get("summary", "")).strip(),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "delete_stroke_ids": list(self.delete_stroke_ids),
            "add_strokes": [asdict(item) for item in self.add_strokes],
            "summary": self.summary,
        }


@dataclass(frozen=True)
class PatchValidation:
    valid: bool
    errors: tuple[str, ...] = ()


Decision = Literal["continue", "retry", "rollback", "finish", "fail"]


@dataclass(frozen=True)
class PlannerReview:
    decision: Decision
    assessment: dict[str, Any]
    instruction: dict[str, Any] | None = None
    rollback_revision: str | None = None
    reason: str = ""

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "PlannerReview":
        decision = str(value.get("decision", ""))
        if decision not in {"continue", "retry", "rollback", "finish", "fail"}:
            raise ValueError(f"invalid planner decision: {decision!r}")
        instruction = value.get("instruction")
        if decision in {"continue", "retry"} and not isinstance(instruction, dict):
            raise ValueError(f"planner decision {decision} requires instruction")
        rollback = value.get("rollback_revision")
        if decision == "rollback" and not rollback:
            raise ValueError("rollback decision requires rollback_revision")
        return cls(
            decision,
            value.get("assessment") if isinstance(value.get("assessment"), dict) else {},
            instruction,
            str(rollback) if rollback else None,
            str(value.get("reason", "")).strip(),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RevisionRecord:
    revision_id: str
    parent_revision: str | None
    round_index: int
    scene_path: str
    contact_sheet_path: str
    views_dir: str
    patch_path: str | None
    stroke_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
