from __future__ import annotations

import json
import shutil
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

from path3d.renderer import render_scene_views
from path3d_json.compiler import compile_scene
from path3d_json.generator import SYSTEM_PROMPT as BASE_GENERATOR_SYSTEM_PROMPT
from path3d_json.schema import StructuredScene

from .common import ResponsesRole, image_url, json_object, write_json


GENERATOR_SYSTEM_PROMPT = BASE_GENERATOR_SYSTEM_PROMPT + """

Quality priorities for complete regeneration:
- Make the target immediately recognizable in every useful view, with a coherent main body rather than disconnected symbols.
- Preserve actual depth and shared joints across front, side, top, and perspective views.
- Balance detail against clarity. Use smooth abstract curves for organic mass instead of accumulating brittle facets.
- If prior experience is supplied, apply it while redrawing the complete scene. Do not patch or discuss the previous scene."""

CRITIC_SYSTEM_PROMPT = """You are a strict multiview visual critic for complete structured 3D line sketches. Inspect the actual front, side, top, and perspective contact sheet for every candidate. Give an absolute assessment, not praise merely because one candidate is relatively best.

Evaluate target recognizability, coherent main body and silhouette, meaningful depth, connected joints, proportions, curve smoothness, and consistency across all four views. For a dragon breathing fire, judge whether the head/body/tail/wings read as one dragon and whether the fire visibly begins at the mouth and travels outward. State strengths worth preserving and concrete weaknesses to correct. Return only JSON."""

SELECTOR_SYSTEM_PROMPT = """You are an independent multiview visual selector. Inspect all actual contact sheets and select the candidate that is most recognizable, coherent, genuinely three-dimensional, and faithful to the target. Do not select an unusable drawing merely because it is least bad without stating that it remains unacceptable. Return only JSON."""

EXPERIENCE_SYSTEM_PROMPT = """You consolidate compact drawing experience for a structured 3D generator that will redraw the whole artifact from scratch.

Rewrite the complete experience as one JSON object with exactly four arrays:
{"preserve":["..."],"avoid":["..."],"general":["..."],"task_strategy":["..."]}

Rules:
- Return at most 6 items total and at most 2 items in any array.
- Each item is one actionable sentence no longer than 220 characters.
- preserve: visually successful decisions worth retaining.
- avoid: evidenced failure patterns that should not recur.
- general: subject-independent 3D drawing lessons reusable across tasks.
- task_strategy: temporary advice specific to the current target.
- Prefer the few highest-impact lessons. Do not restate the target as a long construction plan.
- Base every item on the visual critique and candidate geometry.
- Do not mention candidate IDs, scores, edit patches, or raw coordinates.
- Return only the JSON object."""

PROGRESS_SYSTEM_PROMPT = """You are an independent visual progress judge. Compare the historical loop winners using their actual four-view contact sheets. Select the best historical result and decide whether the newest winner is a clear meaningful improvement in absolute target fidelity, recognizability, coherent 3D structure, and visual quality. Small extra detail or complexity is not meaningful improvement. Return only JSON."""


@dataclass(frozen=True)
class ReflectionCandidate:
    candidate_id: str
    structured_scene: StructuredScene
    directory: Path
    contact_sheet: Path
    raw_response: str
    seconds: float


@dataclass(frozen=True)
class StructuredReflectionResult:
    status: str
    best_candidate_id: str
    best_preview: Path
    loops_completed: int
    stopped_early: bool
    run_wall_seconds: float


EXPERIENCE_KEYS = ("preserve", "avoid", "general", "task_strategy")
MAX_EXPERIENCE_ITEMS = 6
MAX_EXPERIENCE_ITEMS_PER_CATEGORY = 2
MAX_EXPERIENCE_ITEM_CHARS = 220


