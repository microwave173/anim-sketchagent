"""Joint storyboard/key generation followed by one generation per gap."""
from __future__ import annotations

import gzip
import hashlib
import html
import json
from pathlib import Path
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from provider import Provider, OutputLimitError, json_object
from storyboard import parse_storyboard, parse_storyboard_value, storyboard_markdown, gaps
from json_plan import parse_json_plan
from drawing_prompt import frame_batch_system, joint_plan_key_system
from scene import validate_batch, public_frames, SVG_STROKE
from render import export

HERE = Path(__file__).resolve().parent


def write(path: Path, value):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def run(prompt: str, dim: int, frames: int, frame_ms: int, out: Path, provider: Provider,
        size=512, debug=False, gap_workers=6, plan_format="joint"):
    if gap_workers < 1:
        raise ValueError("gap_workers must be >= 1")
    if plan_format not in ("joint", "storyboard", "json"):
        raise ValueError("plan_format must be joint, storyboard or json")
    out.mkdir(parents=True, exist_ok=True)
    request = {"prompt": prompt, "dim": dim, "frames": frames, "frame_ms": frame_ms,
               "size": size, "model": provider.model, "endpoint": provider.base,
               "thinking": True, "effort": provider.effort,
               "protocol": "jointplankey_v2" if plan_format == "joint" else "keygap_v4_naive_draw_contract",
               "plan_format": plan_format}
    if (out / "request.json").exists() and json.loads((out / "request.json").read_text()) != request:
        raise ValueError("Output belongs to a different request; choose a fresh directory")
    write(out / "request.json", request)
    started = time.perf_counter()
    metrics = {"ok": False, "request": request, "stages": [], "calls": provider.calls,
               "gap_workers": gap_workers,
               "key_context": ("joint_storyboard_and_sparse_keys_single_request" if plan_format == "joint"
                               else "naive_prompt_plus_sparse_indices"),
               "gap_context": "naive_prompt_plus_endpoint_keys"}
    metrics_lock = threading.RLock()
    if (out / "metrics.json").exists():
        previous = json.loads((out / "metrics.json").read_text())
        sessions = previous.pop("previous_sessions", [])
        metrics["previous_sessions"] = [*sessions, previous]
    presentation = json.loads((HERE / "prompts/PRESENTATION_2D.json").read_text())
    native_size = min(size, presentation["raster_size"])
    if dim == 2:
        drawing_target = (f"\nActual drawing target: {native_size}x{native_size} pixels, "
            f"{presentation['stroke_width']}px native ink; smooth antialiased enlargement to {size}x{size}. "
            "Design compact, readable subjects for this small native canvas while keeping moving characters and props modest in the frame. "
            "Reserve an open corridor for the full motion and the final pose; keep complete subjects and decisive contacts readable. "
            "Simplify detail rather than omitting objects. Leave enough space between meaningful lines. "
            "The visible Path2D canvas spans [-1,1], not pixels; off-canvas coordinates are valid but clipped.")
    else:
        drawing_target = (f"\nActual projected drawing target: {native_size}x{native_size} pixels, "
            f"{presentation['stroke_width']}px native black ink; smooth antialiased enlargement to {size}x{size}. "
            "Design real 3D geometry while judging its perspective projection at this small native size. "
            "Keep traveling actors and moving props modest in the projected frame, normally 20-35% of frame height, "
            "and reserve open screen and depth space for a large visible displacement and final pose. "
            "Keep contacts readable; simplify secondary wireframe detail rather than enlarging the whole scene. "
            "The primary visible Path3D world spans [-1,1], not pixels; projected off-canvas geometry may be clipped.")
    spatial_guide = (HERE / "prompts/SPATIAL_3D.md").read_text() if dim == 3 else ""

    def save():
        with metrics_lock:
            metrics["wall_seconds"] = round(time.perf_counter() - started, 3)
            metrics["cumulative_wall_seconds"] = round(metrics["wall_seconds"] + sum(
                s.get("wall_seconds", 0) for s in metrics.get("previous_sessions", [])), 3)
            metrics["cumulative_api_calls"] = len(provider.calls) + sum(
                len(s.get("calls", [])) for s in metrics.get("previous_sessions", []))
            write(out / "metrics.json", {**metrics, "calls": list(provider.calls), "stages": list(metrics["stages"])})
    def generate(stage, system, user, decode):
        checkpoint = out / "checkpoints" / f"{stage}.json"
        t = time.perf_counter()
        fingerprint = hashlib.sha256((system + "\n\n" + user).encode()).hexdigest()
        if checkpoint.exists():
            value = json.loads(checkpoint.read_text())
            if value.get("input_sha256") == fingerprint:
                result = decode(value["raw"])
                metrics["stages"].append({"stage": stage, "resumed": True, "seconds": round(time.perf_counter()-t,3)})
                save()
                return result
        checkpoint.parent.mkdir(exist_ok=True)
        if debug:
            (checkpoint.parent / f"{stage}_prompt.txt").write_text(system + "\n\nUSER\n" + user)
        last_error = None
        for attempt in range(1, 3):
            print(f"{stage}: generation {attempt}", flush=True)
            def save_reasoning():
                reasoning = provider.pop_reasoning(stage) if hasattr(provider, "pop_reasoning") else ""
                if debug and reasoning:
                    with gzip.open(checkpoint.parent / f"{stage}_reasoning_{attempt}.txt.gz", "wt") as f:
                        f.write(reasoning)
            try:
                raw = provider.call(stage, system, user, max_tokens=getattr(provider, "max_tokens", None))
            except OutputLimitError as exc:
                save_reasoning()
                with gzip.open(checkpoint.parent / f"{stage}_truncated.txt.gz", "wt") as f:
                    f.write(exc.content)
                metrics["stages"].append({"stage": stage, "failed": "output_length", "seconds": round(time.perf_counter()-t,3)})
                save()
                raise
            save_reasoning()
            with gzip.open(checkpoint.parent / f"{stage}_response_{attempt}.txt.gz", "wt") as f:
                f.write(raw)
            try:
                result = decode(raw)
                write(checkpoint, {"raw": raw, "input_sha256": fingerprint})
                metrics["stages"].append({"stage": stage, "seconds": round(time.perf_counter()-t,3),
                                           "generations": attempt, "repair_error": last_error})
                save()
                print(f"{stage}: complete ({metrics['stages'][-1]['seconds']}s)", flush=True)
                return result
            except (ValueError, KeyError, TypeError) as exc:
                last_error = str(exc)
                if attempt == 2:
                    raise
                user += f"\nYour previous output failed structural validation: {last_error}. Generate a corrected full response for the same request."
        raise RuntimeError(stage)

    try:
        drawing_system = frame_batch_system(dim, size)
        if plan_format == "joint":
            joint_system = joint_plan_key_system(dim, size)
            joint_user = (f"User request: {prompt}\nDimension: {dim}D\n"
                          f"Playback: {frames} frames, {frame_ms} ms/frame, "
                          f"{frames*frame_ms/1000:.2f} seconds.\n"
                          "Jointly finalize the storyboard and its sparse keyframes in one JSON response.")
            def decode_joint(raw):
                value = json_object(raw)
                story = parse_storyboard_value(value.get("storyboard"), frames)
                keys = validate_batch({"frames": value.get("frames")},
                                      story["key_indices"], dim, prompt)
                (out / "storyboard.md").write_text(storyboard_markdown(story), encoding="utf-8")
                public = public_frames(keys, dim)
                write(out / "joint_plan_keys.json", {
                    "storyboard": {key: story[key] for key in ("action", "notes", "beats", "key_indices")},
                    "frames": public,
                })
                return story, keys
            story, keys = generate("joint_plan_keys", joint_system, joint_user, decode_joint)
        else:
            planner_name = "PLANNER_JSON.md" if plan_format == "json" else "PLANNER.md"
            plan_system = (HERE / "prompts" / planner_name).read_text()
            if dim == 2 and plan_format == "storyboard":
                start = plan_system.index("The output uses")
                end = plan_system.index("\n\nPlan enough", start)
                plan_system = (plan_system[:start] +
                    "The output uses expressive single-line stick figures in uniform black ink on white. "
                    "People have plain round heads, open single-line torsos and single-line limbs; no clothing or body outlines. "
                    "Give human characters clearly circular heads and expressive single-line limbs. "
                    "Stage moving characters and objects modestly within the canvas, leaving room for the entire travel path and final pose while keeping contacts readable. "
                    "For walking or running, plan alternating leg leads, planted support, passing poses and natural opposing arm swing rather than rigid translation. "
                    "Animals have flowing closed silhouettes and unmistakable species features. Keep quadrupeds on four legs and let them use mouths, paws, heads and body weight naturally; never make them stand or manipulate props like humans unless explicitly requested. Props keep diagnostic structural details. "
                    "Plan simple staging that makes the action immediately readable, without decorative clutter. "
                    "Explicit user appearance requests override defaults." + plan_system[end:])
            plan_system += drawing_target
            if spatial_guide:
                plan_system += "\n" + spatial_guide
            plan_user = f"User request: {prompt}\nDimension: {dim}D\nPlayback: {frames} frames, {frame_ms} ms/frame, {frames*frame_ms/1000:.2f} seconds."
            def decode_plan(raw):
                if plan_format == "json":
                    story = parse_json_plan(json_object(raw), frames)
                    write(out / "plan.json", story["json_plan"])
                    return story
                text = raw.strip()
                if text.startswith("```markdown") and text.endswith("```"):
                    text = text[11:-3].strip()
                story = parse_storyboard(text, frames)
                (out / "storyboard.md").write_text(text + "\n")
                return story
            story = generate("plan", plan_system, plan_user, decode_plan)
            story_text = ((out / "plan.json").read_text() if plan_format == "json"
                          else (out / "storyboard.md").read_text())
            key_user = (f"User request: {story_text.strip()}\nDimension: {dim}D\n"
                        f"Playback: {frames} frames, {frame_ms} ms/frame, {frames*frame_ms/1000:.2f} seconds.\n"
                        f"Assigned sparse samples: frames {story['key_indices']} from the complete clip. "
                        "The first requested frame shows the state before the first event; each later requested frame shows the exit state of the beat ending at that index.\n"
                        f"Return exactly frames {story['key_indices']}, all in this one JSON object.")
            def decode_keys(raw):
                return validate_batch(json_object(raw), story["key_indices"], dim, prompt)
            keys = generate("keys", drawing_system, key_user, decode_keys)
        gap_system = drawing_system
        all_frames = dict(keys)
        def draw_gap(index, gap):
            left, right = gap["from"], gap["to"]
            def external(frame):
                return public_frames({frame["i"]: frame}, dim)[0]
            context = {"from": external(keys[left]), "to": external(keys[right])}
            beat = gap["beat"]
            local_prompt = beat["event"] + " Finish in this state: " + beat["exit"]
            interval_frames = right - left + 1
            user = (f"User request: {local_prompt}\nDimension: {dim}D\n"
                    f"Playback: {interval_frames} frames, {frame_ms} ms/frame, "
                    f"{interval_frames*frame_ms/1000:.2f} seconds.\n"
                    f"Assigned interval: frames {left} through {right} of the larger clip. "
                    "FROM and TO below are accepted endpoint frames and must not be regenerated.\n"
                    f"Return exactly frames {gap['indices']}, all in this one JSON object.\n"
                    "Boundary keyframes:\n" + json.dumps(context, ensure_ascii=False))
            system = gap_system
            def interval(stage, wanted, request_user, references):
                previous_calls = [c for session in metrics.get("previous_sessions", []) for c in session.get("calls", [])]
                prior_truncation = any(c.get("stage") == stage and c.get("finish_reason") == "length"
                                       for c in [*previous_calls, *provider.calls])
                cached = out / "checkpoints" / f"{stage}.json"
                split = prior_truncation and getattr(provider, "max_tokens", None) is None and len(wanted) > 1 and not cached.exists()
                if not split:
                    try:
                        return generate(stage, system, request_user,
                            lambda raw: validate_batch(json_object(raw), wanted, dim, prompt))
                    except OutputLimitError:
                        if len(wanted) == 1:
                            raise
                print(f"{stage}: splitting {len(wanted)} frames after output truncation", flush=True)
                result = {}
                midpoint = len(wanted) // 2
                for label, subset in zip(("a", "b"), (wanted[:midpoint], wanted[midpoint:])):
                    refs = dict(references)
                    if result:
                        end = max(result)
                        refs["from"] = result[end]
                    def compact(frame):
                        if frame is None:
                            return None
                        path_key = "d" if dim == 2 else "path"
                        return {"i": frame["i"], "strokes": [
                            {"id": s["id"], path_key: s.get(path_key, s.get("path")),
                             "description": s["description"]} for s in frame["strokes"]]}
                    refs = {k:compact(f) for k,f in refs.items()}
                    start = refs["from"]["i"]
                    target = refs["to"]["i"]
                    progress = [{"i":i,"t":round((i-start)/(target-start),4)} for i in subset]
                    header = request_user.split("\nThis is a partial batch", 1)[0].split("\nBoundary keyframes:\n", 1)[0]
                    header = header.replace(f"Return exactly frames {wanted}, all in this one JSON object",
                                            f"Return exactly frames {subset}, all in this one JSON object")
                    piece_user = (header + "\nThis is a partial batch of the SAME gap. TO is still the final key; "
                                  "do not reach it early or stop at a batch boundary. Progress from the current FROM toward TO: " +
                                  json.dumps(progress) + "\nBoundary keyframes:\n" + json.dumps(refs,ensure_ascii=False))
                    values = interval(stage + "_" + label, subset, piece_user, refs)
                    result.update(values)
                write(cached, {"raw":json.dumps({"frames":[result[i] for i in wanted]}),
                               "input_sha256":hashlib.sha256((system+"\n\n"+request_user).encode()).hexdigest(),
                               "assembled_from_batches":True})
                save()
                return result
            decoded = interval(f"gap_{index:02d}", gap["indices"], user, context)
            return decoded

        gap_started = time.perf_counter()
        jobs = [(index, gap) for index, gap in enumerate(gaps(story), 1) if gap["indices"]]
        failures = []
        with ThreadPoolExecutor(max_workers=gap_workers) as executor:
            pending = {executor.submit(draw_gap, index, gap): index for index, gap in jobs}
            for future in as_completed(pending):
                try:
                    all_frames.update(future.result())
                except Exception as exc:
                    failures.append((pending[future], exc))
        metrics["gap_wall_seconds"] = round(time.perf_counter() - gap_started, 3)
        if failures:
            metrics["gap_failures"] = [{"gap": i, "error": str(exc)} for i, exc in failures]
            raise failures[0][1]
        if sorted(all_frames) != list(range(1, frames + 1)):
            raise ValueError("Incomplete final timeline")
        animation = {"dimension": dim, "frame_ms": frame_ms,
                     "key_indices": story["key_indices"], "frames": public_frames(all_frames, dim)}
        if dim == 2:
            animation.update({"geometry_format": "standard_svg_path_data",
                              "svg_coordinate_system": "viewBox coordinates in [-1,1], +y up via root transform",
                              "svg_style": {"fill": "none", "stroke": SVG_STROKE,
                                            "stroke_width": "fixed by presentation.json",
                                            "stroke_linecap": "round", "stroke_linejoin": "round"}})
        else:
            animation.update({"geometry_format": "spatial_path3d_with_standard_svg_projection",
                              "projected_svg": "animation.svg and frames_svg/frame_XXXX.svg",
                              "svg_style": {"fill": "none", "stroke": SVG_STROKE,
                                            "stroke_width": "fixed by presentation.json",
                                            "stroke_linecap": "round", "stroke_linejoin": "round"}})
        write(out / "animation.json", animation)
        t = time.perf_counter()
        export(all_frames, out, dim, frame_ms, size, prompt)
        metrics["stages"].append({"stage": "render", "seconds": round(time.perf_counter()-t,3)})
        metrics.update(ok=True, n_frames=frames, n_keys=len(keys), generation_calls=len(provider.calls),
                       quality_review="Structural validation only; visual inspection is separate")
        save()
        page = out / "index.html"
        if page.exists():
            view = {"wall_seconds": metrics["wall_seconds"], "n_frames": frames,
                    "n_keys": len(keys), "generation_calls": len(provider.calls), "stages": metrics["stages"]}
            page.write_text(page.read_text().replace('<pre id="metrics"></pre>',
                '<pre id="metrics">' + html.escape(json.dumps(view, ensure_ascii=False, indent=2)) + '</pre>'))
        print(f"Finished: {out / 'clip.gif'} ({metrics['wall_seconds']}s)", flush=True)
    except BaseException as exc:
        metrics.update(error_type=type(exc).__name__, error=str(exc))
        save()
        raise
