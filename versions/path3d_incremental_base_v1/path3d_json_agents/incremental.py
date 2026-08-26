from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

from drawer_v14.three_d.document import Path3DDocument, Path3DPatchPolicy
from drawer_v14.three_d.patch import PlannerReview
from drawer_v14.three_d.storage import Path3DRevisionStore

from .common import ResponsesRole, image_url, write_json
from .structured_patch import StructuredPath3DPatch


STRUCTURED_PLANNER_SYSTEM_PROMPT = """You are the visual director of an incremental 3D sketch.

Review the target and the front, side, top, and perspective renders. Decide whether to continue, rebuild, finish, roll back, or fail. Give the Editor one high-level objective and visual success criteria.

Do not design curves. Do not specify coordinates, stroke counts, stroke IDs, additions, deletions, or protected parts. The Editor decides how to draw and may preserve, replace, or rebuild any geometry.

Return only the requested JSON object."""


STRUCTURED_EDITOR_SYSTEM_PROMPT = """You are a professional 3D sketch artist editing one complete spatial line drawing.

Output rules:
1. Return one JSON patch with delete_stroke_ids, add_strokes, and summary.
2. Every added stroke has a unique id, description, style, group, and a commands array beginning with M.
3. Points are exactly [x,y,z]. Commands are M, L, Q3, C3, or Z.
4. Existing strokes are replaced by deleting their IDs and adding new IDs in the same patch.

Geometry rules:
1. +x is right, +y is away/deeper, and +z is up. Keep coordinates roughly in [-1,1].
2. Use real depth and exact shared joints. Do not collapse the object onto one plane.
3. Make the main body and target identity dominate the silhouette in all four views.
4. Use enough strokes to express coherent structure, but avoid redundant tiny strokes and clutter.
5. Use Q3 for simple rounded bends, C3 for organic or S-shaped curves, and L for straight structure.
6. Follow the director's objective, but decide the geometry, interpretation, stroke count, and whether a local edit or broad rebuild is needed.

Valid command example:
[{"command":"M","point":[-0.8,0,0]},{"command":"C3","control_1":[-0.3,0.5,0.4],"control_2":[0.3,-0.5,0.2],"end":[0.8,0,0]}]

Return only:
{"delete_stroke_ids":["existing_id"],"add_strokes":[{"id":"new_unique_id","commands":[...],"description":"...","stroke":"#111111","stroke_width":3,"opacity":1,"group":"component"}],"summary":"..."}
Never return flat path strings, SVG, surfaces, meshes, primitives, transforms, or camera commands."""


class StructuredPlannerRole:
    def create_plan(self, *, prompt: str) -> dict[str, Any]:
        raise NotImplementedError

    def review(self, **kwargs: Any) -> PlannerReview:
        raise NotImplementedError

    def select_best(self, **kwargs: Any) -> tuple[str, str]:
        raise NotImplementedError


