from __future__ import annotations

import ast
import base64
import io
import json
import math
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .model_config import reasoning_options

from .providers import OpenAIProvider


CURVE_START = "<curves>"
CURVE_END = "</curves>"


@dataclass
class Curve3D:
    control_points: list[list[float]]


@dataclass
class Sketch3D:
    curves: list[Curve3D]
    prompt: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "prompt": self.prompt,
            "curves": [curve.control_points for curve in self.curves],
            "metadata": self.metadata,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


def parse_curves(text: str, *, coordinate_mode: str = "real") -> list[Curve3D]:
    start, end = text.rfind(CURVE_START), text.rfind(CURVE_END)
    if start < 0 or end <= start:
        raise ValueError("missing <curves>...</curves> block")
    block = re.sub(r"#.*", "", text[start + len(CURVE_START):end]).strip()
    values = ast.literal_eval(block)
    if not isinstance(values, list):
        raise ValueError("curves must be a list")
    curves: list[Curve3D] = []
    for curve in values:
        if not isinstance(curve, list) or len(curve) != 4:
            raise ValueError("each curve must contain four control points")
        points: list[list[float]] = []
        for point in curve:
            if not isinstance(point, list) or len(point) != 3:
                raise ValueError("each control point must contain three coordinates")
            if not all(isinstance(value, (int, float)) for value in point):
                raise ValueError("coordinates must be numeric")
            values_point = [float(value) for value in point]
            if coordinate_mode == "integer":
                values_point = [round(max(0.0, min(50.0, value))) for value in values_point]
            points.append(values_point)
        curves.append(Curve3D(points))
    if not curves:
        raise ValueError("empty curve list")
    return curves


def curves_to_json(curves: list[Curve3D], prompt: str, metadata: dict[str, Any] | None = None) -> str:
    return Sketch3D(curves, prompt, metadata or {}).to_json()


def _project(point: list[float], view: str, size: int) -> tuple[float, float]:
    x, y, z = point
    if view == "front":
        a, b = x, z
    elif view == "side":
        a, b = y, z
    elif view == "top":
        a, b = x, y
    else:
        angle = math.radians(35)
        a = x * math.cos(angle) - y * math.sin(angle)
        b = z + 0.35 * (x * math.sin(angle) + y * math.cos(angle))
    scale = size * 0.38
    return size / 2 + a * scale, size / 2 - b * scale


def _render_coordinates(curves: list[Curve3D]) -> list[Curve3D]:
    """Convert integer coordinates and center/scale every scene for rendering."""
    values = [value for curve in curves for point in curve.control_points for value in point]
    if not values:
        return curves
    if any(abs(value) > 2 for value in values):
        curves = [Curve3D([[(value - 25.0) / 25.0 for value in point] for point in curve.control_points]) for curve in curves]
    points = [point for curve in curves for point in curve.control_points]
    mins = [min(point[i] for point in points) for i in range(3)]
    maxs = [max(point[i] for point in points) for i in range(3)]
    center = [(mins[i] + maxs[i]) / 2.0 for i in range(3)]
    extent = max(maxs[i] - mins[i] for i in range(3)) or 1.0
    scale = 1.55 / extent
    return [
        Curve3D([[(point[i] - center[i]) * scale for i in range(3)] for point in curve.control_points])
        for curve in curves
    ]


def render_3d_views(curves: list[Curve3D], output_dir: str | Path, *, width: int = 512, height: int = 512) -> list[Path]:
    from PIL import Image, ImageDraw

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    curves = _render_coordinates(curves)
    scale_size = min(width, height)
    for view in ("front", "side", "top", "perspective"):
        image = Image.new("RGB", (width, height), "white")
        draw = ImageDraw.Draw(image)
        for curve in curves:
            points = [_project(point, view, scale_size) for point in curve.control_points]
            points = [(x + (width - scale_size) / 2, y + (height - scale_size) / 2) for x, y in points]
            draw.line(points, fill="black", width=2, joint="curve")
        path = output / f"view_{view}.png"
        image.save(path)
        paths.append(path)
    return paths


def curves_to_svg(curves: list[Curve3D], *, view: str = "perspective", width: int = 512, height: int = 512) -> str:
    curves = _render_coordinates(curves)
    paths = []
    for curve in curves:
        span = min(width, height)
        points = [_project(point, view, span) for point in curve.control_points]
        points = [(x + (width - span) / 2, y + (height - span) / 2) for x, y in points]
        if len(points) == 4:
            d = "M %.2f %.2f C %.2f %.2f %.2f %.2f %.2f %.2f" % (*points[0], *points[1], *points[2], *points[3])
        else:
            d = "M " + " L ".join("%.2f %.2f" % point for point in points)
        paths.append(f'<path d="{d}" fill="none" stroke="black" stroke-width="2" />')
    return '\n'.join([
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        *paths,
        '</svg>',
    ])


