"""Command line entry point for the single-response baseline."""
from __future__ import annotations

import argparse
from pathlib import Path

from naive import run
from provider import Provider


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate every animation frame in one model response")
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--dim", type=int, choices=(2, 3), default=2)
    parser.add_argument("--frames", type=int, default=24)
    parser.add_argument("--frame-ms", type=int, default=120)
    parser.add_argument("--size", type=int, default=640)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--api-profile", choices=("official", "env"), default="official")
    parser.add_argument("--effort", choices=("low", "high", "max"), default="high")
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--max-tokens", type=int, default=393216)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()
    if args.frames < 2 or args.frame_ms < 10 or args.size < 64 or args.max_tokens < 1024:
        parser.error("frames >= 2, frame-ms >= 10, size >= 64, max-tokens >= 1024 required")
    run(args.prompt, args.dim, args.frames, args.frame_ms, args.out,
        Provider(args.api_profile, args.effort, args.timeout, args.max_tokens), args.size, args.debug)


if __name__ == "__main__":
    main()
