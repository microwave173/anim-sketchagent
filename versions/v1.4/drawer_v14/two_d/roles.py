from __future__ import annotations

import base64
import json
import os
import time
from pathlib import Path
from typing import Any, Protocol

from dotenv import load_dotenv

from sketch_agent.model_config import get_reasoning_effort, reasoning_options

from .schema import PlannerReview, StrokePatch


PLANNER_SYSTEM_PROMPT = """You are the Planner and visual reviewer for one incremental 2D SVG artifact.
You never write SVG paths. First form a compact visual plan. Then repeatedly inspect the complete current rendering and SVG, decide the next small drawing goal, and tell the Editor what to add, delete, or replace.
Balance beauty, coordination, prompt fidelity, and distinctive identity cues. Diagnose both excessive complexity and excessive simplification. Preserve successful strokes by ID. Prefer small reversible steps. You may continue, retry a failed goal, roll back to an earlier revision, finish, or fail.
The Editor can only batch-add and batch-delete whole strokes; replacement means deleting old IDs and adding new IDs in one atomic patch.
For cute character faces, default to short vertical-line eyes or simple small bean/dot eyes. Keep them understated and coordinated with the face; use another eye design when the target explicitly requires it.
Return only the requested JSON object."""


EDITOR_SYSTEM_PROMPT = """You are the incremental SVG Editor for one artifact.
Execute only the Planner's current instruction. You can see the complete current SVG including every path ID and description. Return one atomic batch patch that adds strokes, deletes strokes, or does both. You cannot update a stroke in place: replace it by deleting its old ID and adding a new unique ID.
Use clean SVG path data in the given pixel canvas. Keep geometry in bounds. Never delete a stroke the Planner asked to preserve. Add only the few strokes needed for this round; do not redraw the entire artifact unless explicitly instructed. Every added stroke needs a unique semantic ID and concise description.
For cute character faces, default to short vertical-line eyes or simple small bean/dot eyes. Keep them understated and coordinated with the face; use another eye design when the target explicitly requires it.
Return only the requested JSON object."""

PLANNER_DEFAULT_STYLE = """
Default visual language: clean black line art on white, fill="none", restrained stroke count, consistent line weight, and coordinated negative space. Use color, solid fills, shading, or large detailed eyes only when the user's request explicitly asks for them."""

EDITOR_DEFAULT_STYLE = """
Default to black line art: stroke="#111111", fill="none", opacity=1, and a consistent moderate stroke width. Do not introduce color, solid fills, shading, or large detailed eyes unless the target explicitly requests them."""

OUTLINE_ONLY_CONSTRAINT = """
Hard rendering constraint for this run: every SVG stroke must have fill="none". Visible color may be used only for stroke lines. Do not simulate fills with dense hatching or many adjacent strokes. Apart from the prohibition on fills, choose the visual design freely to maximize beauty, coordination, prompt fidelity, and distinctive identity."""


class PlannerRole(Protocol):
    def create_plan(self, *, prompt: str, width: int, height: int) -> dict[str, Any]: ...

    def review(
        self,
        *,
        prompt: str,
        plan: dict[str, Any],
        current_revision: str,
        current_svg: str,
        current_preview: Path,
        history: list[dict[str, Any]],
        last_error: str | None,
        round_index: int,
        max_rounds: int,
    ) -> PlannerReview: ...

    def select_best(
        self,
        *,
        prompt: str,
        plan: dict[str, Any],
        revisions: list[dict[str, Any]],
    ) -> tuple[str, str]: ...


class EditorRole(Protocol):
    def edit(
        self,
        *,
        prompt: str,
        plan: dict[str, Any],
        instruction: dict[str, Any],
        current_svg: str,
        width: int,
        height: int,
        previous_error: str | None,
        previous_patch: dict[str, Any] | None,
    ) -> StrokePatch: ...


def _json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip().removeprefix("```json").removesuffix("```").strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start < 0 or end < start:
        raise ValueError(f"model returned no JSON object: {text[:300]}")
    value = json.loads(cleaned[start:end + 1])
    if not isinstance(value, dict):
        raise ValueError("model response must be a JSON object")
    return value


def _image_url(path: Path) -> str:
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


