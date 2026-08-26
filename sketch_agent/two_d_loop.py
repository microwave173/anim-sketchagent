from __future__ import annotations

import base64
import json
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any, Callable

from dotenv import load_dotenv

from .drawer import DrawConfig, Drawer
from .model_config import get_reasoning_effort, reasoning_options
from .providers import OfficialSketchAgentProvider
from .rendering import render_svg_png
from .schema import Sketch
from .svg import render_svg


CRITIC_SYSTEM_PROMPT = """You are the critic in a 2D vector-sketch system.
You only evaluate visible drawings against the user's drawing request. Do not propose file edits, SVG code, or hidden implementation details.
Evaluate both the whole image (recognizability, prompt adherence, composition, style) and local parts (shape, proportion, connections, missing or malformed details).
Treat beauty, coherence, visual economy, and preservation of distinctive identity cues as simultaneous requirements. Diagnose both failure modes: excessive detail that makes the image cluttered or ugly, and excessive simplification that makes it generic, incomplete, or less recognizable. Classify visible or requested details by value: preserve high-value identity and expression cues; simplify, merge, or omit low-value anatomical and decorative complexity.
When complexity hurts beauty, identify the offending detail and propose a simpler coordinated replacement rather than reflexively deleting it. When a simplified candidate is attractive but missing useful cues, specify the smallest clean strokes that should be added back without disturbing the composition. Derive which cues are high-value from the user's request and the visible candidates, not from assumptions about a particular test subject. Prefer simplified contours and symbolic marks for difficult anatomy, repeated texture, or decorative detail, while preserving features essential to identity, expression, count, pose, or spatial relation.
Return only valid JSON using the requested schema."""

SELECTOR_SYSTEM_PROMPT = """You are an independent visual selector in a 2D vector-sketch system.
Choose the single best candidate for the user's request based only on the visible candidate images. Do not critique every candidate and do not infer how they were generated.
Do not reward minimal stroke count by itself. Prefer the candidate that best balances beauty and coordination with enough distinctive details to communicate the prompt. Penalize both cluttered literalism and attractive-but-generic over-simplification.
Return only valid JSON using the requested schema."""

PROGRESS_SYSTEM_PROMPT = """You are an independent progress judge in an iterative 2D vector-sketch system.
You only see the winner from each completed loop. Select the best winner overall and decide whether the newest winner is a clear, meaningful improvement over the best earlier winner.
An improvement should preserve or improve overall beauty and coordination while retaining or restoring useful identity cues. A cleaner redraw that loses important details is not an improvement; a more detailed redraw that introduces clutter is also not an improvement. Small stylistic variation or an equally good redraw is not meaningful improvement. Return only valid JSON using the requested schema."""

EXPERIENCE_SYSTEM_PROMPT = """You are the drawing model's experience consolidator.
Rewrite the complete drawing experience for the next attempt. Preserve earlier advice that remains supported, include both strengths worth retaining and weaknesses to improve, resolve contradictions, and remove obsolete or task-specific noise.
The experience must encode a beauty-constrained detail policy. Begin with a readable, harmonious silhouette. Preserve successful high-value identity and expression cues, simplify low-value complexity, and explicitly restore high-value cues that earlier simplification removed. Prefer the smallest coordinated stroke set that is both attractive and unmistakably expressive; do not optimize for minimum stroke count alone.
Include concrete retain, simplify, and restore instructions supported by the critic and the visible evidence. Do not hard-code details for any particular subject. State which observed features carry identity, expression, count, pose, or spatial relation; preserve or restore those with minimal coordinated marks, while compressing lower-value anatomy, texture, repetition, and decoration into simpler contours or symbols.
The output replaces the previous experience in full. Return plain text only, with concise actionable drawing guidance. Do not output SVG or JSON."""


@dataclass
class Candidate2D:
    loop_index: int
    candidate_index: int
    sketch: Sketch
    svg: str
    png_path: Path
    raw_response: str
    drawing_system_prompt: str

    @property
    def candidate_id(self) -> str:
        return f"loop_{self.loop_index:02d}_candidate_{self.candidate_index:02d}"


@dataclass
class TwoDLoopResult:
    sketch: Sketch
    raw_response: str
    experience: str
    loops_completed: int
    stopped_early: bool
    best_candidate_id: str
    timings: dict[str, Any]


def _json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip().removeprefix("```json").removesuffix("```").strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start < 0 or end < start:
        raise ValueError(f"model did not return a JSON object: {text[:300]}")
    value = json.loads(cleaned[start:end + 1])
    if not isinstance(value, dict):
        raise ValueError("model response must be a JSON object")
    return value


def _image_url(path: Path) -> str:
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return "data:image/png;base64," + encoded


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


