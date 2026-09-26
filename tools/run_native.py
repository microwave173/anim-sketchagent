from __future__ import annotations

import argparse
import importlib
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    gate = argparse.ArgumentParser(add_help=False)
    gate.add_argument("--dim", type=int, choices=(2, 3), required=True)
    known, rest = gate.parse_known_args()
    anim = ROOT / "versions" / f"anim_sketchagent_{known.dim}d_v1" / "src"
    sys.path[:0] = [str(anim), str(ROOT / f"versions/path{known.dim}d_v1")]
    prompts = importlib.import_module("prompts")
    requested_frames = 120
    requested_keys = 12
    for flag, default in (("--frames", 120), ("--keys", 12)):
        if flag in rest:
            try:
                value = int(rest[rest.index(flag) + 1])
            except (ValueError, IndexError):
                value = default
            if flag == "--frames":
                requested_frames = value
            else:
                requested_keys = value
    prompts.MAX_FRAMES = max(int(prompts.MAX_FRAMES), requested_frames, 120)
    prompts.MAX_KEYS = max(int(prompts.MAX_KEYS), requested_keys, 12)
    native = importlib.import_module(f"glm_anim_{known.dim}d")
    native.MAX_FRAMES = prompts.MAX_FRAMES
    if hasattr(native, "MAX_KEYS"):
        native.MAX_KEYS = prompts.MAX_KEYS
    sys.argv = [sys.argv[0], *rest]
    native.main()


if __name__ == "__main__":
    main()
