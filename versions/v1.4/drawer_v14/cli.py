from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path

from .three_d import IncrementalPath3DLoop
from .two_d import IncrementalDrawerLoop


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Drawer v1.4 incremental 2D/3D CLI tool")
    parser.add_argument("--mode", choices=("2d", "3d"), required=True)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--width", type=int, default=512)
    parser.add_argument("--height", type=int, default=512)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default=None)
    parser.add_argument("--max-rounds", type=int, default=8)
    parser.add_argument("--max-patch-attempts", type=int, default=3)
    parser.add_argument("--max-additions", type=int, default=6)
    parser.add_argument("--outline-only", action="store_true", help="2D only: require fill='none'.")
    parser.add_argument("--no-spatial-annotation", action="store_true", help="Skip final vision landmark/local-frame annotation.")
    parser.add_argument("--landmark-model", default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        if args.mode == "3d" and args.outline_only:
            raise ValueError("--outline-only is a 2D-only option")
        common = {
            "output_dir": args.output,
            "model": args.model,
            "max_rounds": args.max_rounds,
            "max_patch_attempts": args.max_patch_attempts,
            "max_additions_per_patch": args.max_additions,
        }
        if args.mode == "2d":
            loop = IncrementalDrawerLoop(**common, outline_only=args.outline_only)
        else:
            loop = IncrementalPath3DLoop(**common)
        result = loop.run(args.prompt, width=args.width, height=args.height)
        spatial = None
        if result.best_revision and not args.no_spatial_annotation:
            from manager_tools_v2 import ArtifactLandmarkAgent, SpatialArtifactFinalizer
            final_dir = args.output / "final"
            source = final_dir / ("sketch.svg" if args.mode == "2d" else "scene.json")
            preview = final_dir / ("preview.png" if args.mode == "2d" else "views/contact_sheet.png")
            artifact_id = args.output.name.replace("-", "_").replace(" ", "_")
            spatial = SpatialArtifactFinalizer(
                landmark_agent=ArtifactLandmarkAgent(model=args.landmark_model or args.model),
            ).finalize(
                artifact_id=artifact_id, prompt=args.prompt, kind=args.mode,
                source_path=source, output_dir=final_dir, preview_paths=[preview],
                width=args.width, height=args.height,
            )
        payload = {
            "status": result.status,
            "mode": args.mode,
            "best_revision": result.best_revision,
            "best_preview": str(result.best_preview.resolve()) if result.best_preview else None,
            "rounds_completed": result.rounds_completed,
            "trajectory_path": str(result.trajectory_path.resolve()),
            "plan_path": str(result.plan_path.resolve()),
            "reason": result.reason,
            "run_wall_seconds": result.run_wall_seconds,
            "spatial_manifest_path": spatial["spatial_manifest_path"] if spatial else None,
        }
        print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
        return 0 if result.best_revision else 1
    except Exception as exc:
        print(json.dumps({
            "status": "error", "error_type": type(exc).__name__, "message": str(exc),
            "traceback": traceback.format_exc(),
        }, ensure_ascii=False, separators=(",", ":")))
        return 2


if __name__ == "__main__":
    sys.exit(main())
