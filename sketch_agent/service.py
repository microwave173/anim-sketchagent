from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv

from .rendering import render_svg_png
from .svg import render_svg
from .three_d import TrainingFree3DGRPO, curves_to_svg, render_3d_views
from .two_d_loop import TwoDCriticLoop
from .model_config import get_reasoning_effort


Mode = Literal["2d", "3d"]


def safe_name(text: str, limit: int = 48) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "_", text.lower()).strip("_")
    return (value or "sketch")[:limit]


@dataclass(frozen=True)
class DrawerResult:
    mode: Mode
    output_dir: Path
    sketch_json: Path
    preview_svg: Path
    preview_images: tuple[Path, ...]
    manifest: Path


class DrawerService:
    """Manager-facing prompt-to-JSON drawer with fixed 2D/3D configurations."""

    def __init__(self, *, model: str | None = None, samples: int | None = None, epochs: int = 2):
        load_dotenv(Path(__file__).resolve().parents[1] / ".env")
        self.model = model or os.getenv("MODEL", "gpt-5.6-terra")
        self.reasoning_effort = get_reasoning_effort()
        self.samples = samples
        self.epochs = epochs

    def draw(self, mode: Mode, prompt: str, output_dir: str | Path | None = None,
             *, width: int = 512, height: int = 512) -> DrawerResult:
        if mode not in ("2d", "3d"):
            raise ValueError("mode must be '2d' or '3d'")
        if not prompt.strip():
            raise ValueError("prompt cannot be empty")
        if width < 64 or height < 64 or width > 4096 or height > 4096:
            raise ValueError("width and height must be between 64 and 4096 pixels")
        output = Path(output_dir) if output_dir else Path("outputs/drawer") / f"{mode}_{safe_name(prompt)}"
        output.mkdir(parents=True, exist_ok=True)
        result = self._draw_2d(prompt, output, width, height) if mode == "2d" else self._draw_3d(prompt, output, width, height)
        return result

    def _draw_2d(self, prompt: str, output: Path, width: int, height: int) -> DrawerResult:
        work = output / "run"
        loop_result = TwoDCriticLoop(
            model=self.model,
            samples=self.samples or 3,
            max_loops=self.epochs,
            output_dir=work,
            canvas_width=width,
            canvas_height=height,
        ).run(prompt)
        sketch = loop_result.sketch

        raw_response = loop_result.raw_response
        canonical = {
            "schema_version": "1.0",
            "modality": "2d",
            "prompt": prompt,
            "coordinate_system": {
                "generation": "integer_grid_1_50",
                "geometry": "svg_canvas_pixels",
                "x_axis": "right",
                "y_axis": "down",
            },
            "canvas": {"width": sketch.width, "height": sketch.height},
            "strokes": [vars(stroke) for stroke in sketch.strokes],
            "metadata": sketch.metadata,
        }
        json_path = output / "sketch.json"
        json_path.write_text(json.dumps(canonical, ensure_ascii=False, indent=2), encoding="utf-8")
        (output / "raw_response.txt").write_text(raw_response, encoding="utf-8")

        svg = render_svg(sketch)
        svg_path = output / "preview.svg"
        svg_path.write_text(svg, encoding="utf-8")
        png_path = render_svg_png(svg, output / "preview.png", width=width, height=height)
        manifest = self._write_manifest(output, "2d", prompt, json_path, [svg_path, png_path], {
            "coordinate_mode": "integer_grid_1_50",
            "canonical_format": "json",
            "stroke_count": len(sketch.strokes),
            "canvas": {"width": width, "height": height},
            "samples_per_loop": self.samples or 3,
            "max_loops": self.epochs,
            "loops_completed": loop_result.loops_completed,
            "stopped_early": loop_result.stopped_early,
            "best_candidate_id": loop_result.best_candidate_id,
            "run_wall_seconds": loop_result.timings["totals"]["run_wall_seconds"],
            "timings": "run/timings.json",
            "reasoning_effort": self.reasoning_effort,
            "vision_model": os.getenv("VISION_MODEL", "gpt-5.6-luna"),
        })
        return DrawerResult("2d", output, json_path, svg_path, (png_path,), manifest)

    def _draw_3d(self, prompt: str, output: Path, width: int, height: int) -> DrawerResult:
        work = output / "run"
        sketch = TrainingFree3DGRPO(
            model=self.model,
            coordinate_mode="real",
            output_format="json",
            samples=self.samples or 2,
            temperature=0.65,
            output_dir=work,
            canvas_width=width,
            canvas_height=height,
        ).run(prompt, epochs=self.epochs)
        canonical = {
            "schema_version": "1.0",
            "modality": "3d",
            "prompt": prompt,
            "coordinate_system": {
                "type": "right_handed",
                "x_axis": "right",
                "y_axis": "forward",
                "z_axis": "up",
                "units": "normalized_real",
            },
            "canvas": {"width": width, "height": height},
            "curves": [
                {"id": f"curve_{index:03d}", "control_points": curve.control_points}
                for index, curve in enumerate(sketch.curves)
            ],
            "metadata": sketch.metadata,
        }
        json_path = output / "sketch.json"
        json_path.write_text(json.dumps(canonical, ensure_ascii=False, indent=2), encoding="utf-8")
        svg_path = output / "preview.svg"
        svg_path.write_text(curves_to_svg(sketch.curves, width=width, height=height), encoding="utf-8")
        images = tuple(render_3d_views(sketch.curves, output / "views", width=width, height=height))
        manifest = self._write_manifest(output, "3d", prompt, json_path, [svg_path, *images], {
            "coordinate_mode": "normalized_real",
            "canonical_format": "json",
            "curve_count": len(sketch.curves),
            "samples": self.samples or 2,
            "learning_epochs": self.epochs,
            "score": sketch.metadata.get("final_score"),
            "reasoning_effort": self.reasoning_effort,
            "vision_model": os.getenv("VISION_MODEL", "gpt-5.6-luna"),
            "canvas": {"width": width, "height": height},
        })
        return DrawerResult("3d", output, json_path, svg_path, images, manifest)

    def _write_manifest(self, output: Path, mode: Mode, prompt: str, json_path: Path,
                        previews: list[Path], config: dict) -> Path:
        path = output / "manifest.json"
        path.write_text(json.dumps({
            "mode": mode,
            "prompt": prompt,
            "model": self.model,
            "canonical": json_path.name,
            "previews": [str(item.relative_to(output)) for item in previews],
            "config": config,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        return path
