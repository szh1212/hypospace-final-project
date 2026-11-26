"""Prompt faces for the boolean hierarchical route."""
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from boolean_benchmark import Dataset, COLLECTION, load_official
from boolean_prompts import completion_prompt, skeleton_prompt
from boolean_space import completion_plan, skeleton_plan

UPSTREAM = ROOT / ".cache/hypospace"
DATASET = Dataset(UPSTREAM, ROOT / ".cache" / COLLECTION)
_, MODULE = load_official(UPSTREAM)


class PromptTests(unittest.TestCase):
    def _public(self, oid):
        case = DATASET.cases[oid]
        return {k: case[k] for k in ("observations", "variables", "operators", "max_depth")}

    def test_official_prompt_mentions_observations_and_prior(self):
        case = DATASET.cases["n3_inputs_00_01_10_outputs_111"]
        observations = [MODULE.BooleanObservation(o["inputs"], o["output"])
                        for o in case["observations"]]
        prompt = DATASET.bench.create_prompt(observations, ["x AND y", "NOT x"])
        self.assertIn("(x=0, y=0) -> 1", prompt)
        self.assertIn("Expression: x AND y", prompt)
        self.assertIn("Expression: NOT x", prompt)
        self.assertIn("Expression: ", prompt)

    def test_completion_prompt_lists_observations_and_targets(self):
        public = self._public("n3_inputs_00_01_10_outputs_111")
        condition = completion_plan(UPSTREAM, public, 17, 16)[0]
        prompt = completion_prompt(public, condition)
        for obs in public["observations"]:
            self.assertIn(obs["string"], prompt)
        self.assertIn("(x=1, y=1) ->", prompt)
        self.assertNotIn("[?]", prompt)

    def test_skeleton_prompt_fixes_the_hole(self):
        public = self._public("n3_inputs_00_01_10_outputs_111")
        condition = skeleton_plan(UPSTREAM, public, 17, 16)[0]
        prompt = skeleton_prompt(public, condition)
        self.assertIn(condition["template"]["hole_text"], prompt)
        self.assertIn("[?]", prompt)
        self.assertIn("Fill [?] with exactly one of: x, y, NOT x, NOT y", prompt)
        self.assertIn("(x=1, y=1) ->", prompt)

    def test_every_scheduled_cell_has_a_distinct_prompt(self):
        public = self._public("n3_inputs_00_01_10_outputs_111")
        plan = skeleton_plan(UPSTREAM, public, 17, 16)
        prompts = [skeleton_prompt(public, c) for c in plan]
        self.assertEqual(len(set(prompts)), 16)


if __name__ == "__main__":
    unittest.main()