class _ModelRole:
    def __init__(
        self,
        *,
        model: str | None = None,
        client: Any | None = None,
        outline_only: bool = False,
    ) -> None:
        load_dotenv(Path(__file__).resolve().parents[4] / ".env")
        self.model = model or os.getenv("MODEL", "gpt-5.6-terra")
        self.outline_only = outline_only
        self.reasoning_effort = get_reasoning_effort()
        if client is None:
            from openai import OpenAI

            client = OpenAI(
                api_key=os.getenv("OPENAI_API_KEY"),
                base_url=os.getenv("BASE_URL"),
                timeout=float(os.getenv("SKETCH_API_TIMEOUT", "120")),
                max_retries=0,
            )
        self.client = client

    def _system_prompt(self, base: str) -> str:
        if self.outline_only:
            return base + OUTLINE_ONLY_CONSTRAINT
        default_style = PLANNER_DEFAULT_STYLE if base == PLANNER_SYSTEM_PROMPT else EDITOR_DEFAULT_STYLE
        return base + default_style

    def _json(self, system: str, content: str | list[dict[str, Any]], *, max_tokens: int = 2400) -> dict[str, Any]:
        inputs: list[dict[str, Any]] = [
            {"role": "system", "content": system},
            {"role": "user", "content": content},
        ]
        last_error: Exception | None = None

        def chat_messages() -> list[dict[str, Any]]:
            messages = []
            for item in inputs:
                blocks = item.get("content", [])
                if isinstance(blocks, str):
                    blocks = [{"type": "input_text", "text": blocks}]
                translated = []
                for block in blocks:
                    if block.get("type") == "input_text":
                        translated.append({"type": "text", "text": block.get("text", "")})
                    elif block.get("type") == "input_image":
                        translated.append({"type": "image_url", "image_url": {"url": block["image_url"]}})
                messages.append({"role": item["role"], "content": translated})
            return messages

        def model_text() -> str:
            deepseek = self.model.lower().startswith("deepseek")
            budgets = [max(max_tokens, 12000), 24000, 48000] if deepseek else [max_tokens]
            response_errors = []
            for budget in dict.fromkeys(budgets):
                try:
                    response = self.client.responses.create(
                        model=self.model, input=inputs, max_output_tokens=budget,
                        **reasoning_options(self.reasoning_effort),
                    )
                except Exception as exc:
                    response_errors.append(f"budget={budget}: {type(exc).__name__}: {exc}")
                    break
                raw = (response.output_text or "").strip()
                if raw:
                    return raw
                reason = getattr(getattr(response, "incomplete_details", None), "reason", None)
                response_errors.append(f"budget={budget}: empty output_text (incomplete={reason})")

            chat_errors = []
            for budget in dict.fromkeys(budgets):
                try:
                    response = self.client.chat.completions.create(
                        model=self.model, messages=chat_messages(), max_tokens=budget,
                    )
                except Exception as exc:
                    chat_errors.append(f"budget={budget}: {type(exc).__name__}: {exc}")
                    break
                raw = ((response.choices[0].message.content or "") if response.choices else "").strip()
                if raw:
                    return raw
                chat_errors.append(f"budget={budget}: empty message content")
            raise RuntimeError(
                "model returned no usable JSON text with thinking enabled; "
                f"responses={response_errors}; chat={chat_errors}"
            )

        for attempt in range(3):
            try:
                raw = model_text()
            except Exception as exc:
                last_error = exc
                if attempt < 2:
                    time.sleep(1)
                    continue
                break
            try:
                return _json_object(raw)
            except (json.JSONDecodeError, ValueError) as exc:
                last_error = exc
                if attempt < 2:
                    inputs.extend([
                        {"role": "assistant", "content": raw},
                        {"role": "user", "content": (
                            f"Your response was not valid JSON: {type(exc).__name__}: {exc}. "
                            "Return the same requested object again as one complete valid JSON object only."
                        )},
                    ])
                    continue
        raise ValueError(f"2D model/API failed to return valid JSON after 2 attempts: {last_error}")


