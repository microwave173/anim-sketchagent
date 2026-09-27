"""One storyboard, one key batch, one generation per gap."""
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
from storyboard import parse_storyboard, gaps
from scene import protocol, validate_batch, static_anchor, pin_static
from render import export

HERE = Path(__file__).resolve().parent


def write(path: Path, value):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def run(prompt: str, dim: int, frames: int, frame_ms: int, out: Path, provider: Provider,
        size=512, debug=False, gap_workers=6):
    if gap_workers < 1:
        raise ValueError("gap_workers must be >= 1")
    out.mkdir(parents=True, exist_ok=True)
    request = {"prompt": prompt, "dim": dim, "frames": frames, "frame_ms": frame_ms,
               "size": size, "model": provider.model, "endpoint": provider.base,
               "thinking": True, "effort": provider.effort, "protocol": "light_v2_unified"}
    if (out / "request.json").exists() and json.loads((out / "request.json").read_text()) != request:
        raise ValueError("Output belongs to a different request; choose a fresh directory")
    write(out / "request.json", request)
    started = time.perf_counter()
    metrics = {"ok": False, "request": request, "stages": [], "calls": provider.calls,
               "gap_workers": gap_workers, "gap_context": "immutable_neighbor_keys"}
    metrics_lock = threading.RLock()
    if (out / "metrics.json").exists():
        previous = json.loads((out / "metrics.json").read_text())
        sessions = previous.pop("previous_sessions", [])
        metrics["previous_sessions"] = [*sessions, previous]
    guide = (HERE / "prompts/ANIMATION_GUIDE.md").read_text()
    if dim == 2:
        start = guide.index("## Drawing style")
        end = guide.index("## Show causes before consequences", start)
        guide = guide[:start] + (HERE / "prompts/STYLE_2D.md").read_text() + "\n\n" + guide[end:]
    drawing_target = ""
    if dim == 2:
        presentation = json.loads((HERE / "prompts/PRESENTATION_2D.json").read_text())
        native_size = min(size, presentation["raster_size"])
        drawing_target = (f"\nActual drawing target: {native_size}x{native_size} pixels, "
            f"{presentation['stroke_width']}px native ink; smooth antialiased enlargement to {size}x{size}. "
            "Design compact cute proportions and broad readable silhouettes for this small native canvas. "
            "Keep complete subjects and the decisive action; simplify detail rather than omitting objects. "
            "Leave enough space between meaningful lines. Path2D coordinates remain normalized [-1,1], not pixels.")
        guide += drawing_target
    spatial_guide = (HERE / "prompts/SPATIAL_3D.md").read_text() if dim == 3 else ""
    if spatial_guide:
        guide += "\n" + spatial_guide

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
            try:
                raw = provider.call(stage, system, user, max_tokens=getattr(provider, "max_tokens", None))
            except OutputLimitError as exc:
                with gzip.open(checkpoint.parent / f"{stage}_truncated.txt.gz", "wt") as f:
                    f.write(exc.content)
                metrics["stages"].append({"stage": stage, "failed": "output_length", "seconds": round(time.perf_counter()-t,3)})
                save()
                raise
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
        plan_system = (HERE / "prompts/PLANNER.md").read_text()
        if dim == 2:
            start = plan_system.index("The output uses")
            end = plan_system.index("\n\nPlan enough", start)
            plan_system = (plan_system[:start] +
                "The output uses expressive single-line stick figures in uniform black ink on white. "
                "People have plain round heads, open single-line torsos and single-line limbs; no clothing or body outlines. "
                "Make subjects large enough to recognize, with lively whole-body gestures and clear negative space around contacts. "
                "Animals have flowing closed silhouettes and unmistakable species features; props keep diagnostic structural details. "
                "Plan simple staging that makes the action immediately readable, without decorative clutter. "
                "Explicit user appearance requests override defaults." + plan_system[end:])
            plan_system += drawing_target
        if spatial_guide:
            plan_system += "\n" + spatial_guide
        plan_user = f"User request: {prompt}\nDimension: {dim}D\nPlayback: {frames} frames, {frame_ms} ms/frame, {frames*frame_ms/1000:.2f} seconds."
        def decode_plan(raw):
            text = raw.strip()
            if text.startswith("```markdown") and text.endswith("```"):
                text = text[11:-3].strip()
            story = parse_storyboard(text, frames)
            (out / "storyboard.md").write_text(text + "\n")
            return story
        story = generate("plan", plan_system, plan_user, decode_plan)
        story_text = (out / "storyboard.md").read_text()
        key_system = guide + "\n" + (HERE / "prompts/KEYFRAMES.md").read_text() + "\n" + protocol(dim)
        key_user = (story_text + f"\nRequested key indices: {story['key_indices']}. Initial frame shows the story BEFORE the first event. "
                    "At each later requested frame show the exit state of the beat ending there. "
                    'Also return top-level "static_ids": IDs of immutable scenery visible throughout. '
                    "Never include actors, moving handles, fire, water, or transforming objects in static_ids. "
                    "Choose your own strokes; no predefined parts inventory or stroke count. "
                    "Register all IDs needed for later events in the keys where they are visible, not prematurely in frame 1.")
        def decode_keys(raw):
            value = json_object(raw)
            keyframes = validate_batch(value, story["key_indices"], dim, prompt)
            anchor = static_anchor(keyframes, value.get("static_ids", []))
            return {i: pin_static(f, anchor) for i,f in keyframes.items()}, anchor
        keys, anchor = generate("keys", key_system, key_user, decode_keys)
        registry = {s["id"] for f in keys.values() for s in f["strokes"]}
        all_frames = dict(keys)
        def draw_gap(index, gap):
            left, right = gap["from"], gap["to"]
            previous_key = next((keys[i] for i in reversed(sorted(keys)) if i < left), None)
            next_key = next((keys[i] for i in sorted(keys) if i > right), None)
            context = {"identity_reference": keys[1], "from": keys[left], "to": keys[right],
                       "previous_key": previous_key, "next_key": next_key}
            user = (story_text + "\nInterval beat: " + json.dumps(gap["beat"], ensure_ascii=False) +
                    f"\nGenerate exactly {gap['indices']} in ascending order, not the endpoint frames. "
                    f"Full clip: {frames} frames × {frame_ms}ms. Registered IDs: {sorted(registry)}. "
                    "Use those IDs only, without requiring absent objects to be visible. "
                    "Preserve the appearance reference, but advance motion from FROM toward TO. "
                    "Use previous_key and next_key as motion context, not adjacent frames: respect their frame indices. "
                    "Continue motion through keys rather than stopping at each key; infer boundary motion from the timed neighboring poses and story. "
                    "Keep prerequisities and consequences in story order; do not show the endpoint's completed effect too early. "
                    "Draw a complete scene per frame.\nContext:\n" + json.dumps(context, ensure_ascii=False))
            system = guide + "\n" + protocol(dim)
            def interval(stage, wanted, request_user, references):
                previous_calls = [c for session in metrics.get("previous_sessions", []) for c in session.get("calls", [])]
                prior_truncation = any(c.get("stage") == stage and c.get("finish_reason") == "length"
                                       for c in [*previous_calls, *provider.calls])
                cached = out / "checkpoints" / f"{stage}.json"
                split = prior_truncation and getattr(provider, "max_tokens", None) is None and len(wanted) > 1 and not cached.exists()
                if not split:
                    try:
                        return generate(stage, system, request_user,
                            lambda raw: validate_batch(json_object(raw), wanted, dim, prompt, registry))
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
                        refs["previous_frame"] = result.get(end-1, keys.get(end-1))
                    def compact(frame):
                        if frame is None:
                            return None
                        return {"i": frame["i"], "strokes": [{k:s[k] for k in ("id","path","description")}
                                for s in frame["strokes"]]}
                    refs = {k:compact(f) for k,f in refs.items()}
                    start = refs["from"]["i"]
                    target = refs["to"]["i"]
                    progress = [{"i":i,"t":round((i-start)/(target-start),4)} for i in subset]
                    header = request_user.split("\nThis is a partial batch", 1)[0].split("\nContext:\n", 1)[0]
                    header = header.replace(f"Generate exactly {wanted} in ascending order", f"Generate exactly {subset} in ascending order")
                    piece_user = (header + "\nThis is a partial batch of the SAME gap. TO is still the final key; "
                                  "do not reach it early or stop at a batch boundary. Progress from the current FROM toward TO: " +
                                  json.dumps(progress) + "\nContext:\n" + json.dumps(refs,ensure_ascii=False))
                    values = interval(stage + "_" + label, subset, piece_user, refs)
                    result.update({i:pin_static(f,anchor) for i,f in values.items()})
                write(cached, {"raw":json.dumps({"frames":[result[i] for i in wanted]}),
                               "input_sha256":hashlib.sha256((system+"\n\n"+request_user).encode()).hexdigest(),
                               "assembled_from_batches":True})
                save()
                return result
            decoded = interval(f"gap_{index:02d}", gap["indices"], user, context)
            return {i: pin_static(f, anchor) for i,f in decoded.items()}

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
        write(out / "animation.json", {"dimension": dim, "frame_ms": frame_ms, "static_ids": sorted(anchor),
                                        "key_indices": story["key_indices"], "frames": [all_frames[i] for i in sorted(all_frames)]})
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
