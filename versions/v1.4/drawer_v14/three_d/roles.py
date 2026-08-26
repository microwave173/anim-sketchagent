from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any, Protocol

from dotenv import load_dotenv

from sketch_agent.model_config import get_reasoning_effort, reasoning_options

from .patch import Path3DPatch, PlannerReview


SPATIAL_CIRCLE_Q3_EXAMPLE_PATH = "M 0.678 0.254 0.339 Q3 0.562 0.564 0.339 0.281 0.709 0.240 Q3 0.000 0.854 0.141 -0.281 0.749 0.000 Q3 -0.562 0.644 -0.141 -0.678 0.350 -0.240 Q3 -0.794 0.056 -0.339 -0.678 -0.254 -0.339 Q3 -0.562 -0.564 -0.339 -0.281 -0.709 -0.240 Q3 0.000 -0.854 -0.141 0.281 -0.749 0.000 Q3 0.562 -0.644 0.141 0.678 -0.350 0.240 Q3 0.794 -0.056 0.339 0.678 0.254 0.339"
SPATIAL_S_CURVE_C3_EXAMPLE_PATH = "M -0.8 -0.5 -0.3 C3 -0.3 0.9 0.6 0.3 -0.9 -0.5 0.8 0.5 0.75"


PATH3D_PLANNER_SYSTEM_PROMPT = """You are the Planner and multiview visual reviewer for one incremental 3D spatial line artifact.
You never write Path3D coordinates. First form a compact 3D structural plan. Then repeatedly inspect the complete Path3D scene and its front, side, top, and perspective renders. Decide one small next goal and tell the Path3D Editor what to add, delete, or replace.
Judge genuine three-dimensional structure: depth separation, shared joints, connectivity, symmetry, proportions, silhouette across all views, and prompt fidelity. A good perspective view is insufficient if side or top view exposes flattened or disconnected geometry. For wheels, rings, rounded bodies, tails, necks, wings, and other organic parts, also judge curve smoothness and flag unnecessary polygonal/faceted approximations when a clean Q3/C3 contour would better express the target. Preserve successful strokes by ID and prefer reversible steps.
Balance beauty, coordination, prompt fidelity, and distinctive identity cues. Diagnose both excessive complexity and excessive simplification. Prefer small reversible steps. Keep enough identity details to make the subject unmistakable, but abstract a detail when literal geometry makes the whole drawing awkward or incoherent.
The Editor can only batch-add and batch-delete whole spatial strokes; replacement means deleting old IDs and adding new IDs in one atomic patch. You may continue, retry, roll back, finish, or fail.
Return only the requested JSON object."""


PATH3D_EDITOR_SYSTEM_PROMPT = f"""You are the incremental Path3D Editor for one 3D spatial line artifact. This is not 2D SVG.
Execute only the Planner's current instruction. You see the complete Path3D scene and every semantic stroke. Return one atomic patch that batch-adds or batch-deletes strokes. You cannot update a stroke in place; replace it by deleting its old ID and adding a new unique ID.

Path3D controls a virtual pen in 3D space:
- M x y z moves without drawing.
- L x y z draws a line.
- Q3 cx cy cz x y z draws a quadratic 3D Bezier. Q3 always has exactly 6 numbers, grouped as [one xyz control], [one xyz endpoint].
- C3 c1x c1y c1z c2x c2y c2z x y z draws a cubic 3D Bezier. C3 always has exactly 9 numbers, grouped as [control 1], [control 2], [endpoint]. Control 1 sets the departure direction; control 2 sets the arrival direction.
- Z closes to the latest M point.
Use uppercase absolute commands. Do not use the 2D SVG commands Q or C.
Balance beauty, coordination, prompt fidelity, and distinctive identity cues. Diagnose both excessive complexity and excessive simplification. Prefer small reversible steps. Keep the complete artifact coordinated; a few clear strokes are better than brittle clutter, but do not remove an identity cue merely to reduce stroke count.
Write Q3 or C3 again before every new curve segment. Never append an incomplete second segment after one command. Include all three coordinates for every control and endpoint, even for a planar curve.

Axes: +x right, +y away/deeper, +z up. Use real coordinates roughly in [-1,1]. Make actual depth explicit and keep shared joints at exactly shared xyz coordinates. Use continuous paths when one pen movement naturally expresses a connected contour, ring, frame, or rail. Add only the few strokes needed for this round and never delete Planner-protected IDs.

Curve choice:
- Prefer Q3 for circular arcs, wheels, rings, rounded cross-sections, and simple one-direction bends.
- Use C3 for S-shaped tails/necks/paths or when departure and arrival directions need independent control.
- Use L only for genuinely straight members; do not replace intended organic curvature with a faceted L chain.

Format-only Q3 example: a smooth closed contour using eight explicit segments. Each segment repeats Q3 and contains [control], [endpoint]:
{SPATIAL_CIRCLE_Q3_EXAMPLE_PATH}

Format-only C3 example: one non-planar spatial S curve containing exactly [control 1], [control 2], [endpoint]:
{SPATIAL_S_CURVE_C3_EXAMPLE_PATH}

Do not copy example content or coordinates unless they fit the current target.
Return only the requested JSON object. Do not return SVG tags, fill, surfaces, meshes, primitives, transforms, or camera commands."""


