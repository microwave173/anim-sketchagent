from __future__ import annotations

from path3d.parser import parse_path3d
from path3d.schema import Path3DScene, Path3DStroke

from .schema import Point3, StructuredCommand, StructuredScene


def _numbers(point: Point3) -> str:
    return " ".join(f"{value:.6g}" for value in point)


def compile_command(command: StructuredCommand) -> str:
    if command.command in {"M", "L"}:
        assert command.point is not None
        return f"{command.command} {_numbers(command.point)}"
    if command.command == "Q3":
        assert command.control is not None and command.end is not None
        return f"Q3 {_numbers(command.control)} {_numbers(command.end)}"
    if command.command == "C3":
        assert command.control_1 is not None and command.control_2 is not None and command.end is not None
        return f"C3 {_numbers(command.control_1)} {_numbers(command.control_2)} {_numbers(command.end)}"
    return "Z"


def compile_scene(scene: StructuredScene) -> Path3DScene:
    strokes = []
    for item in scene.strokes:
        path = " ".join(compile_command(command) for command in item.commands)
        parse_path3d(path)
        strokes.append(Path3DStroke(
            item.id,
            path,
            item.description,
            item.stroke,
            item.stroke_width,
            item.opacity,
            item.group,
        ))
    metadata = dict(scene.metadata)
    metadata.update({"source_format": "structured_path3d_json_v1"})
    return Path3DScene(scene.prompt, tuple(strokes), metadata)
