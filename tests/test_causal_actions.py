"""Offline contracts for the bounded public local-edit control."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import causal_actions as actions


def public(roots=(), limit=4):
    nodes = list("ABCD")
    return {
        "nodes": nodes, "max_edges": limit,
        "observations": [
            {"perturbed_node": root, "effects": {n: int(n in targets) for n in nodes}}
            for root, targets in roots
        ],
    }


def accepted(*edges):
    return {"edges": list(edges), "valid": True}


class ActionTests(unittest.TestCase):
    def test_single_seed_is_transitively_reduced(self):
        case = public([("A", "BC"), ("B", "C")])
        menu = actions.action_menu(case, [], 0, 17)
        self.assertEqual(menu[0], (("A", "B"), ("B", "C")))
        self.assertGreater(len(menu), 1)
        self.assertLessEqual(len(menu), 4)
        self.assertEqual(len(menu), len(set(menu)))
        for graph in menu:
            self.assertEqual(graph, tuple(sorted(graph)))
            self.assertTrue(actions._valid(case, graph))

    def test_contradictions_and_unachievable_cap_return_no_menu(self):
        for case in [public([("A", "B"), ("B", "A")]),
                     public([("A", "BCD")], limit=2),
                     public([("A", "B"), ("B", "C")])]:
            with self.subTest(case=case):
                menu = actions.action_menu(case, [], 0, 17)
                self.assertEqual(menu, [])
                self.assertEqual(actions.decode_choice("Choice: 1", menu), "INVALID_CHOICE")
                self.assertIn("No valid", actions.action_prompt(case, menu))

    def test_unseen_moves_preferred_and_previous_sources_revisited(self):
        # A reaches each other node, so a star at the tight edge cap has no valid edit.
        restricted = public([("A", "BCD")], limit=3)
        star = (("A", "B"), ("A", "C"), ("A", "D"))
        self.assertEqual(actions.action_menu(restricted, [], 0, 17), [star])
        case = public()
        earlier, recent = (("A", "B"),), ()
        # Exhaust the one-edge neighbors of the recent empty graph. The earlier
        # graph still has a two-edge neighbor that the walk has never selected.
        single_edges = [
            ((u, v),) for u in "ABCD" for v in "ABCD" if u != v
        ]
        history = [accepted(*graph) for graph in single_edges if graph != earlier]
        history += [accepted(*earlier), accepted(*recent)]
        menu = actions.action_menu(case, history, len(history), 17)
        self.assertEqual(menu[0], earlier)
        self.assertTrue(all(len(graph) == 2 for graph in menu[1:]))

    def test_only_history_and_public_constraints_drive_generation(self):
        case = public()
        previous = [accepted(("C", "A")), {"valid": False, "edges": [["B", "D"]]}]
        poisoned = dict(case, ground_truth_graphs=object(), n_compatible_graphs=object())
        a = actions.action_menu(case, previous, 2, 17)
        self.assertEqual(a, actions.action_menu(poisoned, previous, 2, 17))
        self.assertEqual(a, actions.action_menu(case, previous[:1], 2, 17))
        self.assertEqual(a[0], (("C", "A"),))
        self.assertNotEqual(a, actions.action_menu(public([("C", "")]), previous, 2, 17))
        self.assertGreater(len({tuple(actions.action_menu(case, [], i, 17)) for i in range(5)}), 1)
        self.assertNotIn("ground_truth", actions.action_prompt(poisoned, a))

    def test_only_one_step_neighbors_are_considered(self):
        case = public()
        source = (("A", "B"), ("B", "C"))
        with patch.object(actions, "_valid", wraps=actions._valid) as valid:
            menu = actions.action_menu(case, [accepted(*source)], 1, 17)
        self.assertEqual(menu[0], source)
        self.assertLessEqual(valid.call_count, 20)
        for graph in menu[1:]:
            removed = set(source) - set(graph)
            added = set(graph) - set(source)
            self.assertTrue(len(added) + len(removed) == 1 or
                            (len(added) == len(removed) == 1 and
                             next(iter(added)) == tuple(reversed(next(iter(removed))))))
        labels = actions.action_prompt(case, [source, source[:-1], (), (("B", "A"), ("B", "C"))][:2])
        self.assertIn("KEEP", labels)
        self.assertIn("DELETE B->C", labels)

    def test_decode_uses_exactly_one_model_choice_without_repair(self):
        menu = [(), (("A", "B"),), (("A", "D"), ("D", "C"))]
        self.assertEqual(actions.decode_choice(" Choice: 1\n", menu), "Graph: No edges")
        self.assertEqual(actions.decode_choice("Choice: 2", menu), "Graph: A->B")
        self.assertEqual(actions.decode_choice("Choice: 3", menu), "Graph: A->D, D->C")
        for raw in [None, "", "2", "Choice: 0", "Choice: 4", "Choice: 2.", "Choice: 1\nChoice: 2",
                    "I choose Choice: 1", "Choice: 1\nGraph: A->B", "Graph: A->B"]:
            with self.subTest(raw=raw):
                self.assertEqual(actions.decode_choice(raw, menu), "INVALID_CHOICE")
