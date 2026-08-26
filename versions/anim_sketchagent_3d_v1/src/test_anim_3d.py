from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from glm_anim_3d import (
    expand_timeline,
    pin_anchored_scene,
    require_scene_contract,
    scene_contract_report,
    validate_key_plan,
)
from glm_ds_roles import GlmDsPlanner


PLAN = {
    "action": "A player releases one ball while a fixed hoop stays at the right side of the scene.",
    "parts": [
        {"id": "person", "name": "person", "motion": "moving"},
        {"id": "ball", "name": "ball", "motion": "moving"},
        {"id": "hoop", "name": "hoop", "motion": "anchored"},
    ],
    "keys": [{"name": "start"}, {"name": "end"}],
    "gaps": [{"after": "start", "n_inbetween": 2, "ease": "smooth"}],
}


def scene(*, hoop_path: str = "M 0.8 0 0 L 0.8 0 0.8") -> dict:
    return {
        "prompt": "test",
        "strokes": [
            {"id": "person", "path": "M -0.5 0 0 L -0.5 0 0.5", "description": "person"},
            {"id": "person_arm", "path": "M -0.5 0 0.4 L -0.2 0 0.5", "description": "arm"},
            {"id": "ball", "path": "M -0.1 0 0.5 L -0.08 0 0.5", "description": "ball"},
            {"id": "hoop", "path": hoop_path, "description": "hoop"},
        ],
        "metadata": {},
    }


class Anim3DContractTests(unittest.TestCase):
    def test_expand_timeline_uses_planned_gap(self) -> None:
        timeline = expand_timeline(PLAN["keys"], PLAN["gaps"])
        self.assertEqual([item["kind"] for item in timeline], ["key", "inbetween", "inbetween", "key"])
        self.assertAlmostEqual(timeline[1]["t"], 1 / 3)
        self.assertAlmostEqual(timeline[2]["t"], 2 / 3)

    def test_validate_plan_keeps_free_length(self) -> None:
        value = validate_key_plan(
            {**PLAN, "parts": list(PLAN["parts"]), "keys": list(PLAN["keys"]), "gaps": [dict(PLAN["gaps"][0])]},
            None,
            {"part_range": (3, 5)},
        )
        self.assertEqual(value["n_frames"], 4)

    def test_scene_contract_accepts_prefixed_helpers(self) -> None:
        report = require_scene_contract(scene(), PLAN, label="test")
        self.assertTrue(report["ok"])
        self.assertEqual(report["unknown_ids"], [])

    def test_scene_contract_rejects_missing_canonical_id(self) -> None:
        value = scene()
        value["strokes"] = [item for item in value["strokes"] if item["id"] != "person_arm"]
        report = scene_contract_report(value, PLAN, canonical_ids={"person", "person_arm", "ball", "hoop"})
        self.assertFalse(report["ok"])
        self.assertEqual(report["canonical_missing"], ["person_arm"])

    def test_pin_anchored_scene_uses_first_key_geometry(self) -> None:
        first = scene()
        changed = scene(hoop_path="M 0 0 0 L 0 0 0.2")
        pinned = pin_anchored_scene(changed, first, PLAN)
        hoop = next(item for item in pinned["strokes"] if item["id"] == "hoop")
        self.assertEqual(hoop["path"], "M 0.8 0 0 L 0.8 0 0.8")
        self.assertEqual(pinned["metadata"]["animation_anchors_pinned_from"], "first_key")

    def test_visual_review_falls_back_after_two_invalid_directives(self) -> None:
        with TemporaryDirectory() as tmp:
            sheet = Path(tmp) / "sheet.png"
            sheet.write_bytes(b"not decoded by the role")
            with patch("glm_ds_roles._call_json", return_value=({}, "")) as call:
                review = GlmDsPlanner().review(
                    prompt="draw the planned pose",
                    plan={"steps": []},
                    current_contact_sheet=sheet,
                    round_index=1,
                    max_rounds=4,
                    current_revision="revision_000",
                    trajectory=[],
                    history=[],
                )
        self.assertEqual(call.call_count, 2)
        self.assertEqual(review.decision, "continue")
        self.assertIsNotNone(review.instruction)


if __name__ == "__main__":
    unittest.main()
