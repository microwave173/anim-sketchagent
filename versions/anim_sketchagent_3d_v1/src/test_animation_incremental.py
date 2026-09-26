from __future__ import annotations
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import glm_anim_3d  # sets up the frozen dependency paths
from animation_incremental import AnimationDocument, AnimationIncrementalLoop, AnimationRevisionStore
from drawer_v14.three_d.document import Path3DDocument
from drawer_v14.three_d.patch import Path3DPatch, PlannerReview
from drawer_v14.three_d.schema import Path3DStroke
from path3d_json_agents.structured_patch import StructuredPath3DPatch


def stroke(name="arm", path="M 0 0 0 L 0 0 0.5"):
    return Path3DStroke.from_dict({"id":name, "path":path, "description":"test stroke"})


class AnimationReplacementTests(unittest.TestCase):
    def test_atomic_replacement_preserves_identity_and_other_strokes(self):
        doc = AnimationDocument("pose", [stroke(), stroke("hoop")])
        patch = Path3DPatch(("arm",), (stroke(path="M 0 0 0 L 0.5 0 0.5"),))
        self.assertTrue(doc.validate_patch(patch).valid)
        updated = doc.apply_patch(patch)
        self.assertEqual(set(updated.stroke_ids), {"arm", "hoop"})
        self.assertNotIn("arm", updated.retired_ids)
        self.assertEqual(updated.strokes[0], doc.strokes[1])
        self.assertTrue(updated.validate_patch(patch).valid)
        # The original still-sketch document keeps its existing policy.
        self.assertFalse(Path3DDocument("pose", doc.strokes).validate_patch(patch).valid)

    def test_duplicate_and_protected_ids_remain_invalid(self):
        doc = AnimationDocument("pose", [stroke()])
        duplicate = Path3DPatch(("arm",), (stroke(), stroke()))
        self.assertFalse(doc.validate_patch(duplicate).valid)
        replace = Path3DPatch(("arm",), (stroke(),))
        self.assertFalse(doc.validate_patch(replace, protected_ids=("arm",)).valid)
        self.assertFalse(doc.validate_patch(Path3DPatch((), (stroke(),))).valid)

    def test_genuinely_removed_ids_stay_retired_across_reload(self):
        with TemporaryDirectory() as tmp:
            store = AnimationRevisionStore(Path(tmp)/"run", width=32, height=32)
            initial = store.initialize(prompt="pose")
            first = Path3DPatch((), (stroke(), stroke("hoop")))
            r1 = store.commit(AnimationDocument("pose").apply_patch(first),
                              parent=initial.revision_id, round_index=1, patch=first)
            delete = Path3DPatch(("arm",), ())
            r2 = store.commit(store.load_document(r1.revision_id).apply_patch(delete),
                              parent=r1.revision_id, round_index=2, patch=delete)
            loaded = store.load_document(r2.revision_id)
            self.assertIn("arm", loaded.retired_ids)
            self.assertFalse(loaded.validate_patch(Path3DPatch((), (stroke(),))).valid)
            self.assertFalse(loaded.validate_patch(Path3DPatch(("arm",), (stroke(),))).valid)

    def test_existing_geometry_and_budget_checks_are_kept(self):
        from drawer_v14.three_d.document import Path3DPatchPolicy
        doc = AnimationDocument("pose", [stroke()])
        invalid = Path3DPatch(("arm",), (stroke(path="M 0 0 0 L 100 0 0"),))
        self.assertFalse(doc.validate_patch(invalid).valid)
        self.assertFalse(doc.validate_patch(Path3DPatch(("arm",), (stroke(),)),
                                            Path3DPatchPolicy(max_additions=0)).valid)

    def test_incremental_loop_commits_an_identity_preserving_pose_edit(self):
        class Planner:
            def create_plan(self, **kwargs): return {}
            def review(self, **kwargs):
                if kwargs["round_index"] == 3:
                    return PlannerReview("finish", {}, reason="edited pose ready")
                return PlannerReview("continue", {}, {"objective":"draw then change pose"})
            def select_best(self, **kwargs):
                return kwargs["revisions"][-1]["revision_id"], "latest edited pose"
        class Editor:
            def edit(self, **kwargs):
                exists = bool(kwargs["current_scene"]["strokes"])
                value = {"delete_stroke_ids":["arm"] if exists else [], "add_strokes":[{
                    "id":"arm", "description":"arm pose", "commands":[
                        {"command":"M", "point":[0,0,0]},
                        {"command":"L", "point":[.5 if exists else 0,0,.5]}]}]}
                return StructuredPath3DPatch.from_dict(value), json.dumps(value)
        with TemporaryDirectory() as tmp:
            out = Path(tmp)/"run"
            result = AnimationIncrementalLoop(output_dir=out, planner=Planner(), editor=Editor(),
                                              max_rounds=3).run("pose", width=32, height=32)
            self.assertEqual(result.status, "complete")
            self.assertEqual(result.best_revision, "revision_002")
            scene = json.loads((out/"final/scene.json").read_text())
            self.assertEqual(scene["strokes"][0]["id"], "arm")
            self.assertIn("0.5 0 0.5", scene["strokes"][0]["path"])


if __name__ == "__main__":
    unittest.main()
