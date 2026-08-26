from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
import traceback
from pathlib import Path

from .service import DrawerService


class ToolArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError(message)


def build_parser() -> argparse.ArgumentParser:
    parser = ToolArgumentParser(description="Agent tool: draw canonical 2D/3D JSON from a prompt.")
    parser.add_argument("--mode", required=True, choices=("2d", "3d"))
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--width", required=True, type=int, help="canvas width in pixels (64..4096)")
    parser.add_argument("--height", required=True, type=int, help="canvas height in pixels (64..4096)")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--samples", type=int, default=None, help="candidates per loop (default: 2D=3, 3D=2)")
    parser.add_argument("--epochs", type=int, default=2, help="maximum 2D/3D learning loops (default: 2)")
    return parser


def main(argv: list[str] | None = None) -> int:
    diagnostics = io.StringIO()
    try:
        args = build_parser().parse_args(argv)
        with contextlib.redirect_stdout(diagnostics):
            result = DrawerService(
                samples=max(1, args.samples) if args.samples is not None else None,
                epochs=max(1, args.epochs),
            ).draw(
                args.mode,
                args.prompt,
                args.output,
                width=args.width,
                height=args.height,
            )
        payload = {
            "status": "success",
            "mode": result.mode,
            "canvas": {"width": args.width, "height": args.height},
            "output_dir": str(result.output_dir.resolve()),
            "canonical_path": str(result.sketch_json.resolve()),
            "manifest_path": str(result.manifest.resolve()),
            "preview_paths": [
                str(result.preview_svg.resolve()),
                *(str(path.resolve()) for path in result.preview_images),
            ],
        }
        captured = diagnostics.getvalue().strip()
        if captured:
            payload["diagnostics"] = captured.splitlines()
        print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
        return 0
    except Exception as exc:
        payload = {
            "status": "error",
            "error_type": type(exc).__name__,
            "message": str(exc),
        }
        captured = diagnostics.getvalue().strip()
        if captured:
            payload["diagnostics"] = captured.splitlines()
        print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
        return 2 if isinstance(exc, ValueError) else 1


if __name__ == "__main__":
    sys.exit(main())
