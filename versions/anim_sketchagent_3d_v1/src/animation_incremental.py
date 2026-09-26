"""Animation-specific incremental loop; frozen still-sketch code remains unchanged."""
from __future__ import annotations
import shutil
from pathlib import Path
from time import perf_counter
from typing import Any
from drawer_v14.three_d.document import Path3DDocument
from drawer_v14.three_d.patch import PatchValidation
from drawer_v14.three_d.storage import Path3DRevisionStore
from path3d_json_agents.common import write_json
from path3d_json_agents.incremental import StructuredIncrementalPath3DLoop, StructuredIncrementalResult


class AnimationDocument(Path3DDocument):
    def validate_patch(self, patch, policy=None, *, protected_ids=()):
        validation = super().validate_patch(patch, policy, protected_ids=protected_ids)
        # The still-sketch validator forbids every ID reuse. Animation permits
        # replacing a currently live stroke only by deleting+adding it atomically.
        prefix = "new stroke IDs must never reuse current or retired IDs: "
        errors = [error for error in validation.errors if not error.startswith(prefix)]
        current = set(self.stroke_ids)
        replaced = current & set(patch.delete_stroke_ids)
        additions = {stroke.id for stroke in patch.add_strokes}
        forbidden = sorted(additions & ((current - replaced) | (self.retired_ids - replaced)))
        if forbidden:
            errors.append(prefix + ", ".join(forbidden))
        return PatchValidation(not errors, tuple(errors))

    def apply_patch(self, patch, policy=None, *, protected_ids=()):
        updated = super().apply_patch(patch, policy, protected_ids=protected_ids)
        removed = set(patch.delete_stroke_ids) - {stroke.id for stroke in patch.add_strokes}
        return AnimationDocument(updated.prompt, updated.strokes,
                                 retired_ids=self.retired_ids | removed)


class AnimationRevisionStore(Path3DRevisionStore):
    def load_document(self, revision_id):
        document = super().load_document(revision_id)
        return AnimationDocument(document.prompt, document.strokes, retired_ids=document.retired_ids)


class AnimationIncrementalLoop(StructuredIncrementalPath3DLoop):
    # Keep the proven revision/review/export flow, using an animation document
    # factory instead of mutating the imported frozen module's global classes.
    def run(self, prompt: str, *, width: int = 512, height: int = 512) -> StructuredIncrementalResult:
        started = perf_counter()
        if not prompt.strip():
            raise ValueError("prompt cannot be empty")
        if self.output_dir.exists():
            raise FileExistsError(f"output already exists: {self.output_dir}")
        store = AnimationRevisionStore(self.output_dir, width=width, height=height)
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
