from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

from .document import PatchPolicy
from .roles import EditorRole, ModelEditor, ModelPlanner, PlannerRole
from .schema import StrokePatch
from .storage import RevisionStore


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


@dataclass(frozen=True)
class IncrementalRunResult:
    status: str
    best_revision: str | None
    best_preview: Path | None
    rounds_completed: int
    trajectory_path: Path
    plan_path: Path
    reason: str
    run_wall_seconds: float


class IncrementalDrawerLoop:
    def __init__(
        self,
        *,
        output_dir: str | Path,
        planner: PlannerRole | None = None,
        editor: EditorRole | None = None,
        model: str | None = None,
        max_rounds: int = 8,
        max_patch_attempts: int = 3,
        max_additions_per_patch: int = 6,
        outline_only: bool = False,
        sketch_metadata: dict[str, Any] | None = None,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.planner = planner or ModelPlanner(model=model, outline_only=outline_only)
        self.editor = editor or ModelEditor(model=model, outline_only=outline_only)
        self.max_rounds = max(1, max_rounds)
        self.max_patch_attempts = max(1, max_patch_attempts)
        self.sketch_metadata = dict(sketch_metadata or {})
        self.policy = PatchPolicy(
            max_additions=max(1, max_additions_per_patch),
            require_no_fill=outline_only,
        )

    def run(self, prompt: str, *, width: int = 512, height: int = 512) -> IncrementalRunResult:
        started = perf_counter()
        if not prompt.strip():
            raise ValueError("prompt cannot be empty")
        if not 64 <= width <= 4096 or not 64 <= height <= 4096:
            raise ValueError("canvas dimensions must be between 64 and 4096")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        store = RevisionStore(self.output_dir)
        initial = store.initialize(width=width, height=height, metadata=self.sketch_metadata)
        active_revision = initial.revision_id
        plan = self.planner.create_plan(prompt=prompt, width=width, height=height)
        plan_path = self.output_dir / "plan.json"
        trajectory_path = self.output_dir / "trajectory.json"
        _write_json(plan_path, plan)
        trajectory: list[dict[str, Any]] = []
        last_error: str | None = None
        terminal_reason = "maximum rounds reached"
        status = "max_rounds"

        for round_index in range(1, self.max_rounds + 1):
            document = store.load_document(active_revision)
            history_summary = [item.to_dict() for item in store.records()]
            review = self.planner.review(
                prompt=prompt,
                plan=plan,
                current_revision=active_revision,
                current_svg=document.to_svg(),
                current_preview=store.preview_path(active_revision),
                history=history_summary,
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
                terminal_reason = review.reason or "planner finished"
                trajectory.append(event)
                _write_json(trajectory_path, trajectory)
                break
            if review.decision == "fail":
                status = "failed"
                terminal_reason = review.reason or "planner reported failure"
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
                    current_svg=document.to_svg(),
                    width=width,
                    height=height,
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
                    record = store.commit(
                        updated,
                        parent=active_revision,
                        round_index=round_index,
                        patch=patch,
                    )
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

        nonempty = []
        for record in store.records():
            if record.stroke_count:
                nonempty.append({
                    **record.to_dict(),
                    "preview_path": str(store.preview_path(record.revision_id).resolve()),
                })
        best_revision: str | None = None
        best_preview: Path | None = None
        final_reason = terminal_reason
        if nonempty:
            best_revision, selection_reason = self.planner.select_best(
                prompt=prompt,
                plan=plan,
                revisions=nonempty,
            )
            best_preview = store.preview_path(best_revision)
            final_reason = selection_reason or terminal_reason
            best_record = store.records_by_id()[best_revision]
            final_dir = self.output_dir / "final"
            final_dir.mkdir(exist_ok=True)
            shutil.copy2(self.output_dir / best_record.sketch_path, final_dir / "sketch.json")
            shutil.copy2(self.output_dir / best_record.svg_path, final_dir / "sketch.svg")
            shutil.copy2(best_preview, final_dir / "preview.png")
            _write_json(self.output_dir / "final_selection.json", {
                "status": status,
                "best_revision": best_revision,
                "reason": final_reason,
                "active_revision_at_stop": active_revision,
                "final_artifact": {
                    "sketch": "final/sketch.json",
                    "svg": "final/sketch.svg",
                    "preview": "final/preview.png",
                },
            })
        else:
            status = "failed"
            final_reason = "no non-empty drawing revision was produced"
            _write_json(self.output_dir / "final_selection.json", {
                "status": status,
                "best_revision": None,
                "reason": final_reason,
                "active_revision_at_stop": active_revision,
            })
        return IncrementalRunResult(
            status=status,
            best_revision=best_revision,
            best_preview=best_preview,
            rounds_completed=len(trajectory),
            trajectory_path=trajectory_path,
            plan_path=plan_path,
            reason=final_reason,
            run_wall_seconds=perf_counter() - started,
        )
