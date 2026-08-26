from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from drawer_v14.three_d.patch import PlannerReview
from path3d_json_agents.incremental import (
    STRUCTURED_EDITOR_SYSTEM_PROMPT,
    STRUCTURED_PLANNER_SYSTEM_PROMPT,
    ModelStructuredPlanner,
    StructuredIncrementalPath3DLoop,
    StructuredPatchEditor,
    StructuredPatchParseError,
)
from path3d_json_agents.reflection import (
    CRITIC_SYSTEM_PROMPT,
    GENERATOR_SYSTEM_PROMPT,
    PROGRESS_SYSTEM_PROMPT,
    SELECTOR_SYSTEM_PROMPT,
    StructuredReflectionPath3DLoop,
    validate_experience,
)
from path3d_json_agents.structured_patch import StructuredPath3DPatch


def structured_stroke(stroke_id: str) -> dict:
    return {
        "id": stroke_id,
        "commands": [
            {"command": "M", "point": [0, 0, 0]},
            {"command": "C3", "control_1": [0, 0.5, 0.2], "control_2": [0.5, 0.5, 0.5], "end": [1, 0, 0]},
        ],
        "description": stroke_id,
        "stroke": "#111111",
        "stroke_width": 3,
        "opacity": 1,
        "group": "test",
    }


class StructuredPatchTest(unittest.TestCase):
    def test_compile_patch_and_reject_missing_control(self):
        patch = StructuredPath3DPatch.from_dict({"delete_stroke_ids": [], "add_strokes": [structured_stroke("curve")]})
        compiled = patch.compile(prompt="x")
        self.assertIn("C3", compiled.add_strokes[0].path)
        invalid = structured_stroke("bad")
        del invalid["commands"][1]["control_2"]
        with self.assertRaisesRegex(ValueError, "control_2"):
            StructuredPath3DPatch.from_dict({"add_strokes": [invalid]})


class FakePlanner:
    def create_plan(self, *, prompt):
        return {"stages": [{"goal": "body"}], "final_criteria": ["recognizable"]}

    def review(self, **kwargs):
        if kwargs["round_index"] <= 2:
            return PlannerReview("continue", {}, {"goal": "body", "preserve_stroke_ids": []})
        return PlannerReview("finish", {}, reason="done")

    def select_best(self, **kwargs):
        return "revision_001", "first valid revision"


class FakeStructuredEditor:
    def __init__(self):
        self.calls = 0

    def edit(self, **kwargs):
        self.calls += 1
        if self.calls == 1:
            invalid = structured_stroke("bad")
            invalid["commands"][0]["point"] = [0, 0]
            return StructuredPath3DPatch.from_dict({"add_strokes": [invalid]}), "invalid"
        return StructuredPath3DPatch.from_dict({"add_strokes": [structured_stroke(f"curve_{self.calls}")]}), "valid"


class IncrementalLoopTest(unittest.TestCase):
    def test_structured_repair_and_auditable_patch(self):
        class RepairingEditor(FakeStructuredEditor):
            def edit(self, **kwargs):
                self.calls += 1
                if self.calls == 1:
                    raise ValueError("M.point must be one [x,y,z] triplet")
                return StructuredPath3DPatch.from_dict({"add_strokes": [structured_stroke(f"curve_{self.calls}")]}), "valid"

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "run"
            result = StructuredIncrementalPath3DLoop(
                output_dir=root, planner=FakePlanner(), editor=RepairingEditor(), max_rounds=3,
            ).run("dragon", width=128, height=128)
            self.assertEqual(result.best_revision, "revision_001")
            self.assertTrue((root / "revisions" / "revision_001" / "structured_patch.json").exists())
            attempt = json.loads((root / "rounds" / "round_01" / "editor_attempt_01.json").read_text())
            self.assertFalse(attempt["validation"]["valid"])

    def test_editor_schema_error_preserves_raw_response(self):
        class Responses:
            def create(self, **kwargs):
                value = {"delete_stroke_ids": [], "add_strokes": [structured_stroke("bad")]}
                del value["add_strokes"][0]["commands"][1]["control_2"]
                return SimpleNamespace(output_text=json.dumps(value))

        editor = StructuredPatchEditor(model="fake", client=SimpleNamespace(responses=Responses()))
        with tempfile.TemporaryDirectory() as temp:
            image_path = Path(temp) / "view.png"
            from PIL import Image
            Image.new("RGB", (8, 8), "white").save(image_path)
            with self.assertRaises(StructuredPatchParseError) as caught:
                editor.edit(
                    prompt="x", plan={}, instruction={}, current_scene={},
                    current_contact_sheet=image_path, previous_error=None, previous_patch=None,
                )
        self.assertIn('"add_strokes"', caught.exception.raw)
        self.assertEqual(caught.exception.value["add_strokes"][0]["id"], "bad")

    def test_planner_cannot_prescribe_drawing_operations(self):
        valid = {
            "decision": "continue",
            "assessment": {"strengths": [], "problems": ["weak silhouette"]},
            "instruction": {
                "objective": "Make the target recognizable.",
                "priority": "main silhouette",
                "success_criteria": ["Readable in every view"],
                "scope": "rebuild",
            },
            "rollback_revision": None,
            "reason": "identity is weak",
        }
        ModelStructuredPlanner._validate_directive(valid)
        valid["instruction"]["scope"] = "build"
        ModelStructuredPlanner._validate_directive(valid)
        valid["instruction"]["scope"] = "initial full composition"
        ModelStructuredPlanner._validate_directive(valid)
        del valid["instruction"]["scope"]
        ModelStructuredPlanner._validate_directive(valid)
        valid["instruction"]["add_strokes"] = ["body"]
        with self.assertRaisesRegex(ValueError, "drawing boundary"):
            ModelStructuredPlanner._validate_directive(valid)

    def test_default_patch_budget_allows_structural_rebuild(self):
        loop = StructuredIncrementalPath3DLoop(
            output_dir="unused", planner=FakePlanner(), editor=FakeStructuredEditor(),
        )
        self.assertEqual(loop.policy.max_additions, 48)
        self.assertEqual(loop.policy.max_deletions, 48)