def validate_experience(value: dict[str, Any]) -> dict[str, list[str]]:
    if set(value) != set(EXPERIENCE_KEYS):
        raise ValueError(f"experience must contain exactly these keys: {', '.join(EXPERIENCE_KEYS)}")
    result: dict[str, list[str]] = {}
    total = 0
    for key in EXPERIENCE_KEYS:
        items = value[key]
        if not isinstance(items, list):
            raise ValueError(f"experience.{key} must be an array")
        if len(items) > MAX_EXPERIENCE_ITEMS_PER_CATEGORY:
            raise ValueError(
                f"experience.{key} has {len(items)} items; maximum is {MAX_EXPERIENCE_ITEMS_PER_CATEGORY}"
            )
        cleaned: list[str] = []
        for item in items:
            text = str(item).strip()
            if not text:
                raise ValueError(f"experience.{key} contains an empty item")
            if len(text) > MAX_EXPERIENCE_ITEM_CHARS:
                raise ValueError(
                    f"experience.{key} item has {len(text)} characters; maximum is {MAX_EXPERIENCE_ITEM_CHARS}"
                )
            cleaned.append(text)
        result[key] = cleaned
        total += len(cleaned)
    if total > MAX_EXPERIENCE_ITEMS:
        raise ValueError(f"experience has {total} items; maximum is {MAX_EXPERIENCE_ITEMS}")
    if total == 0:
        raise ValueError("experience must contain at least one item")
    return result


def format_experience(experience: dict[str, list[str]] | None) -> str:
    if not experience:
        return "None; solve the target directly."
    return json.dumps(experience, ensure_ascii=False, indent=2)


