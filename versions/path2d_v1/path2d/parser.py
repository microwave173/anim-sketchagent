from __future__ import annotations

import math
import re

from .schema import Path2DCommand

_TOKEN = re.compile(r"[MLQCZmlqcz]|[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?")
_ARITY = {"M": 2, "L": 2, "Q": 4, "C": 6, "Z": 0}


def parse_path2d(path: str) -> tuple[Path2DCommand, ...]:
    tokens = _TOKEN.findall(path.replace(",", " "))
    residue = _TOKEN.sub("", path.replace(",", " "))
    if residue.strip():
        raise ValueError(f"invalid Path2D syntax near {residue.strip()!r}")
    if not tokens:
        raise ValueError("empty Path2D path")

    commands: list[Path2DCommand] = []
    index = 0
    while index < len(tokens):
        raw = tokens[index]
        if raw.upper() not in _ARITY:
            raise ValueError(f"expected Path2D command, found {raw!r}")
        if raw != raw.upper():
            raise ValueError("Path2D v1 supports absolute uppercase commands only")
        command = raw
        index += 1
        arity = _ARITY[command]
        if command == "Z":
            commands.append(Path2DCommand(command))
            continue
        group_index = 0
        while index < len(tokens) and tokens[index].upper() not in _ARITY:
            if index + arity > len(tokens):
                raise ValueError(f"command {command} requires groups of {arity} numeric values")
            raw_values = tokens[index : index + arity]
            values = tuple(float(value) for value in raw_values)
            if not all(math.isfinite(value) for value in values):
                raise ValueError("Path2D coordinates must be finite")
            effective = "L" if command == "M" and group_index else command
            commands.append(Path2DCommand(effective, values))
            index += arity
            group_index += 1
        if group_index == 0:
            raise ValueError(f"command {command} requires {arity} numeric values")

    if commands[0].command != "M":
        raise ValueError("Path2D path must begin with M")
    current_subpath = False
    for command in commands:
        if command.command == "M":
            current_subpath = True
        elif not current_subpath:
            raise ValueError(f"command {command.command} requires an active subpath")
        elif command.command == "Z":
            current_subpath = False
    return tuple(commands)
