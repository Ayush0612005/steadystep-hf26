import argparse
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import steadystep


class SteadyStepTests(unittest.TestCase):
    def test_new_goal_does_not_relabel_pending_work(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "state.json"
            args = argparse.Namespace(goal="original goal", minutes=10,
                model="gemma3:1b", sample=True, replace=False)
            with contextlib.redirect_stdout(io.StringIO()):
                steadystep.command_plan(args, path)
            args.goal = "different goal"
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                steadystep.command_plan(args, path)
            self.assertIn("Goal: original goal", output.getvalue())
            self.assertNotIn("Goal: different goal", output.getvalue())
            args.replace = True
            with self.assertRaises(steadystep.SteadyStepError):
                steadystep.command_plan(args, path)
            self.assertEqual(steadystep.load_state(path)["goal"], "original goal")

    def test_non_object_ollama_response_has_clear_error(self):
        response = MagicMock()
        response.read.return_value = b"[]"
        response.__enter__.return_value = response
        with patch("urllib.request.urlopen", return_value=response):
            with self.assertRaises(steadystep.SteadyStepError):
                steadystep.call_ollama("gemma3:1b", "prompt")

    def test_prompt_requires_one_small_step(self):
        prompt = steadystep.build_prompt("learn binary trees", 15, [])
        self.assertIn("exactly ONE", prompt)
        self.assertIn("15 minutes", prompt)
        self.assertIn("learn binary trees", prompt)

    def test_plan_schema_rejects_extra_fields(self):
        with self.assertRaises(steadystep.SteadyStepError):
            steadystep.Plan.from_dict({
                "title": "x", "action": "x", "done_when": "x",
                "why_now": "x", "encouragement": "x", "extra": "x"
            })

    def test_sample_plan_then_done_persists_history(self):
        with tempfile.TemporaryDirectory() as td:
            state = Path(td) / "state.json"
            args = argparse.Namespace(
                goal="ship a tiny CLI", minutes=10, model="gemma3:1b",
                sample=True, replace=False
            )
            self.assertEqual(steadystep.command_plan(args, state), 0)
            data = json.loads(state.read_text())
            self.assertIsNotNone(data["pending"])

            done = argparse.Namespace(outcome="Added three README bullets")
            self.assertEqual(steadystep.command_done(done, state), 0)
            data = json.loads(state.read_text())
            self.assertIsNone(data["pending"])
            self.assertEqual(len(data["history"]), 1)

    def test_pending_plan_is_reused_without_ai_call(self):
        with tempfile.TemporaryDirectory() as td:
            state = Path(td) / "state.json"
            args = argparse.Namespace(
                goal="ship a tiny CLI", minutes=10, model="gemma3:1b",
                sample=True, replace=False
            )
            steadystep.command_plan(args, state)
            args.sample = False
            with patch.object(steadystep, "call_ollama") as call:
                steadystep.command_plan(args, state)
                call.assert_not_called()

    def test_compact_history_limits_context(self):
        state = {"history": [
            {"plan": {"title": str(i), "action": "a"}, "outcome": "done"}
            for i in range(10)
        ]}
        h = steadystep.compact_history(state, limit=6)
        self.assertEqual(len(h), 6)
        self.assertEqual(h[0]["title"], "4")

    def test_ollama_json_response_is_parsed(self):
        payload = {
            "response": json.dumps({
                "title": "Read One Section",
                "action": "Read the BST insertion section and write one example by hand.",
                "done_when": "One worked insertion example is written down.",
                "why_now": "It connects the concept to a concrete operation.",
                "encouragement": "A small example is enough for this session."
            })
        }
        response = MagicMock()
        response.read.return_value = json.dumps(payload).encode("utf-8")
        cm = MagicMock()
        cm.__enter__.return_value = response
        cm.__exit__.return_value = False
        with patch("urllib.request.urlopen", return_value=cm):
            plan = steadystep.call_ollama("gemma3:1b", "prompt")
        self.assertEqual(plan.title, "Read One Section")
        self.assertIn("BST insertion", plan.action)

    def test_invalid_model_schema_is_rejected(self):
        payload = {"response": json.dumps({"title": "Only title"})}
        response = MagicMock()
        response.read.return_value = json.dumps(payload).encode("utf-8")
        cm = MagicMock()
        cm.__enter__.return_value = response
        cm.__exit__.return_value = False
        with patch("urllib.request.urlopen", return_value=cm):
            with self.assertRaises(steadystep.SteadyStepError):
                steadystep.call_ollama("gemma3:1b", "prompt")


if __name__ == "__main__":
    unittest.main()