class StructuredReflectionPath3DLoop(ResponsesRole):
    def __init__(
        self,
        *,
        output_dir: str | Path,
        model: str | None = None,
        vision_model: str | None = None,
        client: Any | None = None,
        samples: int = 3,
        max_loops: int = 2,
        max_workers: int = 3,
    ) -> None:
        super().__init__(model=model, vision_model=vision_model, client=client)
        self.output_dir = Path(output_dir)
        self.samples = max(1, samples)
        self.max_loops = max(1, max_loops)
        self.max_workers = max(1, min(3, max_workers))

    def _generate_candidate(
        self,
        prompt: str,
        experience: dict[str, list[str]] | None,
        loop_index: int,
        candidate_index: int,
        width: int,
        height: int,
    ) -> ReflectionCandidate:
        started = perf_counter()
        candidate_id = f"loop_{loop_index:02d}_candidate_{candidate_index:02d}"
        directory = self.output_dir / "loops" / f"loop_{loop_index:02d}" / f"candidate_{candidate_index:02d}"
        directory.mkdir(parents=True, exist_ok=True)
        request = (
            f"Draw this as one complete coherent structured 3D spatial line sketch: {prompt}\n\n"
            f"Compact experience from earlier visual review:\n{format_experience(experience)}"
        )
        raw = self.call(system=GENERATOR_SYSTEM_PROMPT, content=request, max_tokens=8000)
        (directory / "raw_response.txt").write_text(raw, encoding="utf-8")
        try:
            structured = StructuredScene.from_dict(json_object(raw), prompt=prompt)
        except Exception as exc:
            repair = self.call(
                system=GENERATOR_SYSTEM_PROMPT,
                content=request + f"\n\nThe previous output failed validation: {type(exc).__name__}: {exc}. Regenerate the complete valid scene.",
                max_tokens=8000,
            )
            (directory / "repair_response.txt").write_text(repair, encoding="utf-8")
            structured = StructuredScene.from_dict(json_object(repair), prompt=prompt)
            raw = repair
        (directory / "structured_scene.json").write_text(structured.to_json(), encoding="utf-8")
        compiled = compile_scene(structured)
        (directory / "scene.json").write_text(compiled.to_json(), encoding="utf-8")
        render_scene_views(compiled, directory / "views", width=width, height=height)
        return ReflectionCandidate(
            candidate_id, structured, directory, directory / "views" / "contact_sheet.png", raw,
            perf_counter() - started,
        )

    @staticmethod
    def _candidate_content(prompt: str, candidates: list[ReflectionCandidate], instruction: str) -> list[dict[str, Any]]:
        content: list[dict[str, Any]] = [{"type": "input_text", "text": f"Target: {prompt}\n{instruction}"}]
        for candidate in candidates:
            content.extend([
                {"type": "input_text", "text": f"Candidate ID: {candidate.candidate_id}"},
                {"type": "input_image", "image_url": image_url(candidate.contact_sheet)},
            ])
        return content

    def _critic(self, prompt: str, candidates: list[ReflectionCandidate]) -> dict[str, Any]:
        value, _ = self.call_json(
            system=CRITIC_SYSTEM_PROMPT,
            content=self._candidate_content(
                prompt, candidates,
                "For each candidate return strengths, weaknesses, recognizability, fire attachment/direction, multiview consistency, and an absolute verdict. Return {\"candidates\":[...],\"cross_candidate_lessons\":[...]}.",
            ),
            max_tokens=3000, vision=True,
        )
        return value

    def _selector(self, prompt: str, candidates: list[ReflectionCandidate]) -> dict[str, Any]:
        value, _ = self.call_json(
            system=SELECTOR_SYSTEM_PROMPT,
            content=self._candidate_content(
                prompt, candidates,
                "Return {\"selected_candidate_id\":\"...\",\"absolute_acceptable\":true|false,\"reason\":\"...\",\"confidence\":0.0}.",
            ),
            max_tokens=1200, vision=True,
        )
        valid = {item.candidate_id for item in candidates}
        if value.get("selected_candidate_id") not in valid:
            raise ValueError(f"selector chose unknown candidate: {value.get('selected_candidate_id')!r}")
        return value

    def _experience(
        self,
        prompt: str,
        previous: dict[str, list[str]] | None,
        candidates: list[ReflectionCandidate],
        critic: dict[str, Any],
    ) -> dict[str, list[str]]:
        scenes = {item.candidate_id: item.structured_scene.to_dict() for item in candidates}
        request = (
            f"Target: {prompt}\nPrevious complete compact experience:\n{format_experience(previous)}\n\n"
            f"Structured candidates:\n{json.dumps(scenes, ensure_ascii=False)}\n\n"
            f"Visual critic output:\n{json.dumps(critic, ensure_ascii=False)}\n\n"
            "Rewrite the complete compact experience now."
        )
        last_error: Exception | None = None
        for attempt in range(2):
            suffix = "" if attempt == 0 else f"\n\nYour previous experience object failed validation: {last_error}. Return a corrected compact object."
            value, _ = self.call_json(
                system=EXPERIENCE_SYSTEM_PROMPT,
                content=request + suffix,
                max_tokens=1200,
            )
            try:
                return validate_experience(value)
            except ValueError as exc:
                last_error = exc
        raise ValueError(f"experience failed schema validation after 2 attempts: {last_error}")

    def _progress(self, prompt: str, winners: list[ReflectionCandidate]) -> dict[str, Any]:
        value, _ = self.call_json(
            system=PROGRESS_SYSTEM_PROMPT,
            content=self._candidate_content(
                prompt, winners,
                "These are historical loop winners in chronological order. Return {\"best_candidate_id\":\"...\",\"meaningful_improvement\":true|false,\"reason\":\"...\"}.",
            ),
            max_tokens=1200, vision=True,
        )
        valid = {item.candidate_id for item in winners}
        if value.get("best_candidate_id") not in valid:
            raise ValueError(f"progress judge chose unknown candidate: {value.get('best_candidate_id')!r}")
        return value

    def run(self, prompt: str, *, width: int = 512, height: int = 512) -> StructuredReflectionResult:
        started = perf_counter()
        if not prompt.strip():
            raise ValueError("prompt cannot be empty")
        if self.output_dir.exists():
            raise FileExistsError(f"output already exists: {self.output_dir}")
        self.output_dir.mkdir(parents=True)
        experience: dict[str, list[str]] | None = None
        all_candidates: dict[str, ReflectionCandidate] = {}
        winners: list[ReflectionCandidate] = []
        history: list[dict[str, Any]] = []
        timing_loops: list[dict[str, Any]] = []
        stopped_early = False

        for loop_index in range(1, self.max_loops + 1):
            loop_started = perf_counter()
            loop_dir = self.output_dir / "loops" / f"loop_{loop_index:02d}"
            loop_dir.mkdir(parents=True, exist_ok=True)
            draw_started = perf_counter()
            with ThreadPoolExecutor(max_workers=min(self.max_workers, self.samples)) as pool:
                futures = [pool.submit(self._generate_candidate, prompt, experience, loop_index, index, width, height)
                           for index in range(1, self.samples + 1)]
                candidates = [future.result() for future in futures]
            draw_wall = perf_counter() - draw_started
            all_candidates.update((item.candidate_id, item) for item in candidates)

            judge_started = perf_counter()
            with ThreadPoolExecutor(max_workers=2) as pool:
                critic_future = pool.submit(self._critic, prompt, candidates)
                selector_future = pool.submit(self._selector, prompt, candidates)
                critic = critic_future.result()
                selection = selector_future.result()
            judge_wall = perf_counter() - judge_started
            winner = all_candidates[str(selection["selected_candidate_id"])]
            winners.append(winner)
            progress_started = perf_counter()
            progress = self._progress(prompt, winners)
            progress_seconds = perf_counter() - progress_started
            write_json(loop_dir / "critic.json", critic)
            write_json(loop_dir / "selection.json", selection)
            write_json(loop_dir / "progress.json", progress)
            record = {
                "loop": loop_index,
                "candidate_ids": [item.candidate_id for item in candidates],
                "winner": winner.candidate_id,
                "global_best": progress["best_candidate_id"],
                "meaningful_improvement": bool(progress.get("meaningful_improvement", loop_index == 1)),
                "experience_before": experience,
            }
            if loop_index > 1 and not record["meaningful_improvement"]:
                stopped_early = True
                record["stop_reason"] = "visual progress judge found no meaningful improvement"
                history.append(record)
                timing_loops.append({
                    "loop": loop_index, "candidate_seconds": {item.candidate_id: item.seconds for item in candidates},
                    "parallel_draw_wall_seconds": draw_wall, "parallel_visual_judging_wall_seconds": judge_wall,
                    "progress_seconds": progress_seconds, "experience_seconds": 0.0,
                    "loop_wall_seconds": perf_counter() - loop_started,
                })
                break
            experience_started = perf_counter()
            experience = self._experience(prompt, experience, candidates, critic)
            experience_seconds = perf_counter() - experience_started
            write_json(loop_dir / "experience.json", experience)
            (loop_dir / "experience.txt").write_text(format_experience(experience), encoding="utf-8")
            record["experience_after"] = experience
            history.append(record)
            timing_loops.append({
                "loop": loop_index, "candidate_seconds": {item.candidate_id: item.seconds for item in candidates},
                "parallel_draw_wall_seconds": draw_wall, "parallel_visual_judging_wall_seconds": judge_wall,
                "progress_seconds": progress_seconds, "experience_seconds": experience_seconds,
                "loop_wall_seconds": perf_counter() - loop_started,
            })

        best_id = str(history[-1]["global_best"])
        best = all_candidates[best_id]
        final_dir = self.output_dir / "final"
        shutil.copytree(best.directory, final_dir)
        write_json(self.output_dir / "history.json", history)
        if experience:
            write_json(self.output_dir / "final_experience.json", experience)
        (self.output_dir / "final_experience.txt").write_text(format_experience(experience), encoding="utf-8")
        write_json(self.output_dir / "final_selection.json", {
            "status": "complete", "best_candidate_id": best_id, "loops_completed": len(history),
            "stopped_early": stopped_early, "preview": "final/views/contact_sheet.png",
        })
        total = perf_counter() - started
        write_json(self.output_dir / "timings.json", {
            "reasoning_effort": self.reasoning_effort, "loops": timing_loops, "run_wall_seconds": total,
        })
        return StructuredReflectionResult("complete", best_id, final_dir / "views" / "contact_sheet.png", len(history), stopped_early, total)
