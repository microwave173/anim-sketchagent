from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path
from time import perf_counter

from path3d.renderer import render_scene_views

from .compiler import compile_scene
from .generator import StructuredPath3DGenerator


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Single-shot structured JSON Path3D generator")
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default=None)
    parser.add_argument("--width", type=int, default=512)
    parser.add_argument("--height", type=int, default=512)
    started = perf_counter()
    try:
        args = parser.parse_args(argv)
        if args.output.exists():
            raise FileExistsError(f"output already exists: {args.output}")
        args.output.mkdir(parents=True)
        generator = StructuredPath3DGenerator(model=args.model)
        raw = generator.generate_raw(args.prompt)
        (args.output / "raw_response.txt").write_text(raw, encoding="utf-8")
        structured = generator.parse_response(raw, prompt=args.prompt)
        (args.output / "structured_scene.json").write_text(structured.to_json(), encoding="utf-8")
        compiled = compile_scene(structured)
        (args.output / "scene.json").write_text(compiled.to_json(), encoding="utf-8")
        paths = render_scene_views(compiled, args.output / "views", width=args.width, height=args.height)
        result = {
            "status": "complete",
            "structured_scene": str((args.output / "structured_scene.json").resolve()),
            "compiled_scene": str((args.output / "scene.json").resolve()),
            "views": [str(path.resolve()) for path in paths],
            "contact_sheet": str((args.output / "views" / "contact_sheet.png").resolve()),
            "stroke_count": len(compiled.strokes),
            "command_count": sum(len(stroke.commands) for stroke in structured.strokes),
            "run_wall_seconds": perf_counter() - started,
        }
        (args.output / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result, separators=(",", ":")))
        return 0
    except Exception as exc:
        print(json.dumps({
            "status": "error",
            "error_type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(),
        }, ensure_ascii=False, separators=(",", ":")))
        return 2


if __name__ == "__main__":
    sys.exit(main())