class Planner3DRole(Protocol):
    def create_plan(self, *, prompt: str) -> dict[str, Any]: ...

    def review(
        self,
        *,
        prompt: str,
        plan: dict[str, Any],
        current_revision: str,
        current_scene: dict[str, Any],
        current_contact_sheet: Path,
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


class Editor3DRole(Protocol):
    def edit(
        self,
        *,
        prompt: str,
        plan: dict[str, Any],
        instruction: dict[str, Any],
        current_scene: dict[str, Any],
        previous_error: str | None,
        previous_patch: dict[str, Any] | None,
    ) -> Path3DPatch: ...


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


class _Path3DModelRole:
    def __init__(self, *, model: str | None = None, client: Any | None = None) -> None:
        load_dotenv(Path(__file__).resolve().parents[4] / ".env")
        self.model = model or os.getenv("MODEL", "gpt-5.6-terra")
        self.reasoning_effort = get_reasoning_effort()
        if client is None:
            from openai import OpenAI

            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), base_url=os.getenv("BASE_URL"))
        self.client = client

    def _json(self, system: str, content: str | list[dict[str, Any]], *, max_tokens: int) -> dict[str, Any]:
        inputs: list[dict[str, Any]] = [
            {"role": "system", "content": system},
            {"role": "user", "content": content},
        ]
        last_error: Exception | None = None
        for attempt in range(2):
            try:
                response = self.client.responses.create(
                    model=self.model,
                    input=inputs,
                    max_output_tokens=max_tokens,
                    **reasoning_options(self.reasoning_effort),
                )
            except json.JSONDecodeError as exc:
                last_error = exc
                if attempt == 0:
                    continue
                break
            raw = response.output_text or ""
            try:
                return _json_object(raw)
            except (json.JSONDecodeError, ValueError) as exc:
                last_error = exc
                if attempt == 0:
                    inputs.extend([
                        {"role": "assistant", "content": raw},
                        {"role": "user", "content": (
                            f"Your response was not valid JSON: {type(exc).__name__}: {exc}. "
                            "Return the same requested object again as one complete valid JSON object only."
                        )},
                    ])
        raise ValueError(f"3D model/API failed to return valid JSON after 2 attempts: {last_error}")


