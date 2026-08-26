from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

from .document import Path3DDocument, Path3DPatchPolicy
from .patch import Path3DPatch
from .roles import Editor3DRole, ModelPath3DEditor, ModelPath3DPlanner, Planner3DRole
from .storage import Path3DRevisionStore


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


@dataclass(frozen=True)
class Path3DRunResult:
    status: str
    best_revision: str | None
    best_preview: Path | None
    rounds_completed: int
    trajectory_path: Path
    plan_path: Path
    reason: str
    run_wall_seconds: float


class IncrementalPath3DLoop:
    def __init__(
        self,
        *,
        output_dir: str | Path,
        planner: Planner3DRole | None = None,
        editor: Editor3DRole | None = None,
        model: str | None = None,
        max_rounds: int = 8,
        max_patch_attempts: int = 3,
        max_additions_per_patch: int = 6,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.planner = planner or ModelPath3DPlanner(model=model)
        self.editor = editor or ModelPath3DEditor(model=model)
        self.max_rounds = max(1, max_rounds)
        self.max_patch_attempts = max(1, max_patch_attempts)
        self.policy = Path3DPatchPolicy(max_additions=max(1, max_additions_per_patch))

    def run(self, prompt: str, *, width: int = 512, height: int = 512) -> Path3DRunResult:
        started = perf_counter()
        if not prompt.strip():
            raise ValueError("prompt cannot be empty")
        if not 64 <= width <= 4096 or not 64 <= height <= 4096:
            raise ValueError("canvas dimensions must be between 64 and 4096")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        store = Path3DRevisionStore(self.output_dir, width=width, height=height)
        initial = store.initialize(prompt=prompt)
        active_revision = initial.revision_id
        plan = self.planner.create_plan(prompt=prompt)
        plan_path = self.output_dir / "plan.json"
        trajectory_path = self.output_dir / "trajectory.json"
        _write_json(plan_path, plan)
        trajectory: list[dict[str, Any]] = []
        last_error: str | None = None
        status = "max_rounds"
        terminal_reason = "maximum rounds reached"

        for round_index in range(1, self.max_rounds + 1):
            document = store.load_document(active_revision)
            review = self.planner.review(
                prompt=prompt,
                plan=plan,
                current_revision=active_revision,
                current_scene=document.to_dict(),
                current_contact_sheet=store.contact_sheet_path(active_revision),
                history=[item.to_dict() for item in store.records()],
                last_error=last_error,
                round_index=round_index,
                max_rounds=self.max_rounds,
            )
            round_dir = self.output_dir / "rounds" / f"round_{round_index:02d}"
            round_dir.mkdir(parents=True, exist_ok=True)
            _write_json(round_dir / "planner_review.json", review.to_dict())
            event: dict[str, Any] = {
                "round": round_index,
                "active_revision_before": active_revision,
                "planner_review": review.to_dict(),
            }
            if review.decision == "rollback":
                target = review.rollback_revision or ""
                if target not in store.records_by_id():
                    raise ValueError(f"planner requested unknown rollback revision: {target}")
                active_revision = target
                last_error = None
                event["active_revision_after"] = active_revision
                trajectory.append(event)
                _write_json(trajectory_path, trajectory)
                continue
            if review.decision == "finish":
                status = "complete"
                terminal_reason = review.reason or "3D planner finished"
                trajectory.append(event)
                _write_json(trajectory_path, trajectory)
                break
            if review.decision == "fail":
                status = "failed"
                terminal_reason = review.reason or "3D planner reported failure"
                trajectory.append(event)
                _write_json(trajectory_path, trajectory)
                break

            instruction = review.instruction or {}
            protected_ids = tuple(str(item) for item in instruction.get("preserve_stroke_ids", []))
            previous_patch: dict[str, Any] | None = None
            patch_applied = False
            attempts: list[dict[str, Any]] = []
            for attempt in range(1, self.max_patch_attempts + 1):
                patch = self.editor.edit(
                    prompt=prompt,
                    plan=plan,
                    instruction=instruction,
                    current_scene=document.to_dict(),
                    previous_error=last_error,
                    previous_patch=previous_patch,
                )
                validation = document.validate_patch(patch, self.policy, protected_ids=protected_ids)
                attempt_record = {
                    "attempt": attempt,
                    "patch": patch.to_dict(),
                    "validation": {"valid": validation.valid, "errors": list(validation.errors)},
                }
                attempts.append(attempt_record)
                _write_json(round_dir / f"editor_attempt_{attempt:02d}.json", attempt_record)
                if validation.valid:
                    updated = document.apply_patch(patch, self.policy, protected_ids=protected_ids)
                    record = store.commit(updated, parent=active_revision, round_index=round_index, patch=patch)
                    active_revision = record.revision_id
                    last_error = None
                    patch_applied = True
                    event["committed_revision"] = record.to_dict()
                    break
                last_error = "; ".join(validation.errors)
                previous_patch = patch.to_dict()
            event["editor_attempts"] = attempts
            event["patch_applied"] = patch_applied
            event["active_revision_after"] = active_revision
            if not patch_applied:
                event["error"] = last_error
            trajectory.append(event)
            _write_json(trajectory_path, trajectory)

        nonempty = [{
            **record.to_dict(),
            "contact_sheet_absolute": str(store.contact_sheet_path(record.revision_id).resolve()),
        } for record in store.records() if record.stroke_count]
        best_revision: str | None = None
        best_preview: Path | None = None
        final_reason = terminal_reason
        if nonempty:
            best_revision, selection_reason = self.planner.select_best(
                prompt=prompt, plan=plan, revisions=nonempty,
            )
            final_reason = selection_reason or terminal_reason
            best_record = store.records_by_id()[best_revision]
            best_preview = store.contact_sheet_path(best_revision)
            final_dir = self.output_dir / "final"
            final_dir.mkdir(exist_ok=True)
            shutil.copy2(self.output_dir / best_record.scene_path, final_dir / "scene.json")
            shutil.copytree(self.output_dir / best_record.views_dir, final_dir / "views")
            _write_json(self.output_dir / "final_selection.json", {
                "status": status,
                "best_revision": best_revision,
                "reason": final_reason,
                "active_revision_at_stop": active_revision,
                "final_artifact": {"scene": "final/scene.json", "views": "final/views", "preview": "final/views/contact_sheet.png"},
            })
        else:
            status = "failed"
            final_reason = "no non-empty Path3D revision was produced"
            _write_json(self.output_dir / "final_selection.json", {
                "status": status, "best_revision": None, "reason": final_reason,
            })
        return Path3DRunResult(
            status, best_revision, best_preview, len(trajectory), trajectory_path,
            plan_path, final_reason, perf_counter() - started,
        )
