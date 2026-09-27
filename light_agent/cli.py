from __future__ import annotations

import argparse
from pathlib import Path

from pipeline import run
from provider import Provider


def main():
    parser = argparse.ArgumentParser(description="Unified lightweight key-batch + gap animation")
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--dim", type=int, choices=(2, 3), default=2)
    parser.add_argument("--frames", type=int, default=40)
    parser.add_argument("--frame-ms", type=int, default=120)
    parser.add_argument("--size", type=int, default=512)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--api-profile", choices=("official", "env"), default="official")
    parser.add_argument("--effort", choices=("low", "high", "max"), default="high")
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--max-tokens", type=int, default=393216, help="Explicit output budget for every stage; default 384K (393216)")
    parser.add_argument("--gap-workers", type=int, default=6, help="Concurrent gaps after the key batch; use 1 for serial")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()
    if args.gap_workers < 1 or args.frames < 2 or args.frame_ms < 10 or args.size < 64 or (args.max_tokens is not None and args.max_tokens < 1024):
        parser.error("frames >= 2, frame-ms >= 10, size >= 64, max-tokens >= 1024 required")
    run(args.prompt, args.dim, args.frames, args.frame_ms, args.out,
        Provider(args.api_profile, args.effort, args.timeout, args.max_tokens), args.size, args.debug, args.gap_workers)


if __name__ == "__main__":
    main()
