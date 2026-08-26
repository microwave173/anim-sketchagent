from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path

from .incremental import StructuredIncrementalPath3DLoop
from .reflection import StructuredReflectionPath3DLoop


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Structured JSON Path3D agent experiments")
    parser.add_argument("workflow", choices=("incremental", "reflection"))
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default=None)
    parser.add_argument("--vision-model", default=None)
    parser.add_argument("--width", type=int, default=512)
    parser.add_argument("--height", type=int, default=512)
    parser.add_argument("--max-rounds", type=int, default=8)
    parser.add_argument("--max-patch-attempts", type=int, default=3)
    parser.add_argument("--max-additions", type=int, default=48)
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--max-loops", type=int, default=2)
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        if args.workflow == "incremental":
            result = StructuredIncrementalPath3DLoop(
                output_dir=args.output, model=args.model, vision_model=args.vision_model,
                max_rounds=args.max_rounds, max_patch_attempts=args.max_patch_attempts,
                max_additions_per_patch=args.max_additions,
            ).run(args.prompt, width=args.width, height=args.height)
            payload = {
                "status": result.status, "workflow": args.workflow, "best_revision": result.best_revision,
                "best_preview": str(result.best_preview.resolve()) if result.best_preview else None,
                "rounds_completed": result.rounds_completed, "reason": result.reason,
                "run_wall_seconds": result.run_wall_seconds,
            }
        else:
            result = StructuredReflectionPath3DLoop(
                output_dir=args.output, model=args.model, vision_model=args.vision_model,
                samples=args.samples, max_loops=args.max_loops,
            ).run(args.prompt, width=args.width, height=args.height)
            payload = {
                "status": result.status, "workflow": args.workflow,
                "best_candidate_id": result.best_candidate_id,
                "best_preview": str(result.best_preview.resolve()),
                "loops_completed": result.loops_completed, "stopped_early": result.stopped_early,
                "run_wall_seconds": result.run_wall_seconds,
            }
        print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
        return 0
    except Exception as exc:
        print(json.dumps({
            "status": "error", "error_type": type(exc).__name__, "message": str(exc),
            "traceback": traceback.format_exc(),
        }, ensure_ascii=False, separators=(",", ":")))
        return 2


if __name__ == "__main__":
    sys.exit(main())