class ModelPlanner(_ModelRole):
    def create_plan(self, *, prompt: str, width: int, height: int) -> dict[str, Any]:
        value = self._json(
            self._system_prompt(PLANNER_SYSTEM_PROMPT),
            f"""Create the initial incremental drawing plan.
Target: {prompt}
Canvas: {width} x {height}, origin top-left, x right, y down.
Return exactly:
{{"visual_strategy":"...","essential_cues":["..."],"optional_details":["..."],"abstraction_strategy":["..."],"stages":[{{"stage_id":"...","goal":"...","completion_criteria":["..."]}}],"final_criteria":["..."]}}""",
        )
        if not isinstance(value.get("stages"), list) or not value["stages"]:
            raise ValueError("planner initial plan requires non-empty stages")
        return value

    def review(
        self,
        *,
        prompt: str,
        plan: dict[str, Any],
        current_revision: str,
        current_svg: str,
        current_preview: Path,
        history: list[dict[str, Any]],
        last_error: str | None,
        round_index: int,
        max_rounds: int,
    ) -> PlannerReview:
        content: list[dict[str, Any]] = [
            {"type": "input_text", "text": (
                f"Target: {prompt}\nRound: {round_index}/{max_rounds}\nCurrent revision: {current_revision}\n"
                f"Initial plan:\n{json.dumps(plan, ensure_ascii=False)}\n"
                f"Revision history summary:\n{json.dumps(history, ensure_ascii=False)}\n"
                f"Last patch error: {last_error or 'None'}\n\nComplete current SVG:\n{current_svg}\n\n"
                "Review the actual rendering and choose the next action. For continue/retry, make the instruction small and concrete. "
                "Return exactly: {\"decision\":\"continue|retry|rollback|finish|fail\",\"assessment\":{\"preserve\":[\"stroke IDs or properties\"],\"problems\":[\"...\"],\"missing_high_value_cues\":[\"...\"],\"complexity_to_reduce\":[\"...\"]},\"instruction\":{\"goal\":\"...\",\"add\":[\"...\"],\"remove_or_replace\":[\"...\"],\"constraints\":[\"...\"],\"preserve_stroke_ids\":[\"...\"]},\"rollback_revision\":null,\"preferred_revision\":null,\"reason\":\"...\"}"
            )},
            {"type": "input_image", "image_url": _image_url(current_preview)},
        ]
        return PlannerReview.from_dict(
            self._json(self._system_prompt(PLANNER_SYSTEM_PROMPT), content, max_tokens=2600)
        )

    def select_best(
        self,
        *,
        prompt: str,
        plan: dict[str, Any],
        revisions: list[dict[str, Any]],
    ) -> tuple[str, str]:
        if not revisions:
            raise ValueError("cannot select final result without a non-empty revision")
        content: list[dict[str, Any]] = [{"type": "input_text", "text": (
            f"Target: {prompt}\nFinal criteria: {json.dumps(plan.get('final_criteria', []), ensure_ascii=False)}\n"
            "Compare all historical revisions. Choose the best actual image, not necessarily the latest. "
            "Return exactly: {\"best_revision\":\"revision_NNN\",\"reason\":\"...\"}"
        )}]
        valid_ids = []
        for item in revisions:
            valid_ids.append(item["revision_id"])
            content.extend([
                {"type": "input_text", "text": f"Revision: {item['revision_id']}; stroke_count={item['stroke_count']}"},
                {"type": "input_image", "image_url": _image_url(Path(item["preview_path"]))},
            ])
        result = self._json(self._system_prompt(PLANNER_SYSTEM_PROMPT), content, max_tokens=900)
        selected = str(result.get("best_revision", ""))
        if selected not in valid_ids:
            raise ValueError(f"planner selected unknown final revision: {selected!r}")
        return selected, str(result.get("reason", "")).strip()


class ModelEditor(_ModelRole):
    def edit(
        self,
        *,
        prompt: str,
        plan: dict[str, Any],
        instruction: dict[str, Any],
        current_svg: str,
        width: int,
        height: int,
        previous_error: str | None,
        previous_patch: dict[str, Any] | None,
    ) -> StrokePatch:
        request = f"""Target: {prompt}
Canvas: {width} x {height}; origin top-left; x increases right; y increases down.
Initial plan: {json.dumps(plan, ensure_ascii=False)}
Current Planner instruction: {json.dumps(instruction, ensure_ascii=False)}
Previous validation error: {previous_error or 'None'}
Previous invalid patch: {json.dumps(previous_patch, ensure_ascii=False) if previous_patch else 'None'}

Complete current SVG:
{current_svg}

Return exactly:
{{"delete_stroke_ids":["existing_id"],"add_strokes":[{{"id":"new_unique_id","path":"M ...","description":"...","stroke":"#111111","fill":"none","stroke_width":3,"opacity":1,"group":"semantic_group"}}],"summary":"..."}}"""
        return StrokePatch.from_dict(
            self._json(self._system_prompt(EDITOR_SYSTEM_PROMPT), request, max_tokens=3200)
        )