class TwoDCriticLoop:
    """Generate, critique, select, consolidate experience, and stop on a plateau."""

    def __init__(
        self,
        *,
        model: str | None = None,
        samples: int = 3,
        max_loops: int = 2,
        output_dir: str | Path = "outputs/2d_critic_loop",
        canvas_width: int = 512,
        canvas_height: int = 512,
        provider_factory: Callable[..., OfficialSketchAgentProvider] = OfficialSketchAgentProvider,
        client: Any | None = None,
    ) -> None:
        load_dotenv(Path(__file__).resolve().parents[1] / ".env")
        self.model = model or os.getenv("MODEL", "gpt-5.6-terra")
        self.vision_model = os.getenv("VISION_MODEL", "gpt-5.6-luna")
        self.reasoning_effort = get_reasoning_effort()
        self.samples = max(1, samples)
        self.max_loops = max(1, max_loops)
        self.output_dir = Path(output_dir)
        self.canvas_width = canvas_width
        self.canvas_height = canvas_height
        self.provider_factory = provider_factory
        if client is None:
            from openai import OpenAI

            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), base_url=os.getenv("BASE_URL"))
        self.client = client

    def run(self, prompt: str) -> TwoDLoopResult:
        run_started = perf_counter()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        experience = ""
        winners: list[Candidate2D] = []
        all_candidates: dict[str, Candidate2D] = {}
        loop_history: list[dict[str, Any]] = []
        loop_timings: list[dict[str, Any]] = []
        stopped_early = False

        for loop_index in range(1, self.max_loops + 1):
            loop_started = perf_counter()
            loop_dir = self.output_dir / f"loop_{loop_index:02d}"
            loop_dir.mkdir(parents=True, exist_ok=True)
            drawing_started = perf_counter()
            with ThreadPoolExecutor(max_workers=self.samples) as pool:
                draw_futures = [
                    pool.submit(
                        self._timed_call,
                        self._draw_candidate,
                        prompt,
                        experience,
                        loop_index,
                        candidate_index,
                        loop_dir,
                    )
                    for candidate_index in range(1, self.samples + 1)
                ]
                timed_candidates = [future.result() for future in draw_futures]
            parallel_draw_wall_seconds = perf_counter() - drawing_started
            candidates = [item[0] for item in timed_candidates]
            draw_timings = [
                {"candidate_id": candidate.candidate_id, "seconds": seconds}
                for candidate, seconds in timed_candidates
            ]
            all_candidates.update((candidate.candidate_id, candidate) for candidate in candidates)

            # The critic and selector are deliberately isolated and run concurrently.
            evaluation_started = perf_counter()
            with ThreadPoolExecutor(max_workers=2) as pool:
                critic_future = pool.submit(self._timed_call, self._critique, prompt, candidates)
                selector_future = pool.submit(self._timed_call, self._select, prompt, candidates)
                critic, critic_seconds = critic_future.result()
                selection, selector_seconds = selector_future.result()
            evaluation_wall_seconds = perf_counter() - evaluation_started

            winner = self._selected_candidate(selection, candidates)
            winners.append(winner)
            progress_started = perf_counter()
            progress = self._judge_progress(prompt, winners)
            progress_seconds = perf_counter() - progress_started
            global_best = self._selected_candidate(progress, winners, key="best_candidate_id")
            meaningful_improvement = bool(progress.get("meaningful_improvement", loop_index == 1))

            timing = {
                "loop": loop_index,
                "draw_candidates": draw_timings,
                "draw_total_seconds": sum(item["seconds"] for item in draw_timings),
                "parallel_draw_wall_seconds": parallel_draw_wall_seconds,
                "critic_seconds": critic_seconds,
                "selector_seconds": selector_seconds,
                "parallel_evaluation_wall_seconds": evaluation_wall_seconds,
                "progress_judge_seconds": progress_seconds,
                "experience_consolidation_seconds": 0.0,
            }

            _write_json(loop_dir / "critic.json", critic)
            _write_json(loop_dir / "selection.json", selection)
            _write_json(loop_dir / "progress.json", progress)

            record = {
                "loop": loop_index,
                "candidate_ids": [candidate.candidate_id for candidate in candidates],
                "loop_winner": winner.candidate_id,
                "global_best": global_best.candidate_id,
                "meaningful_improvement": meaningful_improvement,
                "experience_before": experience,
            }

            if loop_index > 1 and not meaningful_improvement:
                stopped_early = True
                record["stop_reason"] = "progress judge found no meaningful improvement"
                loop_history.append(record)
                timing["loop_total_seconds"] = perf_counter() - loop_started
                loop_timings.append(timing)
                break

            experience_started = perf_counter()
            experience = self._consolidate_experience(prompt, experience, candidates, critic)
            timing["experience_consolidation_seconds"] = perf_counter() - experience_started
            (loop_dir / "experience.txt").write_text(experience, encoding="utf-8")
            record["experience_after"] = experience
            _write_json(loop_dir / "role_contexts.json", {
                "llm_a_draw": {
                    "drawing_prompt": prompt,
                    "experience": record["experience_before"],
                    "candidate_ids": record["candidate_ids"],
                    "can_see": ["drawing system prompt", "drawing prompt", "previous experience"],
                },
                "llm_b_critic": {
                    "system_prompt": CRITIC_SYSTEM_PROMPT,
                    "drawing_prompt": prompt,
                    "image_paths": [str(candidate.png_path) for candidate in candidates],
                },
                "llm_c_selector": {
                    "system_prompt": SELECTOR_SYSTEM_PROMPT,
                    "drawing_prompt": prompt,
                    "image_paths": [str(candidate.png_path) for candidate in candidates],
                },
                "llm_d_progress": {
                    "system_prompt": PROGRESS_SYSTEM_PROMPT,
                    "drawing_prompt": prompt,
                    "winner_image_paths": [str(item.png_path) for item in winners],
                },
                "llm_a_experience": {
                    "system_prompt": EXPERIENCE_SYSTEM_PROMPT,
                    "drawing_prompt": prompt,
                    "previous_experience": record["experience_before"],
                    "svg_candidate_ids": record["candidate_ids"],
                    "critic_output_file": "critic.json",
                },
            })
            loop_history.append(record)
            timing["loop_total_seconds"] = perf_counter() - loop_started
            loop_timings.append(timing)

        final_progress = loop_history[-1]["global_best"]
        best = all_candidates[final_progress]
        _write_json(self.output_dir / "history.json", loop_history)
        (self.output_dir / "final_experience.txt").write_text(experience, encoding="utf-8")
        _write_json(self.output_dir / "final_selection.json", {
            "best_candidate_id": best.candidate_id,
            "loops_completed": len(loop_history),
            "stopped_early": stopped_early,
        })
        timings = {
            "loops": loop_timings,
            "totals": {
                "draw_seconds": sum(item["draw_total_seconds"] for item in loop_timings),
                "parallel_draw_wall_seconds": sum(
                    item["parallel_draw_wall_seconds"] for item in loop_timings
                ),
                "critic_seconds": sum(item["critic_seconds"] for item in loop_timings),
                "selector_seconds": sum(item["selector_seconds"] for item in loop_timings),
                "parallel_evaluation_wall_seconds": sum(
                    item["parallel_evaluation_wall_seconds"] for item in loop_timings
                ),
                "progress_judge_seconds": sum(
                    item["progress_judge_seconds"] for item in loop_timings
                ),
                "experience_consolidation_seconds": sum(
                    item["experience_consolidation_seconds"] for item in loop_timings
                ),
                "loop_wall_seconds": sum(item["loop_total_seconds"] for item in loop_timings),
                "run_wall_seconds": perf_counter() - run_started,
            },
            "note": (
                "Candidates run concurrently, and critic/selector run concurrently. Individual "
                "durations overlap; use parallel_draw_wall_seconds and "
                "parallel_evaluation_wall_seconds for end-to-end latency."
            ),
            "reasoning_effort": self.reasoning_effort,
        }
        _write_json(self.output_dir / "timings.json", timings)
        return TwoDLoopResult(
            sketch=best.sketch,
            raw_response=best.raw_response,
            experience=experience,
            loops_completed=len(loop_history),
            stopped_early=stopped_early,
            best_candidate_id=best.candidate_id,
            timings=timings,
        )

    @staticmethod
    def _timed_call(function: Callable[..., Any], *args: Any) -> tuple[Any, float]:
        started = perf_counter()
        return function(*args), perf_counter() - started

    def _draw_candidate(
        self,
        prompt: str,
        experience: str,
        loop_index: int,
        candidate_index: int,
        loop_dir: Path,
    ) -> Candidate2D:
        candidate_dir = loop_dir / f"candidate_{candidate_index:02d}"
        provider = self.provider_factory(
            output_dir=candidate_dir / "provider",
            model=self.model,
            coordinate_mode="integer",
            output_format="json",
            canvas_width=self.canvas_width,
            canvas_height=self.canvas_height,
            canvas_constraint="bounds_only",
            drawing_experience=experience,
        )
        # A non-zero temperature gives the selector genuinely different candidates.
        sketch, validation = Drawer(
            provider,
            DrawConfig(model=self.model, temperature=0.65 + 0.05 * (candidate_index - 1)),
        ).draw(prompt)
        if not validation.valid:
            raise RuntimeError("invalid 2D candidate: " + "; ".join(validation.errors))
        raw_response = str(sketch.metadata.pop("raw_response", ""))
        drawing_system_prompt = str(sketch.metadata.pop("drawing_system_prompt", ""))
        svg = render_svg(sketch)
        candidate_dir.mkdir(parents=True, exist_ok=True)
        (candidate_dir / "sketch.json").write_text(sketch.to_json(), encoding="utf-8")
        (candidate_dir / "raw_response.txt").write_text(raw_response, encoding="utf-8")
        (candidate_dir / "preview.svg").write_text(svg, encoding="utf-8")
        png_path = render_svg_png(
            svg,
            candidate_dir / "preview.png",
            width=self.canvas_width,
            height=self.canvas_height,
        )
        return Candidate2D(
            loop_index,
            candidate_index,
            sketch,
            svg,
            png_path,
            raw_response,
            drawing_system_prompt,
        )

    def _vision_json(self, system: str, text: str, candidates: list[Candidate2D]) -> dict[str, Any]:
        content: list[dict[str, Any]] = [{"type": "input_text", "text": text}]
        for candidate in candidates:
            content.append({"type": "input_text", "text": f"Candidate ID: {candidate.candidate_id}"})
            content.append({"type": "input_image", "image_url": _image_url(candidate.png_path)})
        response = self.client.responses.create(
            model=self.vision_model,
            input=[
                {"role": "system", "content": system},
                {"role": "user", "content": content},
            ],
            max_output_tokens=2400,
            **reasoning_options(self.reasoning_effort),
        )
        return _json_object(response.output_text or "")

    def _critique(self, prompt: str, candidates: list[Candidate2D]) -> dict[str, Any]:
        return self._vision_json(
            CRITIC_SYSTEM_PROMPT,
            "Drawing request: " + prompt + "\nReturn this schema: "
            '{"candidates":[{"candidate_id":"...","overall_strengths":["..."],'
            '"overall_weaknesses":["..."],"local_strengths":[{"part":"...","comment":"..."}],'
            '"local_weaknesses":[{"part":"...","comment":"..."}]}],"cross_candidate_observations":["..."]}',
            candidates,
        )

    def _select(self, prompt: str, candidates: list[Candidate2D]) -> dict[str, Any]:
        return self._vision_json(
            SELECTOR_SYSTEM_PROMPT,
            "Drawing request: " + prompt + "\nReturn this schema: "
            '{"selected_candidate_id":"loop_XX_candidate_XX","reason":"brief visual reason",'
            '"confidence":0.0}',
            candidates,
        )

    def _judge_progress(self, prompt: str, winners: list[Candidate2D]) -> dict[str, Any]:
        result = self._vision_json(
            PROGRESS_SYSTEM_PROMPT,
            "Drawing request: " + prompt + "\nThe candidates are loop winners in chronological order. "
            "For the first loop, set meaningful_improvement to true. Return this schema: "
            '{"best_candidate_id":"loop_XX_candidate_XX","meaningful_improvement":true,'
            '"reason":"brief comparison","confidence":0.0}',
            winners,
        )
        if len(winners) == 1:
            result["meaningful_improvement"] = True
        return result

    def _consolidate_experience(
        self,
        prompt: str,
        previous_experience: str,
        candidates: list[Candidate2D],
        critic: dict[str, Any],
    ) -> str:
        drawing_system_prompt = candidates[0].drawing_system_prompt
        svg_text = "\n\n".join(
            f"Candidate ID: {candidate.candidate_id}\n{candidate.svg}"
            for candidate in candidates
        )
        request = "\n\n".join([
            "Drawing request:\n" + prompt,
            "Drawing system prompt:\n" + drawing_system_prompt,
            "Previous complete experience (empty means none):\n" + (previous_experience or "None"),
            "SVG outputs from the previous drawing attempt:\n" + svg_text,
            "Critic evaluation of the full candidate batch:\n" + json.dumps(critic, ensure_ascii=False),
            "Rewrite the complete experience that the drawing model should use in the next loop.",
        ])
        response = self.client.responses.create(
            model=self.model,
            input=[
                {"role": "system", "content": EXPERIENCE_SYSTEM_PROMPT},
                {"role": "user", "content": request},
            ],
            max_output_tokens=1200,
            **reasoning_options(self.reasoning_effort),
        )
        text = (response.output_text or "").strip()
        if not text:
            raise RuntimeError("experience consolidator returned empty output")
        return text

    @staticmethod
    def _selected_candidate(
        result: dict[str, Any],
        candidates: list[Candidate2D],
        *,
        key: str = "selected_candidate_id",
    ) -> Candidate2D:
        selected_id = str(result.get(key, ""))
        by_id = {candidate.candidate_id: candidate for candidate in candidates}
        if selected_id not in by_id:
            raise ValueError(f"judge selected unknown candidate: {selected_id!r}")
        return by_id[selected_id]
