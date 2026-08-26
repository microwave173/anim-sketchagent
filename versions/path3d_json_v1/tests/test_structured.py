from __future__ import annotations

import json
import unittest

from path3d.parser import parse_path3d
from path3d_json.compiler import compile_scene
from path3d_json.generator import SYSTEM_PROMPT
from path3d_json.schema import StructuredScene


class StructuredPath3DTest(unittest.TestCase):
    def test_compiles_all_commands_to_valid_path3d(self):
        value = {
            "prompt": "test",
            "strokes": [{
                "id": "curve",
                "commands": [
                    {"command": "M", "point": [0, 0, 0]},
                    {"command": "L", "point": [1, 0, 0]},
                    {"command": "Q3", "control": [1, 1, 0], "end": [0, 1, 0]},
                    {"command": "C3", "control_1": [0, 1, 1], "control_2": [1, 0, 1], "end": [0, 0, 1]},
                    {"command": "Z"},
                ],
                "description": "all commands",
            }],
        }
        structured = StructuredScene.from_dict(value)
        compiled = compile_scene(structured)
        self.assertEqual([item.command for item in parse_path3d(compiled.strokes[0].path)], ["M", "L", "Q", "C", "Z"])

    def test_rejects_wrong_triplet_and_missing_curve_field(self):
        base = {"prompt": "x", "strokes": [{"id": "x", "description": "x", "commands": []}]}
        base["strokes"][0]["commands"] = [{"command": "M", "point": [0, 0]}]
        with self.assertRaisesRegex(ValueError, "triplet"):
            StructuredScene.from_dict(base)
        base["strokes"][0]["commands"] = [
            {"command": "M", "point": [0, 0, 0]},
            {"command": "C3", "control_1": [0, 1, 0], "end": [1, 0, 0]},
        ]
        with self.assertRaisesRegex(ValueError, "control_2"):
            StructuredScene.from_dict(base)

    def test_rejects_flat_path_string_protocol(self):
        value = {"prompt": "x", "strokes": [{"id": "x", "path": "M 0 0 0 L 1 0 0", "description": "x"}]}
        with self.assertRaisesRegex(ValueError, "commands array"):
            StructuredScene.from_dict(value)

    def test_system_prompt_uses_explicit_triplet_objects(self):
        self.assertIn('"control_1":[c1x,c1y,c1z]', SYSTEM_PROMPT)
        self.assertIn("Never flatten several points", SYSTEM_PROMPT)
        self.assertIn("Do not return a path string", SYSTEM_PROMPT)


if __name__ == "__main__":
    unittest.main()
