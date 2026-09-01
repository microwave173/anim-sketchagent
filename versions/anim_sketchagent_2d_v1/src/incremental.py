"""Multi-step Path2D key drawing: planner reviews a PNG, editor patches strokes."""
from __future__ import annotations

import json
import shutil
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

from PIL import Image

from path2d.parser import parse_path2d
from path2d.renderer import render_scene
from path2d.schema import Path2DScene, Path2DStroke


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def empty_scene(prompt: str) -> dict[str, Any]:
    return {"prompt": prompt, "strokes": [], "metadata": {"format": "path2d_v1"}}


def render_scene_dict(scene: dict[str, Any], png: Path, *, width: int, height: int) -> Path:
    png = Path(png)
    png.parent.mkdir(parents=True, exist_ok=True)
    if not (scene.get("strokes") or []):
        Image.new("RGB", (width, height), "white").save(png)
        return png
    obj = Path2DScene.from_dict(scene, prompt=str(scene.get("prompt") or ""))
    return render_scene(obj, png, width=width, height=height)


@dataclass
class PlannerReview:
    decision: str
    assessment: dict[str, Any]
    instruction: dict[str, Any] | None
    rollback_revision: str | None
    reason: str

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "PlannerReview":
        decision = str(value.get("decision") or "").strip()
        if decision not in {"continue", "retry", "rollback", "finish", "fail"}:
            raise ValueError(f"bad planner decision: {decision!r}")
        instruction = value.get("instruction")
        if decision in {"continue", "retry"}:
            if not isinstance(instruction, dict) or not str(instruction.get("objective") or "").strip():
                raise ValueError("continue/retry requires instruction.objective")
        return cls(
            decision=decision,
            assessment=value.get("assessment") if isinstance(value.get("assessment"), dict) else {},
            instruction=instruction if isinstance(instruction, dict) else None,
            rollback_revision=str(value.get("rollback_revision") or "").strip() or None,
            reason=str(value.get("reason") or "").strip(),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "assessment": self.assessment,
            "instruction": self.instruction,
            "rollback_revision": self.rollback_revision,
            "reason": self.reason,
        }


class Path2DPatchParseError(ValueError):
    def __init__(self, message: str, *, raw: str, value: dict[str, Any]) -> None:
        super().__init__(message)
        self.raw = raw
        self.value = value


@dataclass(frozen=True)
class Path2DPatch:
    delete_stroke_ids: tuple[str, ...] = ()
    add_strokes: tuple[dict[str, Any], ...] = ()
    update_strokes: tuple[dict[str, Any], ...] = ()
    summary: str = ""

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Path2DPatch":
        if not isinstance(value, dict):
            raise ValueError("patch must be an object")
        deletes = tuple(str(x).strip() for x in (value.get("delete_stroke_ids") or []) if str(x).strip())
        adds = tuple(dict(item) for item in (value.get("add_strokes") or []))
        updates = tuple(dict(item) for item in (value.get("update_strokes") or []))
        if not adds and not updates and not deletes:
            raise ValueError("patch is empty")
        for item in adds + updates:
            Path2DStroke.from_dict(
                {
                    "id": item.get("id"),
                    "path": item.get("path"),
                    "description": item.get("description") or item.get("id") or "stroke",
                    **{k: item[k] for k in ("stroke", "stroke_width", "opacity", "group") if k in item},
                }
            )
            parse_path2d(str(item.get("path") or ""))
        return cls(
            delete_stroke_ids=deletes,
            add_strokes=adds,
            update_strokes=updates,
            summary=str(value.get("summary") or "").strip(),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "delete_stroke_ids": list(self.delete_stroke_ids),
            "add_strokes": list(self.add_strokes),
            "update_strokes": list(self.update_strokes),
            "summary": self.summary,
        }


def apply_path2d_patch(
    scene: dict[str, Any],
    patch: Path2DPatch | dict[str, Any],
    *,
    max_additions: int = 48,
    protected_ids: tuple[str, ...] = (),
) -> dict[str, Any]:
    if isinstance(patch, dict):
        patch = Path2DPatch.from_dict(patch)
    strokes = {str(s["id"]): dict(s) for s in scene.get("strokes") or [] if s.get("id")}
    order = [str(s["id"]) for s in scene.get("strokes") or [] if s.get("id")]
    protected = set(protected_ids)
    if len(patch.add_strokes) > max_additions:
        raise ValueError(f"too many add_strokes: {len(patch.add_strokes)} > {max_additions}")
    for did in patch.delete_stroke_ids:
        if did in protected:
            raise ValueError(f"cannot delete protected id {did!r}")
        if did not in strokes:
            raise ValueError(f"delete unknown id {did!r}")
        del strokes[did]
        order = [i for i in order if i != did]
    for item in patch.update_strokes:
        sid = str(item.get("id") or "").strip()
        if sid not in strokes:
            raise ValueError(f"update unknown id {sid!r}")
        parse_path2d(str(item.get("path") or ""))
        strokes[sid] = {**strokes[sid], **item, "id": sid}
    for item in patch.add_strokes:
        sid = str(item.get("id") or "").strip()
        parse_path2d(str(item.get("path") or ""))
        body = {
            "id": sid,
            "path": item["path"],
            "description": item.get("description") or sid,
            "stroke": item.get("stroke", "#111111"),
            "stroke_width": item.get("stroke_width", 3.0),
            "opacity": item.get("opacity", 1.0),
            "group": item.get("group", sid),
        }
        if sid in strokes:
            strokes[sid] = {**strokes[sid], **body}
        else:
            strokes[sid] = body
            order.append(sid)
    return {
        "prompt": scene.get("prompt") or "",
        "strokes": [strokes[i] for i in order if i in strokes],
        "metadata": scene.get("metadata") if isinstance(scene.get("metadata"), dict) else {"format": "path2d_v1"},
    }


