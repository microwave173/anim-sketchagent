from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import Protocol
import json

from .schema import Sketch
from .model_config import reasoning_options
from pathlib import Path
import xml.etree.ElementTree as ET
import re


_SKETCH_AGENT_IMPORT_LOCK = Lock()


SYSTEM_PROMPT = """You are a vector sketch drawer. Return ONLY valid JSON matching this schema:
{"width":1024,"height":1024,"strokes":[{"id":"unique_id","path":"SVG path d attribute","description":"plain-language semantic description","stroke":"#111111","fill":"none","stroke_width":3,"opacity":1,"group":"component"}],"metadata":{}}
Use a small number of clean, editable SVG paths. Every stroke must have a useful description. Do not use markdown fences."""


class SketchProvider(Protocol):
    def draw(self, prompt: str, *, model: str, temperature: float = 0.7) -> Sketch: ...


@dataclass
class MockProvider:
    def draw(self, prompt: str, *, model: str, temperature: float = 0.7) -> Sketch:
        return Sketch.from_dict({"metadata": {"prompt": prompt, "provider": "mock", "model": model}, "strokes": [
            {"id": "outline", "path": "M 180 700 C 180 420 360 220 520 220 C 700 220 840 420 840 700", "description": "A large curved outline representing the main subject", "stroke": "#202020", "fill": "none", "group": "main"},
            {"id": "ground", "path": "M 120 720 L 900 720", "description": "A horizontal ground line beneath the subject", "stroke": "#555555", "group": "environment"},
        ]})


class OpenAIProvider:
    def __init__(self, base_url: str | None = None, api_key: str | None = None):
        from openai import OpenAI
        self.client = OpenAI(base_url=base_url, api_key=api_key)

    def draw(self, prompt: str, *, model: str, temperature: float = 0.7) -> Sketch:
        response = self.client.responses.create(model=model, temperature=temperature, input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ], **reasoning_options())
        text = getattr(response, "output_text", None)
        if not text:
            raise RuntimeError("provider returned no output_text")
        text = text.strip().removeprefix("```json").removesuffix("```").strip()
        return Sketch.from_json(text)


