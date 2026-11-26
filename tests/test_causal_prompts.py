import unittest

from src.causal_prompts import _branch_arms, _reward, adaptive_constraint, prompt_for


def case(*observations):
    return {
        "nodes": list("ABCD"),
        "max_edges": 4,
        "observations": [{"perturbed_node": root,
                          "effects": {node: int(node in descendants) for node in "ABCD"}}
                         for root, descendants in observations],
    }


PUBLIC = case(("A", "B"))
OFFICIAL = "unchanged official prompt\n"


def prompt(method, previous=(), public=PUBLIC, index=None):
    if index is None:
        index = len(previous)
    return prompt_for(method, public, previous, index, 17, OFFICIAL)


def graph(*edges, valid=True):
    return {"valid": valid, "edges": list(edges)}


class PromptTests(unittest.TestCase):
    def test_controls(self):
        self.assertEqual(prompt("official"), OFFICIAL)
        for index, count in enumerate((1, 2, 3, 4, 1)):
            self.assertEqual(prompt("edge_count", index=index), OFFICIAL
                             + "\n\nFor this attempt, also satisfy these subspace constraints:\n"
                             + f"Use exactly {count} directed edges.")

    def test_cold_start_has_no_graph_example(self):
        base = prompt("reachability")
        self.assertIn("From A, must reach: B. Must never reach: C, D.", base)
        self.assertIn("one line", base)
        self.assertNotIn("A->B", base)
        self.assertEqual(base, prompt("feedback"))
        self.assertTrue(prompt("adaptive").startswith(base + "\nStructural constraint"))

    def test_paired_text_and_exact_diagnostics(self):
        previous = [graph(("A", "C"), ("C", "D"), valid=False)]
        reach = prompt("reachability", previous)
        feedback = prompt("feedback", previous)
        adaptive = prompt("adaptive", previous)
        self.assertTrue(feedback.startswith(reach + "\n"))
        self.assertIn("From A, the last graph missed paths to B.", feedback)
        self.assertIn("From A, the last graph had unwanted paths to C, D.", feedback)
        self.assertEqual(adaptive.rsplit("\n", 1)[0], feedback)

    def test_parse_failure_and_duplicate(self):
        failed = [{"edges": None, "valid": False}]
        self.assertIn("failed the graph parser", prompt("feedback", failed))
        previous = [graph(("A", "B"), ("D", "C")), graph(("D", "C"), ("A", "B"))]
        self.assertIn("repeated an earlier valid graph", prompt("feedback", previous))
        self.assertIn("Change at least one direct edge", prompt("feedback", previous))

    def test_edges_filtered_by_public_observations(self):
        available = {edge for seed in range(32) for edge, _ in _branch_arms(PUBLIC, seed)}
        # A must reach only B, so it must contain A->B and cannot contain
        # B->A, B->C, B->D, A->C, or A->D. No feature branches on these.
        self.assertTrue(available)
        self.assertFalse(available & {("A", "B"), ("A", "C"), ("A", "D"),
                                      ("B", "A"), ("B", "C"), ("B", "D")})
        fixed = case(("A", ""), ("B", ""), ("C", ""), ("D", ""))
        self.assertIsNone(adaptive_constraint(fixed, [], 0, 42))
        self.assertEqual(prompt("feedback", public=fixed), prompt("adaptive", public=fixed))

    def test_reward_requires_novelty_validity_and_branch_compliance(self):
        arm = (("D", "C"), True)
        valid = graph(("A", "B"), ("D", "C"))
        seen = set()
        self.assertEqual(_reward(arm, dict(valid, valid=False), seen), 0)
        self.assertFalse(seen)
        self.assertEqual(_reward(arm, valid, seen), 1)
        self.assertEqual(_reward(arm, valid, seen), 0)
        unseen = graph(("A", "B"))
        self.assertEqual(_reward(arm, unseen, seen), 0)
        self.assertIn(frozenset(unseen["edges"]), seen)

    def test_success_reused_failure_switched_and_quota_bounded(self):
        initial = adaptive_constraint(PUBLIC, [], 0, 17)
        edge, required = initial
        self.assertTrue(required)
        first = graph(("A", "B"), edge)
        self.assertEqual(adaptive_constraint(PUBLIC, [first], 1, 17), initial)
        self.assertNotEqual(adaptive_constraint(PUBLIC, [dict(first, valid=False)], 1, 17), initial)
        self.assertNotEqual(adaptive_constraint(PUBLIC, [first, first], 2, 17), initial)
        # Another fresh compliant success after the first still exhausts the quota.
        second = graph(("A", "B"), edge, ("D", "B") if edge != ("D", "B") else ("C", "B"))
        self.assertNotEqual(adaptive_constraint(PUBLIC, [first, second], 2, 17), initial)

    def test_all_failures_explore_every_branch(self):
        history = [{"edges": None, "valid": False}] * 15
        arms = [adaptive_constraint(PUBLIC, history[:i], i, 17) for i in range(16)]
        self.assertEqual(set(arms), set(_branch_arms(PUBLIC, 17)))
        self.assertTrue(all(old != new for old, new in zip(arms, arms[1:])))


if __name__ == "__main__":
    unittest.main()