@dataclass
class IncrementalResult:
    status: str
    best_revision: str | None
    best_preview: Path | None
    rounds_completed: int
    reason: str
    run_wall_seconds: float


@dataclass
class _Revision:
    revision_id: str
    scene: dict[str, Any]
    parent: str | None = None
    stroke_count: int = 0
    png: Path | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "revision_id": self.revision_id,
            "parent": self.parent,
            "stroke_count": self.stroke_count,
            "scene_path": f"revisions/{self.revision_id}/scene.json",
            "png": f"revisions/{self.revision_id}/view.png",
        }


class Path2DRevisionStore:
    def __init__(self, output_dir: Path, *, width: int, height: int) -> None:
        self.output_dir = Path(output_dir)
        self.width = width
        self.height = height
        self._records: list[_Revision] = []
        self._by_id: dict[str, _Revision] = {}
        self._n = 0

    def initialize(self, prompt: str, scene: dict[str, Any] | None = None) -> _Revision:
        if scene is None:
            value = empty_scene(prompt)
        else:
            value = deepcopy(scene)
            value["prompt"] = prompt
        return self.commit(value, parent=None)

    def commit(self, scene: dict[str, Any], *, parent: str | None, round_index: int | None = None) -> _Revision:
        rid = f"revision_{self._n:03d}"
        self._n += 1
        dest = self.output_dir / "revisions" / rid
        dest.mkdir(parents=True, exist_ok=True)
        write_json(dest / "scene.json", scene)
        png = render_scene_dict(scene, dest / "view.png", width=self.width, height=self.height)
        rec = _Revision(
            revision_id=rid,
            scene=scene,
            parent=parent,
            stroke_count=len(scene.get("strokes") or []),
            png=png,
        )
        self._records.append(rec)
        self._by_id[rid] = rec
        write_json(dest / "state.json", rec.to_dict())
        return rec

    def load(self, revision_id: str) -> _Revision:
        return self._by_id[revision_id]

    def records(self) -> list[_Revision]:
        return list(self._records)

    def records_by_id(self) -> dict[str, _Revision]:
        return dict(self._by_id)

    def png_path(self, revision_id: str) -> Path:
        rec = self._by_id[revision_id]
        assert rec.png is not None
        return rec.png


