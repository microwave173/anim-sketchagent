from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from drawer_v14.three_d.patch import Path3DPatch
from path3d_json.compiler import compile_scene
from path3d_json.schema import StructuredScene, StructuredStroke


@dataclass(frozen=True)
class StructuredPath3DPatch:
    delete_stroke_ids: tuple[str, ...]
    add_strokes: tuple[StructuredStroke, ...]
    summary: str = ""

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "StructuredPath3DPatch":
        if not isinstance(value.get("delete_stroke_ids", []), list):
            raise ValueError("delete_stroke_ids must be an array")
        raw_additions = value.get("add_strokes", [])
        if not isinstance(raw_additions, list):
            raise ValueError("add_strokes must be an array")
        return cls(
            tuple(str(item) for item in value.get("delete_stroke_ids", [])),
            tuple(StructuredStroke.from_dict(item) for item in raw_additions),
            str(value.get("summary", "")).strip(),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "delete_stroke_ids": list(self.delete_stroke_ids),
            "add_strokes": [item.to_dict() for item in self.add_strokes],
            "summary": self.summary,
        }

    def compile(self, *, prompt: str) -> Path3DPatch:
        if self.add_strokes:
            scene = StructuredScene(prompt, self.add_strokes, {"source_format": "structured_patch_v1"})
            compiled = compile_scene(scene).strokes
        else:
            compiled = ()
        return Path3DPatch(self.delete_stroke_ids, tuple(compiled), self.summary)
