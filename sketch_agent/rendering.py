from __future__ import annotations

import ctypes.util
from pathlib import Path


def render_svg_png(svg: str, output_path: str | Path, *, width: int = 612, height: int = 612) -> Path:
    """Render SVG on macOS/Linux while handling Homebrew's cairo location."""
    cairo_lib = Path("/opt/homebrew/opt/cairo/lib/libcairo.2.dylib")
    if cairo_lib.exists():
        original = ctypes.util.find_library
        ctypes.util.find_library = (
            lambda name: str(cairo_lib)
            if name in ("cairo-2", "cairo", "libcairo-2")
            else original(name)
        )
    import cairosvg

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    cairosvg.svg2png(
        bytestring=svg.encode("utf-8"),
        write_to=str(output),
        output_width=width,
        output_height=height,
        background_color="white",
    )
    return output

