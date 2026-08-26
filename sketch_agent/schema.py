from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
import json


@dataclass
class Stroke:
    """One editable vector stroke with a semantic description."""

    id: str
    path: str
    description: str
    stroke: str = "#111111"
    fill: str = "none"
    stroke_width: float = 3.0
    opacity: float = 1.0
    group: str = "default"

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Stroke":
        required = ("id", "path", "description")
        missing = [key for key in required if not value.get(key)]
        if missing:
            raise ValueError(f"stroke missing required fields: {missing}")
        return cls(**{key: value[key] for key in cls.__dataclass_fields__ if key in value})


@dataclass
class Sketch:
    width: int = 1024
    height: int = 1024
    strokes: list[Stroke] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Sketch":
        strokes = [Stroke.from_dict(item) for item in value.get("strokes", [])]
        return cls(int(value.get("width", 1024)), int(value.get("height", 1024)), strokes, value.get("metadata", {}))

    @classmethod
    def from_json(cls, text: str) -> "Sketch":
        return cls.from_dict(json.loads(text))

    def to_dict(self) -> dict[str, Any]:
        return {"width": self.width, "height": self.height, "strokes": [vars(s) for s in self.strokes], "metadata": self.metadata}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

