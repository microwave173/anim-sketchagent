from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from typing import Any, Literal


Point3 = tuple[float, float, float]
CommandName = Literal["M", "L", "Q3", "C3", "Z"]


def _point(value: Any, *, field_name: str) -> Point3:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError(f"{field_name} must be one [x,y,z] triplet")
    if not all(isinstance(item, (int, float)) and math.isfinite(float(item)) for item in value):
        raise ValueError(f"{field_name} coordinates must be finite numbers")
    return tuple(float(item) for item in value)


@dataclass(frozen=True)
class StructuredCommand:
    command: CommandName
    point: Point3 | None = None
    control: Point3 | None = None
    control_1: Point3 | None = None
    control_2: Point3 | None = None
    end: Point3 | None = None

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "StructuredCommand":
        if not isinstance(value, dict):
            raise ValueError("each command must be a JSON object")
        command = str(value.get("command", ""))
        allowed_keys = {
            "M": {"command", "point"},
            "L": {"command", "point"},
            "Q3": {"command", "control", "end"},
            "C3": {"command", "control_1", "control_2", "end"},
            "Z": {"command"},
        }
        if command not in allowed_keys:
            raise ValueError(f"unsupported structured Path3D command: {command!r}")
        unexpected = sorted(set(value) - allowed_keys[command])
        if unexpected:
            raise ValueError(f"command {command} has unexpected fields: {unexpected}")
        if command in {"M", "L"}:
            return cls(command, point=_point(value.get("point"), field_name=f"{command}.point"))
        if command == "Q3":
            return cls(
                command,
                control=_point(value.get("control"), field_name="Q3.control"),
                end=_point(value.get("end"), field_name="Q3.end"),
            )
        if command == "C3":
            return cls(
                command,
                control_1=_point(value.get("control_1"), field_name="C3.control_1"),
                control_2=_point(value.get("control_2"), field_name="C3.control_2"),
                end=_point(value.get("end"), field_name="C3.end"),
            )
        return cls("Z")

    def to_dict(self) -> dict[str, Any]:
        value: dict[str, Any] = {"command": self.command}
        for key in ("point", "control", "control_1", "control_2", "end"):
            item = getattr(self, key)
            if item is not None:
                value[key] = list(item)
        return value


@dataclass(frozen=True)
class StructuredStroke:
    id: str
    commands: tuple[StructuredCommand, ...]
    description: str
    stroke: str = "#111111"
    stroke_width: float = 3.0
    opacity: float = 1.0
    group: str = "default"

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "StructuredStroke":
        if not isinstance(value, dict):
            raise ValueError("each stroke must be a JSON object")
        stroke_id = str(value.get("id", "")).strip()
        description = str(value.get("description", "")).strip()
        if not stroke_id or not description:
            raise ValueError("each stroke requires non-empty id and description")
        raw_commands = value.get("commands")
        if not isinstance(raw_commands, list) or not raw_commands:
            raise ValueError(f"stroke {stroke_id!r} requires a non-empty commands array")
        commands = tuple(StructuredCommand.from_dict(item) for item in raw_commands)
        if commands[0].command != "M":
            raise ValueError(f"stroke {stroke_id!r} must begin with an M command")
        active = False
        drawable = False
        for item in commands:
            if item.command == "M":
                active = True
            elif not active:
                raise ValueError(f"stroke {stroke_id!r}: {item.command} requires an active subpath")
            elif item.command == "Z":
                active = False
                drawable = True
            else:
                drawable = True
        if not drawable:
            raise ValueError(f"stroke {stroke_id!r} contains no drawable command")
        stroke_width = float(value.get("stroke_width", 3.0))
        opacity = float(value.get("opacity", 1.0))
        if not 0 < stroke_width <= 64:
            raise ValueError(f"stroke {stroke_id!r} has invalid stroke_width")
        if not 0 <= opacity <= 1:
            raise ValueError(f"stroke {stroke_id!r} has invalid opacity")
        return cls(
            stroke_id,
            commands,
            description,
            str(value.get("stroke", "#111111")),
            stroke_width,
            opacity,
            str(value.get("group", "default")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "commands": [item.to_dict() for item in self.commands],
            "description": self.description,
            "stroke": self.stroke,
            "stroke_width": self.stroke_width,
            "opacity": self.opacity,
            "group": self.group,
        }


@dataclass(frozen=True)
class StructuredScene:
    prompt: str
    strokes: tuple[StructuredStroke, ...]
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, value: dict[str, Any], *, prompt: str = "") -> "StructuredScene":
        if not isinstance(value, dict):
            raise ValueError("scene must be a JSON object")
        raw_strokes = value.get("strokes")
        if not isinstance(raw_strokes, list) or not raw_strokes:
            raise ValueError("scene requires a non-empty strokes array")
        strokes = tuple(StructuredStroke.from_dict(item) for item in raw_strokes)
        ids = [item.id for item in strokes]
        if len(ids) != len(set(ids)):
            raise ValueError("stroke IDs must be unique")
        return cls(
            str(value.get("prompt") or prompt).strip(),
            strokes,
            value.get("metadata") if isinstance(value.get("metadata"), dict) else {},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "prompt": self.prompt,
            "strokes": [item.to_dict() for item in self.strokes],
            "metadata": self.metadata,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