class ModelStructuredPlanner(ResponsesRole):
    def create_plan(self, *, prompt: str) -> dict[str, Any]:
        value, _ = self.call_json(
            system=STRUCTURED_PLANNER_SYSTEM_PROMPT,
            content=(
                f"Target: {prompt}\n"
                "Return {\"overall_goal\":\"...\",\"priorities\":[\"...\"],"
                "\"completion_criteria\":[\"...\"]}. Keep it visual and high-level."
            ),
            max_tokens=900,
        )
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
        content = [
            {"type": "input_text", "text": (
                f"Target: {prompt}\nRound: {round_index}/{max_rounds}\nRevision: {current_revision}\n"
                f"Plan: {json.dumps(plan, ensure_ascii=False)}\n"
                f"History summary: {json.dumps(history, ensure_ascii=False)}\n"
                f"Last validation error: {last_error or 'None'}\n"
                "The contact sheet is front, side, top, perspective. Return "
                "{\"decision\":\"continue|retry|rollback|finish|fail\","
                "\"assessment\":{\"strengths\":[\"...\"],\"problems\":[\"...\"]},"
                "\"instruction\":{\"objective\":\"...\",\"priority\":\"...\","
                "\"success_criteria\":[\"...\"],\"scope\":\"optional high-level scope\"},"
                "\"rollback_revision\":null,\"reason\":\"...\"}. "
                "For continue/retry, instruction is required. Use at most 2 strengths, 3 problems, and 3 success criteria; "
                "keep each item to one short sentence. Do not prescribe drawing operations."
            )},
            {"type": "input_image", "image_url": image_url(current_contact_sheet)},
        ]
        value, _ = self.call_json(
            system=STRUCTURED_PLANNER_SYSTEM_PROMPT, content=content, max_tokens=2600, vision=True,
        )
        self._validate_directive(value)
        return PlannerReview.from_dict(value)

    @staticmethod
    def _validate_directive(value: dict[str, Any]) -> None:
        instruction = value.get("instruction")
        if not isinstance(instruction, dict):
            return
        forbidden = {
            "add", "remove", "remove_or_replace", "coordinate_constraints",
            "preserve_stroke_ids", "delete_stroke_ids", "add_strokes", "stroke_count",
        }
        found = sorted(forbidden & set(instruction))
        if found:
            raise ValueError("planner crossed the drawing boundary: " + ", ".join(found))
        allowed = {"objective", "priority", "success_criteria", "scope"}
        unexpected = sorted(set(instruction) - allowed)
        if unexpected:
            raise ValueError("planner instruction has unsupported fields: " + ", ".join(unexpected))
        if "scope" in instruction and not str(instruction["scope"]).strip():
            raise ValueError("planner instruction scope must be non-empty when provided")

    def select_best(self, *, prompt: str, plan: dict[str, Any], revisions: list[dict[str, Any]]) -> tuple[str, str]:
        if not revisions:
            raise ValueError("cannot select without revisions")
        content: list[dict[str, Any]] = [{"type": "input_text", "text": (
            f"Target: {prompt}\nPlan: {json.dumps(plan, ensure_ascii=False)}\n"
            "Choose the best historical revision by visible recognizability, structure, proportions, and four-view consistency. "
            "Return {\"best_revision\":\"revision_NNN\",\"reason\":\"...\"}."
        )}]
        valid = set()
        for item in revisions:
            valid.add(item["revision_id"])
            content.extend([
                {"type": "input_text", "text": f"Revision: {item['revision_id']}"},
                {"type": "input_image", "image_url": image_url(Path(item["contact_sheet_absolute"]))},
            ])
        value, _ = self.call_json(
            system=STRUCTURED_PLANNER_SYSTEM_PROMPT, content=content, max_tokens=900, vision=True,
        )
        selected = str(value.get("best_revision", ""))
        if selected not in valid:
            raise ValueError(f"planner selected unknown revision: {selected!r}")
        return selected, str(value.get("reason", "")).strip()


class StructuredPatchParseError(ValueError):
    def __init__(self, message: str, *, raw: str, value: dict[str, Any]) -> None:
        super().__init__(message)
        self.raw = raw
        self.value = value


class StructuredPatchEditor(ResponsesRole):
    def edit(
        self,
        *,
        prompt: str,
        plan: dict[str, Any],
        instruction: dict[str, Any],
        current_scene: dict[str, Any],
        current_contact_sheet: Path,
        previous_error: str | None,
        previous_patch: dict[str, Any] | None,
    ) -> tuple[StructuredPath3DPatch, str]:
        content = [
            {"type": "input_text", "text": f"""Target: {prompt}
High-level plan: {json.dumps(plan, ensure_ascii=False)}
Director objective: {json.dumps(instruction, ensure_ascii=False)}
Previous validation error: {previous_error or 'None'}
Previous invalid patch: {json.dumps(previous_patch, ensure_ascii=False) if previous_patch else 'None'}
Complete current scene: {json.dumps(current_scene, ensure_ascii=False)}
The contact sheet is front, side, top, perspective. Interpret the target and decide the drawing solution yourself. Return one atomic patch."""},
            {"type": "input_image", "image_url": image_url(current_contact_sheet)},
        ]
        value, raw = self.call_json(
            system=STRUCTURED_EDITOR_SYSTEM_PROMPT, content=content, max_tokens=8000, vision=True,
        )
        try:
            return StructuredPath3DPatch.from_dict(value), raw
        except Exception as exc:
            raise StructuredPatchParseError(str(exc), raw=raw, value=value) from exc


