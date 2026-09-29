"""Replay one saved KeyGap keys request verbatim and persist reasoning_content."""
from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path
import sys
import time

PROJECT = Path("/root/autodl-tmp/anim-sketchagent")
SOURCE = PROJECT / "outputs/keygap_v4_cat_mouse_natural_60f"
OUT = PROJECT / "outputs/keygap_v4_cat_mouse_natural_60f_keys_replay_reasoning"
sys.path.insert(0, str(PROJECT / "light_agent"))

from provider import Provider, json_object
from scene import public_frames, validate_batch


def write(path: Path, value) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    combined = (SOURCE / "checkpoints/keys_prompt.txt").read_text(encoding="utf-8")
    marker = "\n\nUSER\n"
    if marker not in combined:
        raise ValueError("Saved keys prompt has no USER separator")
    system, user = combined.split(marker, 1)
    (OUT / "keys_prompt.txt").write_text(combined, encoding="utf-8")

    original_checkpoint = json.loads((SOURCE / "checkpoints/keys.json").read_text(encoding="utf-8"))
    original = json_object(original_checkpoint["raw"])
    wanted = [frame["i"] for frame in original["frames"]]
    request = {
        "source": str(SOURCE),
        "source_prompt_sha256": hashlib.sha256(combined.encode()).hexdigest(),
        "wanted": wanted,
        "model_profile": "official",
        "effort": "high",
        "max_tokens": 393216,
        "timeout": 1800,
        "scope": "exact keys request replay only",
    }
    write(OUT / "request.json", request)

    provider = Provider("official", "high", 1800, 393216)
    started = time.perf_counter()
    metrics = {"ok": False, "request": request}
    try:
        raw = provider.call("keys_replay", system, user, max_tokens=393216)
        reasoning = provider.pop_reasoning("keys_replay")
        with gzip.open(OUT / "keys_reasoning.txt.gz", "wt", encoding="utf-8") as handle:
            handle.write(reasoning)
        with gzip.open(OUT / "keys_response.txt.gz", "wt", encoding="utf-8") as handle:
            handle.write(raw)
        value = json_object(raw)
        frames = validate_batch(value, wanted, 2, "cat and mouse keys replay")
        write(OUT / "keys_frames.json", {"frames": public_frames(frames, 2)})
        metrics.update(ok=True, returned_frames=len(frames), response_chars=len(raw),
                       reasoning_chars=len(reasoning), calls=provider.calls)
    except BaseException as exc:
        reasoning = provider.pop_reasoning("keys_replay")
        if reasoning:
            with gzip.open(OUT / "keys_reasoning.txt.gz", "wt", encoding="utf-8") as handle:
                handle.write(reasoning)
        metrics.update(error_type=type(exc).__name__, error=str(exc), calls=provider.calls,
                       reasoning_chars=len(reasoning))
        raise
    finally:
        metrics["wall_seconds"] = round(time.perf_counter() - started, 3)
        write(OUT / "metrics.json", metrics)


if __name__ == "__main__":
    main()
