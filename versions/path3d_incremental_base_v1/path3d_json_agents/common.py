from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from sketch_agent.model_config import get_reasoning_effort, reasoning_options


def json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip().removeprefix("```json").removesuffix("```").strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start < 0 or end < start:
        raise ValueError(f"model returned no JSON object: {text[:300]}")
    value = json.loads(cleaned[start:end + 1])
    if not isinstance(value, dict):
        raise ValueError("model response must be a JSON object")
    return value


def image_url(path: Path) -> str:
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


class ResponsesRole:
    def __init__(self, *, model: str | None = None, vision_model: str | None = None, client: Any | None = None) -> None:
        load_dotenv(Path(__file__).resolve().parents[3] / ".env")
        self.model = model or os.getenv("MODEL", "gpt-5.6-terra")
        self.vision_model = vision_model or os.getenv("VISION_MODEL", self.model)
        self.reasoning_effort = get_reasoning_effort()
        if client is None:
            from openai import OpenAI

            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), base_url=os.getenv("BASE_URL"))
        self.client = client

    def call(
        self,
        *,
        system: str,
        content: str | list[dict[str, Any]],
        max_tokens: int,
        vision: bool = False,
    ) -> str:
        response = self.client.responses.create(
            model=self.vision_model if vision else self.model,
            input=[{"role": "system", "content": system}, {"role": "user", "content": content}],
            max_output_tokens=max_tokens,
            **reasoning_options(self.reasoning_effort),
        )
        return response.output_text or ""

    def call_json(
        self,
        *,
        system: str,
        content: str | list[dict[str, Any]],
        max_tokens: int,
        vision: bool = False,
    ) -> tuple[dict[str, Any], str]:
        messages = content
        last_error: Exception | None = None
        raw = ""
        for attempt in range(2):
            raw = self.call(system=system, content=messages, max_tokens=max_tokens, vision=vision)
            try:
                return json_object(raw), raw
            except (ValueError, json.JSONDecodeError) as exc:
                last_error = exc
                if attempt == 0:
                    repair_text = (
                        "Repair the JSON below without changing its intended content. "
                        f"Parser error: {type(exc).__name__}: {exc}\n\n"
                        f"Invalid response:\n{raw}\n\n"
                        "Return one complete valid JSON object only."
                    )
                    if isinstance(content, str):
                        messages = content + "\n\n" + repair_text
                    else:
                        messages = list(content) + [{
                            "type": "input_text",
                            "text": repair_text,
                        }]
        raise ValueError(f"model failed to return valid JSON after 2 attempts: {last_error}; raw={raw[:300]}")