class ModelPath3DPlanner(_Path3DModelRole):
    def create_plan(self, *, prompt: str) -> dict[str, Any]:
        value = self._json(
            PATH3D_PLANNER_SYSTEM_PROMPT,
            f"""Create the initial incremental 3D spatial drawing plan.
Target: {prompt}
Coordinate system: +x right, +y away/deeper, +z up; preferred range [-1,1].
Return exactly:
{{"structural_strategy":"...","essential_3d_cues":["..."],"joint_constraints":["..."],"view_criteria":{{"front":["..."],"side":["..."],"top":["..."],"perspective":["..."]}},"stages":[{{"stage_id":"...","goal":"...","completion_criteria":["..."]}}],"final_criteria":["..."]}}""",
            max_tokens=2600,
        )
        if not isinstance(value.get("stages"), list) or not value["stages"]:
            raise ValueError("3D planner initial plan requires non-empty stages")
        return value

    def review(
        self,
        *,
        prompt: str,
        plan: dict[str, Any],
        current_revision: str,
        current_scene: dict[str, Any],
        current_contact_sheet: Path,
        history: list[dict[str, Any]],
        last_error: str | None,
        round_index: int,
        max_rounds: int,
    ) -> PlannerReview:
        content: list[dict[str, Any]] = [
            {"type": "input_text", "text": (
                f"Target: {prompt}\nRound: {round_index}/{max_rounds}\nCurrent revision: {current_revision}\n"
                f"Initial 3D plan:\n{json.dumps(plan, ensure_ascii=False)}\n"
                f"Revision history:\n{json.dumps(history, ensure_ascii=False)}\n"
                f"Last patch error: {last_error or 'None'}\n"
                f"Complete current Path3D scene:\n{json.dumps(current_scene, ensure_ascii=False)}\n\n"
                "The contact sheet is ordered front, side, top, perspective. Review all four views. "
                "Return exactly: {\"decision\":\"continue|retry|rollback|finish|fail\",\"assessment\":{\"preserve\":[\"stroke IDs\"],\"structural_problems\":[\"...\"],\"missing_3d_cues\":[\"...\"],\"view_failures\":[\"...\"]},\"instruction\":{\"goal\":\"...\",\"add\":[\"...\"],\"remove_or_replace\":[\"...\"],\"coordinate_constraints\":[\"...\"],\"preserve_stroke_ids\":[\"...\"]},\"rollback_revision\":null,\"reason\":\"...\"}"
            )},
            {"type": "input_image", "image_url": _image_url(current_contact_sheet)},
        ]
        return PlannerReview.from_dict(
            self._json(PATH3D_PLANNER_SYSTEM_PROMPT, content, max_tokens=3000)
        )

    def select_best(
        self,
        *,
        prompt: str,
        plan: dict[str, Any],
        revisions: list[dict[str, Any]],
    ) -> tuple[str, str]:
        if not revisions:
            raise ValueError("cannot select final 3D result without a non-empty revision")
        content: list[dict[str, Any]] = [{"type": "input_text", "text": (
            f"Target: {prompt}\nFinal criteria: {json.dumps(plan.get('final_criteria', []), ensure_ascii=False)}\n"
            "Compare every revision across all four views. Choose the best genuinely 3D structure, not necessarily the latest. "
            "Return exactly: {\"best_revision\":\"revision_NNN\",\"reason\":\"...\"}"
        )}]
        valid_ids = []
        for item in revisions:
            valid_ids.append(item["revision_id"])
            content.extend([
                {"type": "input_text", "text": f"Revision: {item['revision_id']}; stroke_count={item['stroke_count']}"},
                {"type": "input_image", "image_url": _image_url(Path(item["contact_sheet_absolute"]))},
            ])
        result = self._json(PATH3D_PLANNER_SYSTEM_PROMPT, content, max_tokens=1000)
        selected = str(result.get("best_revision", ""))
        if selected not in valid_ids:
            raise ValueError(f"3D planner selected unknown revision: {selected!r}")
        return selected, str(result.get("reason", "")).strip()


class ModelPath3DEditor(_Path3DModelRole):
    def edit(
        self,
        *,
        prompt: str,
        plan: dict[str, Any],
        instruction: dict[str, Any],
        current_scene: dict[str, Any],
        previous_error: str | None,
        previous_patch: dict[str, Any] | None,
    ) -> Path3DPatch:
        request = f"""Target: {prompt}
Initial 3D plan: {json.dumps(plan, ensure_ascii=False)}
Current Planner instruction: {json.dumps(instruction, ensure_ascii=False)}
Previous validation error: {previous_error or 'None'}
Previous invalid patch: {json.dumps(previous_patch, ensure_ascii=False) if previous_patch else 'None'}

Complete current Path3D scene:
{json.dumps(current_scene, ensure_ascii=False)}

Return exactly:
{{"delete_stroke_ids":["existing_id"],"add_strokes":[{{"id":"new_unique_id","path":"M ... L ... Q3 ... C3 ... Z","description":"...","stroke":"#111111","stroke_width":3,"opacity":1,"group":"semantic_group"}}],"summary":"..."}}"""
        return Path3DPatch.from_dict(
            self._json(PATH3D_EDITOR_SYSTEM_PROMPT, request, max_tokens=4200)
        )
