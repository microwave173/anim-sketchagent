from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from drawer_v14.three_d.document import Path3DDocument, Path3DPatchPolicy
from drawer_v14.three_d.loop import IncrementalPath3DLoop
from drawer_v14.three_d.patch import Path3DPatch, PlannerReview
from drawer_v14.three_d.roles import (
    PATH3D_EDITOR_SYSTEM_PROMPT,
    PATH3D_PLANNER_SYSTEM_PROMPT,
    SPATIAL_CIRCLE_Q3_EXAMPLE_PATH,
    SPATIAL_S_CURVE_C3_EXAMPLE_PATH,
)
from drawer_v14.three_d.parser import parse_path3d
from drawer_v14.three_d.roles import ModelPath3DPlanner
from drawer_v14.three_d.schema import Path3DStroke
from drawer_v14.two_d.roles import ModelPlanner
from drawer_v14.two_d.roles import EDITOR_SYSTEM_PROMPT, PLANNER_SYSTEM_PROMPT


def stroke(stroke_id: str, path: str = "M 0 0 0 L 1 0 0") -> Path3DStroke:
    return Path3DStroke(stroke_id, path, f"description for {stroke_id}")


class Path3DDocumentTest(unittest.TestCase):
    def test_atomic_batch_replace_and_retired_id(self):
        original = Path3DDocument("object", [stroke("old")])
        patch = Path3DPatch(("old",), (stroke("new", "M 0 0 0 C3 0 1 0 1 1 1 1 0 1"),))
        updated = original.apply_patch(patch)
        self.assertEqual(original.stroke_ids, ("old",))
        self.assertEqual(updated.stroke_ids, ("new",))
        self.assertIn("old", updated.retired_ids)
        reused = updated.validate_patch(Path3DPatch(add_strokes=(stroke("old"),)))
        self.assertFalse(reused.valid)

    def test_rejects_2d_curve_commands_and_protected_deletion(self):
        document = Path3DDocument("object", [stroke("keep")])
        invalid_curve = Path3DPatch(add_strokes=(
            stroke("bad", "M 0 0 0 C 0 1 1 1 0 1"),
        ))
        validation = document.validate_patch(invalid_curve)
        self.assertFalse(validation.valid)
        self.assertTrue(any("Q3/C3" in error for error in validation.errors))
        protected = document.validate_patch(
            Path3DPatch(("keep",), (stroke("replacement"),)),
            protected_ids=("keep",),
        )
        self.assertFalse(protected.valid)

    def test_batch_limit_and_coordinate_limit(self):
        document = Path3DDocument("object", [stroke("base")])
        additions = tuple(stroke(f"s{index}") for index in range(7))
        self.assertFalse(document.validate_patch(
            Path3DPatch(add_strokes=additions), Path3DPatchPolicy(max_additions=6)
        ).valid)
        outside = Path3DPatch(add_strokes=(stroke("outside", "M 0 0 0 L 20 0 0"),))
        self.assertFalse(document.validate_patch(outside).valid)


class FakePlanner:
    def create_plan(self, *, prompt: str):
        return {"stages": [{"goal": "frame"}], "final_criteria": ["recognizable"]}

    def review(self, **kwargs):
        round_index = kwargs["round_index"]
        if round_index == 1:
            return PlannerReview("continue", {}, {"goal": "frame", "preserve_stroke_ids": []})
        if round_index == 2:
            return PlannerReview("continue", {}, {
                "goal": "curve", "preserve_stroke_ids": ["frame"],
            })
        return PlannerReview("finish", {}, reason="done")

    def select_best(self, **kwargs):
        return "revision_001", "earlier frame is cleaner"


class FakeEditor:
    def __init__(self):
        self.curve_attempts = 0

    def edit(self, **kwargs):
        if kwargs["instruction"]["goal"] == "frame":
            return Path3DPatch(add_strokes=(stroke("frame", "M -1 0 0 L 1 0 0 L 1 1 1"),))
        self.curve_attempts += 1
        if self.curve_attempts == 1:
            return Path3DPatch(add_strokes=(stroke("bad_curve", "M 0 0 0 C 0 1 1 1 0 1"),))
        return Path3DPatch(add_strokes=(
            stroke("curve", "M 0 0 0 C3 0 1 0 1 1 1 1 0 1"),
        ))