def _image_data_url(path: Path) -> str:
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


class LM3DScorer:
    def __init__(self, *, model: str | None = None, base_url: str | None = None, api_key: str | None = None,
                 canvas_width: int = 512, canvas_height: int = 512):
        from dotenv import load_dotenv
        load_dotenv(Path(__file__).resolve().parents[1] / ".env")
        from openai import OpenAI
        self.model = model or os.getenv("VISION_MODEL", "gpt-5.6-luna")
        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"), base_url=base_url or os.getenv("BASE_URL"))
        self.canvas_width = canvas_width
        self.canvas_height = canvas_height

    def score(self, prompt: str, curves: list[Curve3D], render_dir: str | Path) -> tuple[float, str]:
        paths = render_3d_views(curves, render_dir, width=self.canvas_width, height=self.canvas_height)
        content: list[dict[str, Any]] = [{"type": "input_text", "text": (
            "Judge this 3D line sketch against the prompt. Inspect all views. "
            "Return only JSON: {\"score\": number 0..1, \"evidence\": string}.\nPrompt: " + prompt
        )}]
        content.extend({"type": "input_image", "image_url": _image_data_url(path)} for path in paths)
        response = self.client.responses.create(
            model=self.model,
            input=[{"role": "user", "content": content}],
            max_output_tokens=300,
            **reasoning_options(),
        )
        text = (response.output_text or "").strip()
        try:
            cleaned = text.strip().removeprefix("```json").removesuffix("```").strip()
            if not cleaned.startswith("{"):
                cleaned = cleaned[cleaned.find("{"):cleaned.rfind("}") + 1]
            data = json.loads(cleaned)
            return max(0.0, min(1.0, float(data["score"]))), str(data.get("evidence", ""))
        except Exception as exc:
            raise ValueError(f"invalid LM score response: {text}") from exc


GENERATION_PROMPT = """You are a professional 3D sketch artist. Generate the object described below as cubic Bezier curves.
Return exactly one Python list wrapped in <curves> and </curves>. Each curve has exactly four [x,y,z] control points.
Use a right-handed coordinate system, +Z up, +X right, +Y forward. Keep the object centered and use depth variation.
Coordinate convention: {coordinate_instruction}
Prompt: {prompt}
Useful drawing experiences:
{experiences}
Return only the curve block."""


EXPERIENCE_PROMPT = """Compare two 3D sketch candidates for this prompt: {prompt}
Best score: {best_score:.3f}\nBest curves:\n{best}\nWorst score: {worst_score:.3f}\nWorst curves:\n{worst}
Extract up to {limit} concise, reusable lessons about 3D geometry, depth, structure, or control-point placement.
Return only a JSON list of strings."""


