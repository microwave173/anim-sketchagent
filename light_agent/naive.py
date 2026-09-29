"""Single-call baseline using the same scene schema and renderer as the staged agent."""
from __future__ import annotations

import gzip
import json
from pathlib import Path
import time

from provider import Provider, OutputLimitError, json_object
from drawing_prompt import frame_batch_system
from scene import SVG_STROKE, public_frames, validate_batch
from render import export

HERE = Path(__file__).resolve().parent


def _write(path: Path, value: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def system_prompt(dim: int, size: int) -> str:
    return frame_batch_system(dim, size)


def run(prompt: str, dim: int, frames: int, frame_ms: int, out: Path,
        provider: Provider, size: int = 640, debug: bool = False,
        storyboard: str | None = None) -> dict:
    if not prompt.strip() or dim not in (2, 3) or frames < 2 or frame_ms < 10 or size < 64:
        raise ValueError("Need a prompt, dim 2/3, frames >= 2, frame_ms >= 10, size >= 64")
    out.mkdir(parents=True, exist_ok=True)
    request = {"prompt": prompt, "dim": dim, "frames": frames, "frame_ms": frame_ms,
               "size": size, "model": provider.model, "endpoint": provider.base,
               "thinking": True, "effort": provider.effort, "protocol": "naive_one_shot_v2_shared_drawer",
               "conditioning": "storyboard" if storyboard else "original_prompt_only"}
    request_path = out / "request.json"
    if request_path.exists() and json.loads(request_path.read_text(encoding="utf-8")) != request:
        raise ValueError("Output belongs to a different request; choose a fresh directory")
    _write(request_path, request)
    if (out / "animation.json").exists():
        raise ValueError("Output already contains a completed animation; choose a fresh directory")
    system = system_prompt(dim, size)
    user = (f"User request: {prompt}\nDimension: {dim}D\n"
            f"Playback: {frames} frames, {frame_ms} ms/frame, {frames*frame_ms/1000:.2f} seconds.\n"
            f"Assigned interval: the complete clip, frames 1 through {frames}.\n")
    if storyboard:
        user += ("Use this externally prepared storyboard as temporal guidance while drawing the complete clip. "
                 "Preserve the original request and do not output the storyboard itself.\n\n" + storyboard.strip() + "\n\n")
    user += f"Return exactly frames 1 through {frames}, all in this one JSON object."
    if debug:
        (out / "one_shot_prompt.txt").write_text(system + "\n\nUSER\n" + user, encoding="utf-8")
    started = time.perf_counter()
    metrics = {"ok": False, "request": request, "generation_protocol": "single_response",
               "semantic_generation_calls": 0, "stages": [], "calls": provider.calls}

    def save() -> None:
        metrics["wall_seconds"] = round(time.perf_counter() - started, 3)
        _write(out / "metrics.json", {**metrics, "calls": list(provider.calls)})

    try:
        stage_started = time.perf_counter()
        metrics["semantic_generation_calls"] = 1
        try:
            raw = provider.call("one_shot", system, user, max_tokens=provider.max_tokens)
        except OutputLimitError as exc:
            reasoning = provider.pop_reasoning("one_shot") if hasattr(provider, "pop_reasoning") else ""
            if debug and reasoning:
                with gzip.open(out / "one_shot_reasoning.txt.gz", "wt", encoding="utf-8") as file:
                    file.write(reasoning)
            with gzip.open(out / "one_shot_truncated.txt.gz", "wt", encoding="utf-8") as file:
                file.write(exc.content)
            raise
        reasoning = provider.pop_reasoning("one_shot") if hasattr(provider, "pop_reasoning") else ""
        if debug and reasoning:
            with gzip.open(out / "one_shot_reasoning.txt.gz", "wt", encoding="utf-8") as file:
                file.write(reasoning)
        with gzip.open(out / "one_shot_response.txt.gz", "wt", encoding="utf-8") as file:
            file.write(raw)
        value = json_object(raw)
        all_frames = validate_batch(value, list(range(1, frames + 1)), dim, prompt)
        metrics["stages"].append({"stage": "one_shot", "seconds": round(time.perf_counter() - stage_started, 3),
                                  "output_chars": len(raw)})
        animation = {"dimension": dim, "frame_ms": frame_ms,
                     "generation_protocol": "naive_one_shot_v2_shared_drawer",
                     "conditioning": "storyboard" if storyboard else "original_prompt_only",
                     "frames": public_frames(all_frames, dim),
                     "geometry_format": "standard_svg_path_data" if dim == 2 else "spatial_path3d_with_standard_svg_projection",
                     "svg_style": {"fill": "none", "stroke": SVG_STROKE,
                                   "stroke_width": "fixed by presentation.json",
                                   "stroke_linecap": "round", "stroke_linejoin": "round"}}
        if dim == 2:
            animation["svg_coordinate_system"] = "viewBox coordinates in [-1,1], +y up via root transform"
        else:
            animation["projected_svg"] = "animation.svg and frames_svg/frame_XXXX.svg"
        _write(out / "animation.json", animation)
        render_started = time.perf_counter()
        export(all_frames, out, dim, frame_ms, size, prompt)
        metrics["stages"].append({"stage": "render", "seconds": round(time.perf_counter() - render_started, 3)})
        metrics.update(ok=True, n_frames=frames, generation_calls=len(provider.calls),
                       quality_review="Structural validation only; visual inspection is separate")
        save()
        return metrics
    except BaseException as exc:
        metrics.update(error_type=type(exc).__name__, error=str(exc))
        save()
        raise
