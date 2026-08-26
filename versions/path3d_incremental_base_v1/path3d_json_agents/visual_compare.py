from __future__ import annotations

import argparse
import json
import shutil
import sys
import traceback
from pathlib import Path

from .common import ResponsesRole, image_url, write_json


SYSTEM_PROMPT = """You are a strict blind visual evaluator of 3D spatial line drawings. You receive labeled contact sheets, each ordered front, side, top, perspective. Judge only the rendered images against the target. Rank every sample and give an absolute verdict.

Evaluate immediate target recognizability, coherent anatomy and silhouette, actual 3D consistency across all four views, connected parts, proportions, smooth purposeful curves, clutter, and prompt-specific relations such as fire visibly beginning at the mouth. Do not reward complexity or the presence of named parts when the result visually reads as another object. Return only JSON."""


def compare(
    *,
    prompt: str,
    items: list[tuple[str, Path]],
    output_dir: Path,
    model: str | None = None,
    vision_model: str | None = None,
) -> dict:
    if output_dir.exists():
        raise FileExistsError(f"output already exists: {output_dir}")
    if len(items) < 2:
        raise ValueError("visual comparison requires at least two items")
    output_dir.mkdir(parents=True)
    blinded = []
    content = [{
        "type": "input_text",
        "text": (
            f"Target: {prompt}\nRank all samples best to worst. Return exactly: "
            "{\"ranking\":[\"A\",\"B\"],\"best\":\"A\",\"samples\":{\"A\":{\"recognizability\":\"...\",\"multiview_consistency\":\"...\",\"fire_correctness\":\"...\",\"strengths\":[\"...\"],\"weaknesses\":[\"...\"],\"absolute_acceptable\":true}},\"reason\":\"...\"}."
        ),
    }]
    for index, (name, path) in enumerate(items):
        label = chr(ord("A") + index)
        copied = output_dir / f"sample_{label}.png"
        shutil.copy2(path, copied)
        blinded.append({"label": label, "source_name": name, "source_path": str(path.resolve()), "copied_path": copied.name})
        content.extend([
            {"type": "input_text", "text": f"Sample {label}"},
            {"type": "input_image", "image_url": image_url(copied)},
        ])
    write_json(output_dir / "mapping.json", blinded)
    role = ResponsesRole(model=model, vision_model=vision_model)
    result, raw = role.call_json(system=SYSTEM_PROMPT, content=content, max_tokens=2600, vision=True)
    valid = {item["label"] for item in blinded}
    ranking = result.get("ranking")
    if not isinstance(ranking, list) or set(ranking) != valid or len(ranking) != len(valid):
        raise ValueError(f"visual judge returned invalid ranking: {ranking!r}")
    (output_dir / "raw_response.txt").write_text(raw, encoding="utf-8")
    write_json(output_dir / "visual_judgment.json", result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Blindly compare rendered Path3D contact sheets")
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--item", action="append", required=True, help="NAME=PATH; repeat at least twice")
    parser.add_argument("--model", default=None)
    parser.add_argument("--vision-model", default=None)
    try:
        args = parser.parse_args(argv)
        items = []
        for raw in args.item:
            name, separator, path = raw.partition("=")
            if not separator or not name.strip() or not path.strip():
                raise ValueError(f"invalid --item {raw!r}; expected NAME=PATH")
            items.append((name.strip(), Path(path)))
        result = compare(
            prompt=args.prompt, items=items, output_dir=args.output,
            model=args.model, vision_model=args.vision_model,
        )
        print(json.dumps({"status": "complete", "best": result["best"], "output": str(args.output.resolve())}, separators=(",", ":")))
        return 0
    except Exception as exc:
        print(json.dumps({
            "status": "error", "error_type": type(exc).__name__, "message": str(exc),
            "traceback": traceback.format_exc(),
        }, ensure_ascii=False, separators=(",", ":")))
        return 2


if __name__ == "__main__":
    sys.exit(main())