@dataclass
class TrainingFree3DGRPO:
    model: str | None = None
    coordinate_mode: str = "real"
    samples: int = 3
    temperature: float = 0.7
    experience_limit: int = 20
    output_dir: Path = Path("outputs/3d_grpo")
    output_format: str = "json"
    canvas_width: int = 512
    canvas_height: int = 512

    def __post_init__(self) -> None:
        from dotenv import load_dotenv
        load_dotenv(Path(__file__).resolve().parents[1] / ".env")
        self.model = self.model or os.getenv("MODEL", "gpt-5.6-terra")
        self.generator = OpenAIProvider(base_url=os.getenv("BASE_URL"), api_key=os.getenv("OPENAI_API_KEY"))
        self.scorer = LM3DScorer(
            model=os.getenv("VISION_MODEL", "gpt-5.6-luna"),
            canvas_width=self.canvas_width,
            canvas_height=self.canvas_height,
        )
        self.experiences: list[str] = []

    def _generate(self, prompt: str, temperature: float) -> tuple[str, list[Curve3D]]:
        instruction = "integer coordinates in [0, 50]" if self.coordinate_mode == "integer" else "real coordinates roughly in [-0.8, 0.8]"
        format_note = (
            "The native deliverable is structured JSON; preserve explicit depth and topology."
            if self.output_format == "json" else
            "The deliverable is a fixed perspective SVG projection; prioritize a legible projected silhouette while retaining coherent depth."
        )
        experience_text = "\n".join(f"- {item}" for item in self.experiences) or "None"
        canvas_note = (
            f"The target render canvas is {self.canvas_width}x{self.canvas_height} pixels "
            f"(aspect ratio {self.canvas_width / self.canvas_height:.3f}). Keep the full object inside the frame, "
            "center it, leave roughly 10 percent margin, and compose for this aspect ratio."
        )
        request = GENERATION_PROMPT.format(
            coordinate_instruction=instruction + " " + format_note + " " + canvas_note,
            prompt=prompt,
            experiences=experience_text,
        )
        response = self.generator.client.responses.create(
            model=self.model,
            temperature=temperature,
            input=request,
            max_output_tokens=6000,
            **reasoning_options(),
        )
        text = response.output_text or ""
        return text, parse_curves(text, coordinate_mode=self.coordinate_mode)

    def run(self, prompt: str, *, epochs: int = 1) -> Sketch3D:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        best_text, best_curves, best_score = "", [], -1.0
        history: list[dict[str, Any]] = []
        for epoch in range(epochs):
            candidates = []
            for index in range(max(1, self.samples)):
                try:
                    text, curves = self._generate(prompt, self.temperature + index * 0.05)
                    score, evidence = self.scorer.score(prompt, curves, self.output_dir / f"epoch_{epoch + 1:02d}_candidate_{index:02d}")
                    candidates.append((score, text, curves, evidence))
                    (self.output_dir / f"epoch_{epoch + 1:02d}_candidate_{index:02d}.json").write_text(
                        json.dumps({"response": text, "curves": [curve.control_points for curve in curves], "score": score, "evidence": evidence}, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
                except Exception as exc:
                    history.append({"epoch": epoch, "candidate": index, "error": str(exc)})
            if not candidates:
                raise RuntimeError("all 3D candidates failed")
            candidates.sort(key=lambda item: item[0], reverse=True)
            best, worst = candidates[0], candidates[-1]
            if best[0] > best_score:
                best_score, best_text, best_curves = best[0], best[1], best[2]
            if len(candidates) >= 2:
                try:
                    lessons = self._extract_experiences(prompt, best, worst)
                    self.experiences = list(dict.fromkeys(self.experiences + lessons))[: self.experience_limit]
                except Exception as exc:
                    history.append({"epoch": epoch, "experience_error": str(exc)})
            history.append({"epoch": epoch, "scores": [item[0] for item in candidates], "best_evidence": best[3], "experiences": self.experiences})
        # Learning rounds build reusable experience; a separate deterministic
        # generation consumes that experience to produce the delivered sketch.
        final_score, final_evidence = best_score, "fallback to best learning candidate"
        try:
            final_text, final_curves = self._generate(prompt, 0.0)
            final_score, final_evidence = self.scorer.score(prompt, final_curves, self.output_dir / "final_generation_views")
            best_text, best_curves = final_text, final_curves
            (self.output_dir / "final_generation.json").write_text(json.dumps({
                "response": final_text,
                "curves": [curve.control_points for curve in final_curves],
                "score": final_score,
                "evidence": final_evidence,
                "experiences_used": self.experiences,
            }, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            history.append({"final_generation_error": str(exc), "fallback": "best_learning_candidate"})

        history.append({"final_score": final_score, "final_evidence": final_evidence})
        result = Sketch3D(best_curves, prompt, {
            "coordinate_mode": self.coordinate_mode,
            "format": self.output_format,
            "best_learning_score": best_score,
            "final_score": final_score,
            "experiences": self.experiences,
        })
        (self.output_dir / "history.json").write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
        (self.output_dir / "experiences.json").write_text(json.dumps(self.experiences, ensure_ascii=False, indent=2), encoding="utf-8")
        (self.output_dir / "final.json").write_text(result.to_json(), encoding="utf-8")
        return result

    def _extract_experiences(self, prompt: str, best: tuple, worst: tuple) -> list[str]:
        request = EXPERIENCE_PROMPT.format(prompt=prompt, best_score=best[0], best=best[1], worst_score=worst[0], worst=worst[1], limit=2)
        response = self.generator.client.responses.create(
            model=self.model,
            temperature=0,
            input=request,
            max_output_tokens=500,
            **reasoning_options(),
        )
        text = (response.output_text or "").strip().removeprefix("```json").removesuffix("```").strip()
        try:
            if not text.startswith("["):
                text = text[text.find("["):text.rfind("]") + 1]
            values = json.loads(text)
            return [str(value).strip() for value in values if str(value).strip()]
        except Exception:
            return []


class ThreeDDrawerProvider:
    """Provider adapter exposing the training-free 3D drawer to DrawerTool."""

    def __init__(self, output_dir: str | Path = "outputs/3d_drawer", *, coordinate_mode: str = "real",
                 samples: int = 1, epochs: int = 1):
        self.output_dir = Path(output_dir)
        self.coordinate_mode = coordinate_mode
        self.samples = samples
        self.epochs = epochs

    def draw(self, prompt: str, *, model: str, temperature: float = 0.7):
        return TrainingFree3DGRPO(
            model=model,
            coordinate_mode=self.coordinate_mode,
            samples=self.samples,
            temperature=temperature,
            output_dir=self.output_dir,
        ).run(prompt, epochs=self.epochs)