class Path2DIncrementalLoop:
    def __init__(
        self,
        *,
        output_dir: str | Path,
        planner: Any,
        editor: Any,
        max_rounds: int = 4,
        max_patch_attempts: int = 3,
        max_additions_per_patch: int = 48,
        width: int = 512,
        height: int = 512,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.planner = planner
        self.editor = editor
        self.max_rounds = max(1, max_rounds)
        self.max_patch_attempts = max(1, max_patch_attempts)
        self.max_additions_per_patch = max(1, max_additions_per_patch)
        self.width = width
        self.height = height

    def run(self, prompt: str, initial_scene: dict[str, Any] | None = None) -> IncrementalResult:
        started = perf_counter()
        if not prompt.strip():
            raise ValueError("prompt cannot be empty")
        if self.output_dir.exists():
            raise FileExistsError(f"output already exists: {self.output_dir}")
        store = Path2DRevisionStore(self.output_dir, width=self.width, height=self.height)
        active = store.initialize(prompt=prompt, scene=initial_scene).revision_id
        plan = self.planner.create_plan(prompt=prompt)
        write_json(self.output_dir / "plan.json", plan)
        trajectory: list[dict[str, Any]] = []
        last_error: str | None = None
        status, terminal_reason = "max_rounds", "maximum rounds reached"
        rounds_completed = 0

        for round_index in range(1, self.max_rounds + 1):
            rounds_completed = round_index
            document = store.load(active)
            review = self.planner.review(
                prompt=prompt,
                plan=plan,
                current_revision=active,
                current_scene=document.scene,
                current_png=store.png_path(active),
                history=[item.to_dict() for item in store.records()],
                last_error=last_error,
                round_index=round_index,
                max_rounds=self.max_rounds,
            )
            round_dir = self.output_dir / "rounds" / f"round_{round_index:02d}"
            round_dir.mkdir(parents=True, exist_ok=True)
            write_json(round_dir / "planner_review.json", review.to_dict())
            print(f"  round {round_index}/{self.max_rounds} review={review.decision}", flush=True)
            event: dict[str, Any] = {
                "round": round_index,
                "active_revision_before": active,
                "planner_review": review.to_dict(),
            }
            if review.decision == "rollback":
                target = review.rollback_revision or ""
                if target not in store.records_by_id():
                    raise ValueError(f"planner requested unknown rollback revision: {target}")
                active, last_error = target, None
                event["active_revision_after"] = active
                trajectory.append(event)
                write_json(self.output_dir / "trajectory.json", trajectory)
                continue
            if review.decision in {"finish", "fail"}:
                status = "complete" if review.decision == "finish" else "failed"
                terminal_reason = review.reason or f"planner decided {review.decision}"
                trajectory.append(event)
                write_json(self.output_dir / "trajectory.json", trajectory)
                break

            instruction = review.instruction or {}
            previous_structured: dict[str, Any] | None = None
            attempts: list[dict[str, Any]] = []
            patch_applied = False
            for attempt in range(1, self.max_patch_attempts + 1):
                raw = ""
                structured_value: dict[str, Any] = previous_structured or {}
                errors: list[str] = []
                compiled: dict[str, Any] | None = None
                try:
                    structured, raw = self.editor.edit(
                        prompt=prompt,
                        plan=plan,
                        instruction=instruction,
                        current_scene=document.scene,
                        current_png=store.png_path(active),
                        previous_error=last_error,
                        previous_patch=previous_structured,
                    )
                    structured_value = structured.to_dict()
                    compiled = apply_path2d_patch(
                        document.scene,
                        structured,
                        max_additions=self.max_additions_per_patch,
                    )
                except Exception as exc:
                    raw = str(getattr(exc, "raw", raw or exc))
                    structured_value = getattr(exc, "value", previous_structured or {})
                    errors = [f"{type(exc).__name__}: {exc}"]
                attempt_record = {
                    "attempt": attempt,
                    "structured_patch": structured_value,
                    "validation": {"valid": not errors, "errors": errors},
                }
                attempts.append(attempt_record)
                write_json(round_dir / f"editor_attempt_{attempt:02d}.json", attempt_record)
                (round_dir / f"editor_attempt_{attempt:02d}_raw.txt").write_text(raw, encoding="utf-8")
                if not errors and compiled is not None:
                    record = store.commit(compiled, parent=active, round_index=round_index)
                    write_json(
                        self.output_dir / "revisions" / record.revision_id / "structured_patch.json",
                        structured_value,
                    )
                    active, last_error, patch_applied = record.revision_id, None, True
                    event["committed_revision"] = record.to_dict()
                    print(f"  round {round_index} patch strokes={record.stroke_count}", flush=True)
                    break
                last_error = "; ".join(errors)
                previous_structured = structured_value
                print(f"  round {round_index} editor attempt {attempt} failed: {last_error}", flush=True)
            event.update(
                {
                    "editor_attempts": attempts,
                    "patch_applied": patch_applied,
                    "active_revision_after": active,
                }
            )
            if not patch_applied:
                event["error"] = last_error
            trajectory.append(event)
            write_json(self.output_dir / "trajectory.json", trajectory)

        revisions = [
            {**record.to_dict(), "png_absolute": str(store.png_path(record.revision_id).resolve())}
            for record in store.records()
            if record.stroke_count
        ]
        best_revision: str | None = None
        best_preview: Path | None = None
        final_reason = terminal_reason
        if revisions:
            best_revision, selected_reason = self.planner.select_best(
                prompt=prompt, plan=plan, revisions=revisions
            )
            final_reason = selected_reason or terminal_reason
            best_record = store.records_by_id()[best_revision]
            best_preview = store.png_path(best_revision)
            final_dir = self.output_dir / "final"
            final_dir.mkdir()
            shutil.copy2(self.output_dir / "revisions" / best_revision / "scene.json", final_dir / "scene.json")
            shutil.copy2(best_preview, final_dir / "view.png")
            source_structured = self.output_dir / "revisions" / best_revision / "structured_patch.json"
            if source_structured.exists():
                shutil.copy2(source_structured, final_dir / "last_structured_patch.json")
            write_json(
                self.output_dir / "final_selection.json",
                {
                    "status": status,
                    "best_revision": best_revision,
                    "reason": final_reason,
                    "active_revision_at_stop": active,
                },
            )
        else:
            status, final_reason = "failed", "no non-empty revision was produced"
            write_json(
                self.output_dir / "final_selection.json",
                {"status": status, "best_revision": None, "reason": final_reason},
            )
        return IncrementalResult(
            status=status,
            best_revision=best_revision,
            best_preview=best_preview,
            rounds_completed=rounds_completed,
            reason=final_reason,
            run_wall_seconds=perf_counter() - started,
        )