@dataclass(frozen=True)
class StructuredIncrementalResult:
    status: str
    best_revision: str | None
    best_preview: Path | None
    rounds_completed: int
    trajectory_path: Path
    plan_path: Path
    reason: str
    run_wall_seconds: float


class StructuredIncrementalPath3DLoop:
    def __init__(
        self,
        *,
        output_dir: str | Path,
        planner: StructuredPlannerRole | None = None,
        editor: StructuredPatchEditor | None = None,
        model: str | None = None,
        vision_model: str | None = None,
        client: Any | None = None,
        max_rounds: int = 8,
        max_patch_attempts: int = 3,
        max_additions_per_patch: int = 48,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.planner = planner or ModelStructuredPlanner(
            model=model, vision_model=vision_model or model, client=client,
        )
        self.editor = editor or StructuredPatchEditor(model=model, vision_model=vision_model, client=client)
        self.max_rounds = max(1, max_rounds)
        self.max_patch_attempts = max(1, max_patch_attempts)
        patch_budget = max(1, max_additions_per_patch)
        self.policy = Path3DPatchPolicy(
            max_additions=patch_budget,
            max_deletions=patch_budget,
        )

    def run(self, prompt: str, *, width: int = 512, height: int = 512) -> StructuredIncrementalResult:
        started = perf_counter()
        if not prompt.strip():
            raise ValueError("prompt cannot be empty")
        if self.output_dir.exists():
            raise FileExistsError(f"output already exists: {self.output_dir}")
        store = Path3DRevisionStore(self.output_dir, width=width, height=height)
        active_revision = store.initialize(prompt=prompt).revision_id
        plan = self.planner.create_plan(prompt=prompt)
        plan_path = self.output_dir / "plan.json"
        trajectory_path = self.output_dir / "trajectory.json"
        write_json(plan_path, plan)
        trajectory: list[dict[str, Any]] = []
        last_error: str | None = None
        status, terminal_reason = "max_rounds", "maximum rounds reached"

        for round_index in range(1, self.max_rounds + 1):
            document = store.load_document(active_revision)
            review = self.planner.review(
                prompt=prompt, plan=plan, current_revision=active_revision,
                current_scene=document.to_dict(), current_contact_sheet=store.contact_sheet_path(active_revision),
                history=[item.to_dict() for item in store.records()], last_error=last_error,
                round_index=round_index, max_rounds=self.max_rounds,
            )
            round_dir = self.output_dir / "rounds" / f"round_{round_index:02d}"
            round_dir.mkdir(parents=True, exist_ok=True)
            write_json(round_dir / "planner_review.json", review.to_dict())
            event: dict[str, Any] = {"round": round_index, "active_revision_before": active_revision, "planner_review": review.to_dict()}
            if review.decision == "rollback":
                target = review.rollback_revision or ""
                if target not in store.records_by_id():
                    raise ValueError(f"planner requested unknown rollback revision: {target}")
                active_revision, last_error = target, None
                event["active_revision_after"] = active_revision
                trajectory.append(event)
                write_json(trajectory_path, trajectory)
                continue
            if review.decision in {"finish", "fail"}:
                status = "complete" if review.decision == "finish" else "failed"
                terminal_reason = review.reason or f"planner decided {review.decision}"
                trajectory.append(event)
                write_json(trajectory_path, trajectory)
                break

            instruction = review.instruction or {}
            protected_ids: tuple[str, ...] = ()
            previous_structured: dict[str, Any] | None = None
            attempts: list[dict[str, Any]] = []
            patch_applied = False
            for attempt in range(1, self.max_patch_attempts + 1):
                raw = ""
                try:
                    structured, raw = self.editor.edit(
                        prompt=prompt, plan=plan, instruction=instruction,
                        current_scene=document.to_dict(),
                        current_contact_sheet=store.contact_sheet_path(active_revision),
                        previous_error=last_error,
                        previous_patch=previous_structured,
                    )
                    structured_value = structured.to_dict()
                    compiled = structured.compile(prompt=prompt)
                    validation = document.validate_patch(compiled, self.policy, protected_ids=protected_ids)
                    errors = list(validation.errors)
                except Exception as exc:
                    raw = str(getattr(exc, "raw", raw))
                    structured_value = getattr(exc, "value", previous_structured or {})
                    compiled = None
                    validation = None
                    errors = [f"{type(exc).__name__}: {exc}"]
                attempt_record = {
                    "attempt": attempt,
                    "structured_patch": structured_value,
                    "compiled_patch": compiled.to_dict() if compiled else None,
                    "validation": {"valid": not errors, "errors": errors},
                }
                attempts.append(attempt_record)
                write_json(round_dir / f"editor_attempt_{attempt:02d}.json", attempt_record)
                (round_dir / f"editor_attempt_{attempt:02d}_raw.txt").write_text(raw, encoding="utf-8")
                if not errors and compiled is not None:
                    updated = document.apply_patch(compiled, self.policy, protected_ids=protected_ids)
                    record = store.commit(updated, parent=active_revision, round_index=round_index, patch=compiled)
                    revision_dir = self.output_dir / "revisions" / record.revision_id
                    write_json(revision_dir / "structured_patch.json", structured_value)
                    active_revision, last_error, patch_applied = record.revision_id, None, True
                    event["committed_revision"] = record.to_dict()
                    break
                last_error = "; ".join(errors)
                previous_structured = structured_value
            event.update({"editor_attempts": attempts, "patch_applied": patch_applied, "active_revision_after": active_revision})
            if not patch_applied:
                event["error"] = last_error
            trajectory.append(event)
            write_json(trajectory_path, trajectory)

        revisions = [{**record.to_dict(), "contact_sheet_absolute": str(store.contact_sheet_path(record.revision_id).resolve())}
                     for record in store.records() if record.stroke_count]
        best_revision: str | None = None
        best_preview: Path | None = None
        final_reason = terminal_reason
        if revisions:
            best_revision, selected_reason = self.planner.select_best(prompt=prompt, plan=plan, revisions=revisions)
            final_reason = selected_reason or terminal_reason
            best_record = store.records_by_id()[best_revision]
            best_preview = store.contact_sheet_path(best_revision)
            final_dir = self.output_dir / "final"
            final_dir.mkdir()
            shutil.copy2(self.output_dir / best_record.scene_path, final_dir / "scene.json")
            shutil.copytree(self.output_dir / best_record.views_dir, final_dir / "views")
            source_structured = self.output_dir / "revisions" / best_revision / "structured_patch.json"
            if source_structured.exists():
                shutil.copy2(source_structured, final_dir / "last_structured_patch.json")
            write_json(self.output_dir / "final_selection.json", {
                "status": status, "best_revision": best_revision, "reason": final_reason,
                "active_revision_at_stop": active_revision,
                "final_artifact": {"scene": "final/scene.json", "views": "final/views", "preview": "final/views/contact_sheet.png"},
            })
        else:
            status, final_reason = "failed", "no non-empty revision was produced"
            write_json(self.output_dir / "final_selection.json", {"status": status, "best_revision": None, "reason": final_reason})
        write_json(self.output_dir / "timings.json", {"run_wall_seconds": perf_counter() - started})
        return StructuredIncrementalResult(status, best_revision, best_preview, len(trajectory), trajectory_path, plan_path, final_reason, perf_counter() - started)
