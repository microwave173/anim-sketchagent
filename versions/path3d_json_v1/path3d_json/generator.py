from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from sketch_agent.model_config import get_reasoning_effort, reasoning_options

from .schema import StructuredScene


SYSTEM_PROMPT = """You are a 3D spatial sketch artist. Draw by moving a virtual pen through three-dimensional space, but return structured JSON commands instead of a flat path string.

Balance beauty, coordination, prompt fidelity, and distinctive identity cues. Diagnose both excessive complexity and excessive simplification. Prefer small reversible steps. Preserve the minimum distinctive details that make the requested subject recognizable while using clean abstract curves when literal detail would harm coordination.

World axes: +x points right, +y points away/deeper into the scene, and +z points up. Use finite real coordinates roughly in [-1,1]. Different strokes may meet by using exactly identical [x,y,z] joint coordinates.

Every coordinate or control point is one JSON array containing exactly three numbers: [x,y,z]. Never flatten several points into one numeric list.

Commands:
- {"command":"M","point":[x,y,z]} moves the pen without drawing.
- {"command":"L","point":[x,y,z]} draws a straight line.
- {"command":"Q3","control":[cx,cy,cz],"end":[x,y,z]} draws one quadratic 3D Bezier.
- {"command":"C3","control_1":[c1x,c1y,c1z],"control_2":[c2x,c2y,c2z],"end":[x,y,z]} draws one cubic 3D Bezier.
- {"command":"Z"} closes the latest subpath to its latest M point.

Each stroke must begin with M. To start another disconnected subpath inside the same semantic stroke, add another M object. Each curved segment is a separate Q3 or C3 object, so parameter counts cannot be shared between commands.

Curve choice:
- Prefer Q3 for circular arcs, wheels, rings, rounded cross-sections, and simple one-direction bends.
- Use C3 for S-shaped bodies, tails, necks, flight paths, or when departure and arrival directions need independent control.
- Use L only for genuinely straight structural members. Do not approximate intended organic curvature with a faceted chain of lines.

Format-only Q3 closed-contour fragment:
[{"command":"M","point":[1,0,0]},{"command":"Q3","control":[1,0.55,0.2],"end":[0.7,0.7,0.3]},{"command":"Q3","control":[0.55,1,0.2],"end":[0,1,0]},{"command":"Z"}]

Format-only non-planar C3 S curve:
[{"command":"M","point":[-0.8,-0.5,-0.3]},{"command":"C3","control_1":[-0.3,0.9,0.6],"control_2":[0.3,-0.9,-0.5],"end":[0.8,0.5,0.75]}]

Examples demonstrate syntax only. Do not copy their subject or coordinates unless appropriate.

Return only one valid JSON object with this structure:
{"prompt":"...","strokes":[{"id":"unique_id","commands":[{"command":"M","point":[0,0,0]},{"command":"L","point":[1,0,0]}],"description":"...","stroke":"#111111","stroke_width":3,"opacity":1,"group":"component"}],"metadata":{}}

Do not return a path string, SVG tags, markdown fences, fill, surfaces, meshes, primitives, transforms, or camera commands."""


def _json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip().removeprefix("```json").removesuffix("```").strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start < 0 or end < start:
        raise ValueError("model returned no JSON object")
    value = json.loads(cleaned[start:end + 1])
    if not isinstance(value, dict):
        raise ValueError("model response must be a JSON object")
    return value


class StructuredPath3DGenerator:
    def __init__(self, *, model: str | None = None, client: Any | None = None) -> None:
        load_dotenv(Path(__file__).resolve().parents[3] / ".env")
        self.model = model or os.getenv("MODEL", "gpt-5.6-terra")
        self.reasoning_effort = get_reasoning_effort()
        if client is None:
            from openai import OpenAI

            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), base_url=os.getenv("BASE_URL"))
        self.client = client

    def generate_raw(self, prompt: str) -> str:
        response = self.client.responses.create(
            model=self.model,
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Draw this as a coherent structured 3D spatial line sketch: {prompt}"},
            ],
            max_output_tokens=7000,
            **reasoning_options(self.reasoning_effort),
        )
        return response.output_text or ""

    def parse_response(self, raw: str, *, prompt: str) -> StructuredScene:
        return StructuredScene.from_dict(_json_object(raw), prompt=prompt)
