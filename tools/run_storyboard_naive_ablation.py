"""Run ordinary naive vs storyboard-conditioned naive on one 60-frame story."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import gzip
import json
from pathlib import Path
import sys
import time

PROJECT = Path("/root/autodl-tmp/anim-sketchagent")
sys.path.insert(0, str(PROJECT / "light_agent"))

from naive import run as run_naive
from provider import Provider
from storyboard import parse_storyboard

PROMPT = ("Create a short silent cartoon in an exaggerated slapstick style: a cat sets a clever trap "
          "for a mouse, but the mouse outsmarts the cat and the trap backfires. Make the setup and payoff "
          "visually clear. No captions.")
FRAMES = 60
FRAME_MS = 120
SIZE = 640
MAX_TOKENS = 393216
ROOT = PROJECT / "outputs/storyboard_naive_ablation_60f"


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def make_storyboard(out: Path, provider: Provider) -> str:
    planner = (PROJECT / "light_agent/prompts/PLANNER.md").read_text(encoding="utf-8")
    start = planner.index("The output uses")
    end = planner.index("\n\nPlan enough", start)
    planner = (planner[:start] +
        "The output uses expressive single-line stick figures in uniform black ink on white. "
        "People have plain round heads, open single-line torsos and single-line limbs; no clothing or body outlines. "
        "Animals have flowing closed silhouettes and unmistakable species features. Keep quadrupeds on four legs and let them use mouths, paws, heads and body weight naturally; never make them stand or manipulate props like humans unless explicitly requested. Props keep diagnostic structural details. "
        "Stage moving characters and objects modestly within the canvas and reserve room for the complete motion. "
        "Plan simple staging that makes the action immediately readable. Explicit user appearance requests override defaults." +
        planner[end:])
    user = (f"User request: {PROMPT}\nDimension: 2D\nPlayback: {FRAMES} frames, "
            f"{FRAME_MS} ms/frame, {FRAMES*FRAME_MS/1000:.2f} seconds.")
    (out / "storyboard_plan_prompt.txt").write_text(planner + "\n\nUSER\n" + user, encoding="utf-8")
    last_error = None
    for attempt in range(1, 3):
        raw = provider.call("storyboard_plan", planner, user, max_tokens=MAX_TOKENS)
        with gzip.open(out / f"storyboard_plan_response_{attempt}.txt.gz", "wt", encoding="utf-8") as handle:
            handle.write(raw)
        text = raw.strip()
        if text.startswith("```markdown") and text.endswith("```"):
            text = text[11:-3].strip()
        try:
            parse_storyboard(text, FRAMES)
            (out / "storyboard.md").write_text(text + "\n", encoding="utf-8")
            write_json(out / "storyboard_plan_metrics.json", {
                "attempts": attempt, "repair_error": last_error, "calls": provider.calls,
            })
            return text
        except (ValueError, KeyError, TypeError) as exc:
            last_error = str(exc)
            user += (f"\nYour previous output failed structural validation: {last_error}. "
                     "Generate a corrected full response for the same request.")
    raise ValueError(last_error)


def ordinary() -> dict:
    out = ROOT / "ordinary_naive"
    return run_naive(PROMPT, 2, FRAMES, FRAME_MS, out,
        Provider("official", "high", 1800, MAX_TOKENS), SIZE, True)


def storyboard_conditioned() -> dict:
    out = ROOT / "storyboard_naive"
    out.mkdir(parents=True, exist_ok=True)
    provider = Provider("official", "high", 1800, MAX_TOKENS)
    storyboard = make_storyboard(out, provider)
    return run_naive(PROMPT, 2, FRAMES, FRAME_MS, out, provider, SIZE, True, storyboard)


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    write_json(ROOT / "experiment.json", {
        "prompt": PROMPT, "frames": FRAMES, "frame_ms": FRAME_MS, "duration_seconds": 7.2,
        "size": SIZE, "max_tokens": MAX_TOKENS, "effort": "high",
        "controlled_difference": "storyboard text added to the renderer user context",
        "shared_system_prompt": "light_agent/prompts/FRAME_BATCH.md",
    })
    started = time.perf_counter()
    results = {}
    with ThreadPoolExecutor(max_workers=2) as executor:
        pending = {executor.submit(ordinary): "ordinary_naive",
                   executor.submit(storyboard_conditioned): "storyboard_naive"}
        for future in as_completed(pending):
            name = pending[future]
            try:
                results[name] = {"ok": True, "metrics": future.result()}
            except BaseException as exc:
                results[name] = {"ok": False, "error_type": type(exc).__name__, "error": str(exc)}
            write_json(ROOT / "status.json", results)
    write_json(ROOT / "status.json", {"wall_seconds": round(time.perf_counter()-started, 3), **results})
    if not all(item["ok"] for item in results.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