class Path3DLoopTest(unittest.TestCase):
    def test_repair_loop_and_historical_best(self):
        with tempfile.TemporaryDirectory() as temp:
            result = IncrementalPath3DLoop(
                output_dir=Path(temp) / "run",
                planner=FakePlanner(),
                editor=FakeEditor(),
                max_rounds=3,
            ).run("3D object", width=128, height=128)
            self.assertEqual(result.status, "complete")
            self.assertEqual(result.best_revision, "revision_001")
            self.assertTrue(result.best_preview.is_file())
            self.assertTrue((Path(temp) / "run" / "final" / "scene.json").is_file())
            self.assertTrue((Path(temp) / "run" / "final" / "views" / "view_perspective.png").is_file())


class PromptIsolationTest(unittest.TestCase):
    def test_2d_and_3d_use_separate_system_prompts(self):
        self.assertIn("incremental 2D SVG", PLANNER_SYSTEM_PROMPT)
        self.assertIn("short vertical-line eyes", EDITOR_SYSTEM_PROMPT)
        self.assertNotIn("Path3D", PLANNER_SYSTEM_PROMPT + EDITOR_SYSTEM_PROMPT)
        self.assertIn("incremental 3D spatial", PATH3D_PLANNER_SYSTEM_PROMPT)
        self.assertIn("C3", PATH3D_EDITOR_SYSTEM_PROMPT)
        self.assertIn("+y away/deeper", PATH3D_EDITOR_SYSTEM_PROMPT)
        self.assertNotIn("vertical-line eyes", PATH3D_PLANNER_SYSTEM_PROMPT + PATH3D_EDITOR_SYSTEM_PROMPT)
        commands = parse_path3d(SPATIAL_CIRCLE_Q3_EXAMPLE_PATH)
        self.assertEqual(sum(item.command == "Q" for item in commands), 8)
        self.assertIn(SPATIAL_CIRCLE_Q3_EXAMPLE_PATH, PATH3D_EDITOR_SYSTEM_PROMPT)
        c3_commands = parse_path3d(SPATIAL_S_CURVE_C3_EXAMPLE_PATH)
        self.assertEqual([item.command for item in c3_commands], ["M", "C"])
        self.assertIn(SPATIAL_S_CURVE_C3_EXAMPLE_PATH, PATH3D_EDITOR_SYSTEM_PROMPT)
        self.assertIn("unnecessary polygonal/faceted", PATH3D_PLANNER_SYSTEM_PROMPT)
        self.assertIn("[control 1], [control 2], [endpoint]", PATH3D_EDITOR_SYSTEM_PROMPT)

    def test_both_model_branches_retry_malformed_json_independently(self):
        class Response:
            def __init__(self, text):
                self.output_text = text

        class Client:
            def __init__(self):
                self.calls = []
                self.responses = self

            def create(self, **kwargs):
                self.calls.append(kwargs)
                return Response("{bad" if len(self.calls) == 1 else '{"ok":true}')

        for role_class, system in (
            (ModelPlanner, PLANNER_SYSTEM_PROMPT),
            (ModelPath3DPlanner, PATH3D_PLANNER_SYSTEM_PROMPT),
        ):
            client = Client()
            role = role_class(client=client)
            self.assertEqual(role._json(system, "request", max_tokens=100), {"ok": True})
            self.assertEqual(len(client.calls), 2)
            self.assertEqual(client.calls[0]["input"][0]["content"], system)
            self.assertEqual(client.calls[1]["input"][0]["content"], system)

    def test_transport_json_decode_error_is_retried(self):
        class Response:
            output_text = '{"ok":true}'

        class Client:
            def __init__(self):
                self.calls = 0
                self.responses = self

            def create(self, **kwargs):
                self.calls += 1
                if self.calls == 1:
                    raise __import__("json").JSONDecodeError("extra data", "{}{}", 2)
                return Response()

        client = Client()
        role = ModelPath3DPlanner(client=client)
        self.assertEqual(role._json(PATH3D_PLANNER_SYSTEM_PROMPT, "request", max_tokens=100), {"ok": True})
        self.assertEqual(client.calls, 2)


if __name__ == "__main__":
    unittest.main()
