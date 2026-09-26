from __future__ import annotations

import gzip
import json
import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]


def load_tasks(path: Path | None = None) -> dict:
    return json.loads((path or Path(__file__).with_name("tasks.json")).read_text())


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def gzip_file(path: Path) -> None:
    if not path.exists() or path.suffix == ".gz":
        return
    target = path.with_suffix(path.suffix + ".gz")
    with path.open("rb") as source, gzip.open(target, "wb", compresslevel=6) as dest:
        shutil.copyfileobj(source, dest)
    path.unlink()


def label(image: Image.Image, text: str) -> Image.Image:
    image = image.convert("RGB")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    draw.rectangle((0, 0, max(50, len(text) * 7 + 8), 20), fill="white")
    draw.text((4, 4), text, fill="black", font=font)
    return image


def write_gif(paths: list[Path], destination: Path, duration_ms: int) -> None:
    images = [label(Image.open(path), f"f{i + 1}") for i, path in enumerate(paths)]
    destination.parent.mkdir(parents=True, exist_ok=True)
    images[0].save(
        destination,
        save_all=True,
        append_images=images[1:],
        duration=duration_ms,
        loop=0,
        optimize=True,
    )


def write_sheet(paths: list[Path], destination: Path, thumb: int = 160) -> None:
    images = [label(Image.open(path).convert("RGB").resize((thumb, thumb)), f"f{i + 1}") for i, path in enumerate(paths)]
    cols = 6
    rows = (len(images) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * thumb, rows * thumb), "white")
    for i, image in enumerate(images):
        sheet.paste(image, ((i % cols) * thumb, (i // cols) * thumb))
    sheet.save(destination, quality=82, optimize=True)
