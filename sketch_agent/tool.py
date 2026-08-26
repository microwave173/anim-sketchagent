from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .drawer import Drawer
from .schema import Sketch
from .svg import render_svg
from .validator import ValidationResult


@dataclass(frozen=True)
class DrawerRequest:
    """A manager-assigned drawing task with no planning semantics."""

    prompt: str
    output_path: Path


@dataclass(frozen=True)
class DrawerArtifact:
    sketch: Sketch
    validation: ValidationResult
    svg_path: Path


class DrawerTool:
    """File-producing tool facade intended for use by a Manager."""

    def __init__(self, drawer: Drawer):
        self.drawer = drawer

    def run(self, request: DrawerRequest) -> DrawerArtifact:
        sketch, validation = self.drawer.draw(request.prompt)
        if not validation.valid:
            raise ValueError("invalid drawer output: " + "; ".join(validation.errors))
        request.output_path.parent.mkdir(parents=True, exist_ok=True)
        if hasattr(sketch, "curves"):
            if request.output_path.suffix.lower() == ".json":
                request.output_path.write_text(sketch.to_json(), encoding="utf-8")
            else:
                from .three_d import curves_to_svg
                request.output_path.write_text(curves_to_svg(sketch.curves), encoding="utf-8")
        else:
            request.output_path.write_text(render_svg(sketch), encoding="utf-8")
        return DrawerArtifact(sketch, validation, request.output_path)