class OfficialSketchAgentProvider:
    """Adapter for the original SketchAgent grid-language drawer.

    The provider owns the model-specific prompt and Bezier conversion. Callers
    only provide a stage prompt; planning and file selection remain outside it.
    """

    def __init__(self, output_dir: str | Path = "outputs/sketchagent", *, model: str | None = None,
                 resolution: int = 50, cell_size: int = 12, stroke_width: float = 7.0,
                 coordinate_mode: str = "integer", output_format: str = "svg",
                 canvas_width: int | None = None, canvas_height: int | None = None,
                 constrain_canvas: bool = True, canvas_constraint: str | None = None,
                 drawing_experience: str = "", output_name: str | None = None):
        self.output_dir = Path(output_dir)
        self.model = model
        self.resolution = resolution
        self.cell_size = cell_size
        self.stroke_width = stroke_width
        self.coordinate_mode = coordinate_mode
        self.output_format = output_format
        self.canvas_width = canvas_width
        self.canvas_height = canvas_height
        self.drawing_experience = drawing_experience
        self.output_name = output_name
        self.canvas_constraint = canvas_constraint or ("full" if constrain_canvas else "none")
        if self.canvas_constraint not in ("none", "bounds_only", "full"):
            raise ValueError("canvas_constraint must be none, bounds_only, or full")

    def draw(self, prompt: str, *, model: str, temperature: float = 0.0) -> Sketch:
        import argparse
        import sys

        repo = Path(__file__).resolve().parents[1] / "third_party" / "SketchAgent-main"
        if not repo.exists():
            raise RuntimeError(f"official SketchAgent checkout not found: {repo}")
        # Importing the vendored package mutates global interpreter state. Keep
        # only that small section locked; independent model calls can run in parallel.
        with _SKETCH_AGENT_IMPORT_LOCK:
            sys.path.insert(0, str(repo))
            try:
                from gen_sketch import SketchApp
            finally:
                if sys.path and sys.path[0] == str(repo):
                    sys.path.pop(0)
        args = argparse.Namespace(
                concept_to_draw=prompt,
                seed_mode="deterministic" if temperature == 0 else "stochastic",
                path2save=str(self.output_dir),
                model=self.model or model,
                gen_mode="generation",
                res=self.resolution,
                cell_size=self.cell_size,
                stroke_width=self.stroke_width,
                # SketchApp wraps this scalar into (width, height) internally.
                grid_size=(self.resolution + 1) * self.cell_size,
                coordinate_mode=self.coordinate_mode,
                output_format=self.output_format,
                canvas_width=self.canvas_width or (self.resolution + 1) * self.cell_size,
                canvas_height=self.canvas_height or (self.resolution + 1) * self.cell_size,
                canvas_constraint=self.canvas_constraint,
                drawing_experience=self.drawing_experience,
                output_name=self.output_name,
        )
        args.path2save = str(self.output_dir / "stage")
        Path(args.path2save).mkdir(parents=True, exist_ok=True)
        app = SketchApp(args)
        svg = app.generate_sketch(render_png=False)
        svg_path = Path(args.path2save) / "stage.svg"
        svg_path.write_text(svg, encoding="utf-8")
        sketch = self._svg_to_sketch(svg, prompt, svg_path, getattr(app, "last_model_output", ""))
        if self.coordinate_mode == "real":
            sketch = self._normalize_coordinates(sketch)
        elif self.canvas_width and self.canvas_height:
            sketch = self._resize_sketch(sketch, self.canvas_width, self.canvas_height)
        sketch.metadata.update({"coordinate_mode": self.coordinate_mode, "format": self.output_format})
        sketch.metadata["raw_response"] = getattr(app, "last_model_output", "")
        sketch.metadata["drawing_system_prompt"] = getattr(app, "base_system_prompt", app.system_prompt)
        return sketch

    @staticmethod
    def _svg_to_sketch(svg: str, prompt: str, svg_path: Path, model_output: str = "") -> Sketch:
        root = ET.fromstring(svg)
        ns = {"svg": "http://www.w3.org/2000/svg"}
        descriptions = {}
        if model_output:
            start, end = model_output.find("<strokes>"), model_output.find("</strokes>")
            if start >= 0 and end >= 0:
                xml = ET.fromstring("<root>" + model_output[start:end + len("</strokes>")] + "</root>")
                for stroke in xml.find("strokes") or []:
                    descriptions[stroke.tag] = stroke.findtext("id") or stroke.tag
        strokes = []
        for group in root.findall("svg:g", ns):
            group_id = group.get("id", "stroke")
            for index, path in enumerate(group.findall("svg:path", ns)):
                strokes.append({
                    "id": f"{group_id}_{index}",
                    "path": path.get("d", ""),
                    "description": descriptions.get(group_id, f"Official SketchAgent stroke {group_id}"),
                    "stroke": group.get("stroke", "black"),
                    "fill": group.get("fill", "none"),
                    "stroke_width": float(group.get("stroke-width", 7)),
                    "group": group_id,
                })
        return Sketch.from_dict({
            "width": int(root.get("width", 612)),
            "height": int(root.get("height", 612)),
            "strokes": strokes,
            "metadata": {"prompt": prompt, "provider": "official_sketchagent", "svg_path": str(svg_path)},
        })

    @staticmethod
    def _normalize_coordinates(sketch: Sketch) -> Sketch:
        scale_x, scale_y = max(1, sketch.width), max(1, sketch.height)
        for stroke in sketch.strokes:
            tokens = stroke.path.replace(',', ' ').split()
            output = []
            for token in tokens:
                try:
                    value = float(token)
                    output.append(f"{value / scale_x:.6g}")
                except ValueError:
                    output.append(token)
            stroke.path = " ".join(output)
            stroke.stroke_width = stroke.stroke_width / max(scale_x, scale_y)
        # Keep normalized coordinates in a normalized SVG viewBox. Rendering
        # with a 612x612 viewBox would collapse the geometry into one pixel.
        sketch.width = 1
        sketch.height = 1
        return sketch

    @staticmethod
    def _resize_sketch(sketch: Sketch, width: int, height: int) -> Sketch:
        source_width, source_height = sketch.width, sketch.height
        for stroke in sketch.strokes:
            numbers = re.compile(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?")
            index = 0
            def replace(match):
                nonlocal index
                value = float(match.group(0))
                scaled = value * (width / source_width if index % 2 == 0 else height / source_height)
                index += 1
                return f"{scaled:.6g}"
            stroke.path = numbers.sub(replace, stroke.path)
        sketch.width, sketch.height = width, height
        return sketch
