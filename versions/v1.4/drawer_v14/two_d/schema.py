from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


@dataclass(frozen=True)
class AddStroke:
    id: str
    path: str
    description: str
    stroke: str = "#111111"
    fill: str = "none"
    stroke_width: float = 3.0
    opacity: float = 1.0
    group: str = "default"

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "AddStroke":
        fields = cls.__dataclass_fields__
        return cls(**{key: value[key] for key in fields if key in value})

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class StrokePatch:
    delete_stroke_ids: tuple[str, ...] = ()
    add_strokes: tuple[AddStroke, ...] = ()
    summary: str = ""

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "StrokePatch":
        deletes = tuple(str(item) for item in value.get("delete_stroke_ids", []))
        additions = tuple(AddStroke.from_dict(item) for item in value.get("add_strokes", []))
        return cls(deletes, additions, str(value.get("summary", "")).strip())

    def to_dict(self) -> dict[str, Any]:
        return {
            "delete_stroke_ids": list(self.delete_stroke_ids),
            "add_strokes": [item.to_dict() for item in self.add_strokes],
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
    assessment: dict[str, Any] = field(default_factory=dict)
    instruction: dict[str, Any] | None = None
    rollback_revision: str | None = None
    preferred_revision: str | None = None
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
            decision=decision,
            assessment=value.get("assessment") if isinstance(value.get("assessment"), dict) else {},
            instruction=instruction,
            rollback_revision=str(rollback) if rollback else None,
            preferred_revision=str(value.get("preferred_revision")) if value.get("preferred_revision") else None,
            reason=str(value.get("reason", "")).strip(),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RevisionRecord:
    revision_id: str
    parent_revision: str | None
    round_index: int
    sketch_path: str
    svg_path: str
    preview_path: str
    patch_path: str | None
    stroke_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
