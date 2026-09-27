from __future__ import annotations

import json
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.error
from unittest.mock import patch

from pipeline import run
from scene import validate_batch, static_anchor, pin_static
from storyboard import parse_storyboard, gaps
from provider import Provider, OutputLimitError

STORY = """## Action
The alarm triggers water that extinguishes fire.
## Notes
Fixed floor and camera.
## Beats
| frames | event | exit |
|---|---|---|
| 1-3 | Pull alarm | Alarm down, fire burning |
| 4-6 | Water reaches fire | Fire gone |
"""


def frame(i, fire=True, floor_y=-0.8):
    strokes = [{"id": "floor", "path": f"M -0.8 {floor_y} L 0.8 {floor_y}", "description": "floor"},
               {"id": "actor", "path": "M 0 0 L 0 -0.6", "description": "actor"}]
    if fire:
        strokes.append({"id": "fire", "path": "M 0.6 -0.8 Q 0.4 -0.4 0.6 -0.3", "description": "flame"})
    return {"i": i, "strokes": strokes}


class LightTests(unittest.TestCase):
    def test_storyboard_compiles_sparse_keys_and_exact_gaps(self):
        story = parse_storyboard(STORY, 6)
        self.assertEqual(story["key_indices"], [1, 3, 6])
        self.assertEqual([g["indices"] for g in gaps(story)], [[2], [4, 5]])

    def test_storyboard_rejects_missing_and_overlapping_time(self):
        for bad in [STORY.replace("4-6", "5-6"), STORY.replace("4-6", "3-6"), STORY.replace("4-6", "4-5")]:
            with self.assertRaises(ValueError):
                parse_storyboard(bad, 6)

    def test_validation_rejects_duplicate_ids_out_of_bounds_and_wrong_indices(self):
        duplicate = frame(1)
        duplicate["strokes"].append(duplicate["strokes"][0])
        outside = frame(1)
        outside["strokes"][0]["path"] = "M -2 0 L 0 0"
        for raw in [duplicate, outside, frame(2)]:
            with self.assertRaises(ValueError):
                validate_batch({"frames": [raw]}, [1], 2, "test")

    def test_pin_only_fixed_scenery_does_not_resurrect_fire(self):
        keys = validate_batch({"frames": [frame(1), frame(6, False)]}, [1, 6], 2, "test")
        anchor = static_anchor(keys, ["floor"])
        end = pin_static(frame(6, False, -0.7), anchor)
        self.assertNotIn("fire", {s["id"] for s in end["strokes"]})
        self.assertEqual(next(s for s in end["strokes"] if s["id"] == "floor")["path"],
                         anchor["floor"]["path"])

    def test_3d_uses_same_envelope_and_validates_real_3d_syntax(self):
        raw = {"frames": [{"i": 1, "strokes": [{"id": "curve", "description": "curve", "path": "M 0 0 0 Q3 0.1 0.2 0.3 0.4 0.5 0.6"}]}]}
        self.assertEqual(list(validate_batch(raw, [1], 3, "test")), [1])

    def test_provider_does_not_retry_output_truncation(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self):
                return json.dumps({"choices": [{"finish_reason": "length", "message": {"content": "partial"}}]}).encode()
        with patch("provider.load_env", return_value={"DEEPSEEK_API_KEY": "test", "DEEPSEEK_MODEL": "fake"}), patch(
            "provider.urllib.request.urlopen", return_value=Response()) as call:
            provider = Provider("env")
            with self.assertRaisesRegex(ValueError, "Incomplete model output"):
                provider.call("test", "system", "user")
            self.assertEqual(call.call_count, 1)
            self.assertFalse(provider.calls[0]["ok"])
            self.assertEqual(provider.calls[0]["finish_reason"], "length")

    def test_provider_records_both_attempts_when_rate_limited(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self):
                return json.dumps({"choices": [{"finish_reason": "stop", "message": {"content": "{}"}}]}).encode()
        limited = urllib.error.HTTPError("https://test", 429, "rate limit", {}, None)
        with patch("provider.load_env", return_value={"DEEPSEEK_API_KEY": "test", "DEEPSEEK_MODEL": "fake"}), patch(
            "provider.urllib.request.urlopen", side_effect=[limited, Response()]), patch("provider.time.sleep"):
            provider = Provider("env")
            self.assertEqual(provider.call("test", "system", "user"), "{}")
            self.assertEqual([row["ok"] for row in provider.calls], [False, True])

    def test_omitted_budget_is_absent_from_http_payload(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self):
                return json.dumps({"choices": [{"finish_reason":"stop","message":{"content":"{}"}}]}).encode()
        with patch("provider.load_env", return_value={"DEEPSEEK_API_KEY":"test","DEEPSEEK_MODEL":"fake"}), patch(
            "provider.urllib.request.urlopen", return_value=Response()) as call:
            provider=Provider("env")
            provider.call("test","system","user",max_tokens=None)
            payload=json.loads(call.call_args.args[0].data)
            self.assertNotIn("max_tokens",payload)
            self.assertEqual(provider.calls[0]["output_budget_policy"],"omitted")
            provider.call("test","system","user")
            payload=json.loads(call.call_args.args[0].data)
            self.assertEqual(payload["max_tokens"],393216)
            self.assertEqual(provider.calls[-1]["output_budget_policy"],"explicit")

    def test_truncated_gap_splits_and_resumes_complete_timeline(self):
        class FakeProvider:
            model,base,effort,max_tokens="fake","test://fake","high",None
            def __init__(self): self.calls=[]
            def call(self,stage,system,user,max_tokens):
                self.calls.append({"stage":stage,"finish_reason":"length" if stage=="gap_02" else "stop"})
                if stage=="plan":return STORY
                if stage=="keys":return json.dumps({"static_ids":["floor"],"frames":[frame(1),frame(3),frame(6,False)]})
                if stage=="gap_02":raise OutputLimitError("truncated","partial")
                indices={"gap_01":[2],"gap_02_a":[4],"gap_02_b":[5]}[stage]
                return json.dumps({"frames":[frame(i,i<5) for i in indices]})
        with tempfile.TemporaryDirectory() as tmp,patch("pipeline.export"):
            provider=FakeProvider();out=Path(tmp)
            run("alarm",2,6,120,out,provider)
            self.assertEqual([c["stage"] for c in provider.calls][:2],["plan","keys"])
            self.assertCountEqual([c["stage"] for c in provider.calls][2:],["gap_01","gap_02","gap_02_a","gap_02_b"])
            self.assertTrue((out/"checkpoints/gap_02.json").exists())
            resumed=FakeProvider();run("alarm",2,6,120,out,resumed)
            self.assertEqual(resumed.calls,[])
            value=json.loads((out/"animation.json").read_text())
            self.assertEqual([f["i"] for f in value["frames"]],list(range(1,7)))

    def test_3d_spatial_guide_reaches_plan_keys_and_gaps(self):
        def spatial_frame(i):
            return {"i": i, "strokes": [{"id": "solid", "description": "spatial outline",
                     "path": "M -0.2 -0.1 0 L 0.2 -0.1 0 L 0.2 0.1 0 L -0.2 0.1 0 Z"}]}
        class FakeProvider:
            model, base, effort, max_tokens = "fake", "test://fake", "high", 393216
            def __init__(self): self.calls = []; self.systems = {}
            def call(self, stage, system, user, max_tokens):
                self.calls.append({"stage": stage}); self.systems[stage] = system
                if stage == "plan": return STORY
                indices = {"keys": [1, 3, 6], "gap_01": [2], "gap_02": [4, 5]}[stage]
                return json.dumps({"static_ids": [], "frames": [spatial_frame(i) for i in indices]})
        with tempfile.TemporaryDirectory() as tmp, patch("pipeline.export"):
            provider = FakeProvider()
            run("spatial", 3, 6, 120, Path(tmp), provider, gap_workers=2)
            for stage in ("plan", "keys", "gap_01", "gap_02"):
                self.assertIn("Genuine spatial sketch construction", provider.systems[stage])
                self.assertIn("planar billboards", provider.systems[stage])

    def test_parallel_gaps_overlap_and_reuse_context_when_resumed_serially(self):
        class FakeProvider:
            model, base, effort, max_tokens = "fake", "test://fake", "high", 393216
            def __init__(self):
                self.calls = []
                self.barrier = threading.Barrier(2)
                self.contexts = {}
            def call(self, stage, system, user, max_tokens):
                self.calls.append({"stage": stage})
                if stage == "plan": return STORY
                if stage == "keys":
                    return json.dumps({"static_ids": ["floor"], "frames": [frame(1), frame(3), frame(6, False)]})
                self.contexts[stage] = json.loads(user.split("\nContext:\n", 1)[1])
                self.barrier.wait(timeout=3)
                return json.dumps({"frames": [frame(2)] if stage == "gap_01" else [frame(4), frame(5, False)]})
        with tempfile.TemporaryDirectory() as tmp, patch("pipeline.export"):
            provider = FakeProvider()
            out = Path(tmp)
            run("alarm", 2, 6, 120, out, provider, gap_workers=2)
            context = provider.contexts["gap_02"]
            self.assertEqual(context["previous_key"]["i"], 1)
            self.assertEqual((context["from"]["i"], context["to"]["i"]), (3, 6))
            self.assertNotIn("previous_frame", context)
            value = json.loads((out / "animation.json").read_text())
            self.assertEqual([f["i"] for f in value["frames"]], list(range(1, 7)))
            resumed = FakeProvider()
            run("alarm", 2, 6, 120, out, resumed, gap_workers=1)
            self.assertEqual(resumed.calls, [])

    def test_pipeline_batches_keys_preserves_missing_objects_and_resumes(self):
        class FakeProvider:
            model, base, effort = "fake", "test://fake", "high"
            def __init__(self):
                self.calls = []
                self.systems = {}
            def call(self, stage, system, user, max_tokens):
                self.calls.append({"stage": stage})
                self.systems[stage] = system
                if stage == "plan":
                    return STORY
                if stage == "keys":
                    self.key_prompt = user
                    return json.dumps({"static_ids": ["floor"], "frames": [frame(1), frame(3), frame(6, False)]})
                return json.dumps({"frames": [frame(2)] if stage == "gap_01" else [frame(4), frame(5, False)]})
        with tempfile.TemporaryDirectory() as tmp, patch("pipeline.export"):
            out = Path(tmp)
            provider = FakeProvider()
            run("alarm", 2, 6, 120, out, provider)
            self.assertEqual([c["stage"] for c in provider.calls][:2], ["plan", "keys"])
            self.assertCountEqual([c["stage"] for c in provider.calls][2:], ["gap_01", "gap_02"])
            animation = json.loads((out / "animation.json").read_text())
            self.assertEqual([f["i"] for f in animation["frames"]], list(range(1,7)))
            self.assertNotIn("fire", {s["id"] for s in animation["frames"][-1]["strokes"]})
            self.assertIn("no predefined parts inventory", provider.key_prompt)
            self.assertIn("single-line stick figures", provider.systems["plan"])
            self.assertIn("Actual drawing target: 320x320 pixels", provider.systems["plan"])
            for stage in ("keys", "gap_01", "gap_02"):
                self.assertIn("2D style: expressive single-line stick figures", provider.systems[stage])
                self.assertIn("People MUST remain open single-line", provider.systems[stage])
                self.assertIn("Actual drawing target: 320x320 pixels", provider.systems[stage])
                self.assertIn("Human stick-figure rules never apply to robots", provider.systems[stage])
                self.assertNotIn("People stay stick figures:", provider.systems[stage])
            resumed = FakeProvider()
            run("alarm", 2, 6, 120, out, resumed)
            self.assertEqual(resumed.calls, [])


if __name__ == "__main__":
    unittest.main()