class FakeResponses:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        system = kwargs["input"][0]["content"]
        user = kwargs["input"][1]["content"]
        if system == GENERATOR_SYSTEM_PROMPT:
            return SimpleNamespace(output_text=json.dumps({"prompt": "x", "strokes": [structured_stroke("body")]}))
        if system == CRITIC_SYSTEM_PROMPT:
            return SimpleNamespace(output_text=json.dumps({"candidates": [], "cross_candidate_lessons": ["smooth body"]}))
        if system == SELECTOR_SYSTEM_PROMPT:
            ids = [block["text"].split(": ", 1)[1] for block in user if block.get("text", "").startswith("Candidate ID: ")]
            return SimpleNamespace(output_text=json.dumps({"selected_candidate_id": ids[0], "absolute_acceptable": True, "reason": "ok"}))
        if system == PROGRESS_SYSTEM_PROMPT:
            ids = [block["text"].split(": ", 1)[1] for block in user if block.get("text", "").startswith("Candidate ID: ")]
            return SimpleNamespace(output_text=json.dumps({"best_candidate_id": ids[-1], "meaningful_improvement": True, "reason": "better"}))
        if "consolidate compact drawing experience" in system:
            return SimpleNamespace(output_text=json.dumps({
                "preserve": ["Keep the readable curved body."],
                "avoid": ["Avoid disconnected joints."],
                "general": ["Establish the main spatial silhouette before internal detail."],
                "task_strategy": [],
            }))
        raise AssertionError(system)


class FakeClient:
    def __init__(self):
        self.responses = FakeResponses()


class JsonRepairTest(unittest.TestCase):
    def test_repair_receives_invalid_response_and_parser_error(self):
        class Responses:
            def __init__(self):
                self.calls = []

            def create(self, **kwargs):
                self.calls.append(kwargs)
                if len(self.calls) == 1:
                    return SimpleNamespace(output_text='{"ok":"missing quote}')
                return SimpleNamespace(output_text='{"ok":"fixed"}')

        from path3d_json_agents.common import ResponsesRole
        responses = Responses()
        role = ResponsesRole(model="fake", client=SimpleNamespace(responses=responses))
        value, _ = role.call_json(system="system", content="request", max_tokens=100)
        self.assertEqual(value, {"ok": "fixed"})
        repair = responses.calls[1]["input"][1]["content"]
        self.assertIn("missing quote", repair)
        self.assertIn("Parser error", repair)


class ReflectionLoopTest(unittest.TestCase):
    def test_visual_roles_receive_contact_sheets_and_full_regeneration_uses_experience(self):
        with tempfile.TemporaryDirectory() as temp:
            client = FakeClient()
            root = Path(temp) / "run"
            result = StructuredReflectionPath3DLoop(
                output_dir=root, model="fake", vision_model="fake-vision", client=client,
                samples=1, max_loops=2,
            ).run("dragon breathing fire", width=128, height=128)
            self.assertEqual(result.loops_completed, 2)
            vision_calls = [call for call in client.responses.calls if call["input"][0]["content"] in {CRITIC_SYSTEM_PROMPT, SELECTOR_SYSTEM_PROMPT, PROGRESS_SYSTEM_PROMPT}]
            self.assertTrue(vision_calls)
            self.assertTrue(all(any(block.get("type") == "input_image" for block in call["input"][1]["content"]) for call in vision_calls))
            generator_calls = [call for call in client.responses.calls if call["input"][0]["content"] == GENERATOR_SYSTEM_PROMPT]
            self.assertIn("Keep the readable curved body", generator_calls[1]["input"][1]["content"])
            self.assertTrue((root / "final" / "views" / "contact_sheet.png").exists())
            experience = json.loads((root / "loops" / "loop_01" / "experience.json").read_text())
            self.assertLessEqual(sum(len(items) for items in experience.values()), 6)

    def test_prompts_require_structured_curves_and_visual_absolute_judgment(self):
        self.assertIn('"control_1"', STRUCTURED_EDITOR_SYSTEM_PROMPT)
        self.assertIn("decide the geometry", STRUCTURED_EDITOR_SYSTEM_PROMPT)
        self.assertIn("Do not design curves", STRUCTURED_PLANNER_SYSTEM_PROMPT)
        self.assertNotIn("preserve_stroke_ids", STRUCTURED_PLANNER_SYSTEM_PROMPT)
        self.assertIn("absolute assessment", CRITIC_SYSTEM_PROMPT)
        self.assertIn("actual four-view contact sheets", PROGRESS_SYSTEM_PROMPT)

    def test_compact_experience_schema_enforces_item_and_length_limits(self):
        valid = validate_experience({
            "preserve": ["Keep the clear silhouette."],
            "avoid": ["Avoid planar collapse."],
            "general": ["Use shared joints."],
            "task_strategy": ["Keep the target-defining relation visible."],
        })
        self.assertEqual(len(valid), 4)
        with self.assertRaisesRegex(ValueError, "maximum is 2"):
            validate_experience({
                "preserve": ["a", "b", "c"], "avoid": [], "general": [], "task_strategy": [],
            })
        with self.assertRaisesRegex(ValueError, "maximum is 220"):
            validate_experience({
                "preserve": ["x" * 221], "avoid": [], "general": [], "task_strategy": [],
            })


if __name__ == "__main__":
    unittest.main()
