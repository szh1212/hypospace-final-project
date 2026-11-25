"""A-priori parent sets must partition all compatible DAGs without consulting them."""
from collections import Counter
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from causal_benchmark import Dataset
from parent_strata import assemble, parent_plan, skeleton_plan


class ParentStrataTests(unittest.TestCase):
    def test_round_robin_repeats_a_balanced_precomputed_prefix(self):
        public = {"nodes": ["A", "B", "C", "D"], "max_edges": 4, "observations": []}
        plan = parent_plan(public, seed=5, budget=19)
        self.assertEqual(plan[:7], parent_plan(public, seed=5, budget=7))
        self.assertEqual(len({entry["node"] for entry in plan}), 1)
        counts = Counter(tuple(entry["parents"]) for entry in plan)
        self.assertEqual(len(counts), 8)
        self.assertEqual(max(counts.values()) - min(counts.values()), 1)
        self.assertEqual(plan[:8], plan[8:16])
        self.assertNotEqual(plan, parent_plan(public, seed=991, budget=19))

    def test_unavoidable_direct_edge_survives_every_stratum(self):
        public = {"nodes": ["A", "B"], "max_edges": 1, "observations": [
            {"perturbed_node": "A", "effects": {"A": 0, "B": 1}}
        ]}
        for seed in range(8):
            plan = parent_plan(public, seed, 3)
            self.assertEqual(len({(r["node"], tuple(r["parents"])) for r in plan}), 1)
            self.assertEqual(plan[0]["parents"], ["A"] if plan[0]["node"] == "B" else [])

    def test_every_official_solution_belongs_to_exactly_one_planned_stratum(self):
        upstream = Path(os.environ.get("HYPOSPACE_UPSTREAM", ROOT / ".cache/hypospace"))
        if not upstream.is_dir():
            self.skipTest("Pinned causal checkout unavailable")
        for case in Dataset(upstream).cases.values():
            public = {key: case[key] for key in ("nodes", "observations", "max_edges")}
            for seed in (17, 42):
                plan = parent_plan(public, seed, 8)
                node = plan[0]["node"]
                buckets = {tuple(row["parents"]) for row in plan}
                for graph in case["ground_truth_graphs"]:
                    parents = tuple(sorted(tail for tail, head in graph["edges"] if head == node))
                    self.assertIn(parents, buckets, (case["observation_set_id"], node, parents))
                self.assertEqual(len(set(tuple(r["parents"]) for r in plan[:len(buckets)])), len(buckets))

    def test_skeleton_plan_shares_the_stratum_cycle_and_completion_limit(self):
        public = {"nodes": ["A", "B", "C", "D"], "max_edges": 4, "observations": []}
        for seed in (17, 42):
            for variant in ("enforce", "complete"):
                plan = skeleton_plan(public, seed, 19, variant)
                self.assertEqual(plan[:7], skeleton_plan(public, seed, 7, variant))
                self.assertEqual([tuple(r["parents"]) for r in plan],
                                 [tuple(r["parents"]) for r in parent_plan(public, seed, 19)])
                for row in plan:
                    remaining = 4 - len(row["parents"])
                    if variant == "complete":
                        self.assertIn(f"at most {max(remaining, 0)} more", row["prompt"])
                    self.assertTrue(row["prompt"].startswith(
                        "These direct edges are already fixed:" if row["parents"]
                        else f"No edge may end at {row['node']}."))

    def test_assemble_fixes_stratum_parents_and_drops_conflicts(self):
        condition = dict(node="D", parents=["A", "B"])
        parsed = [("A", "D"), ("C", "D"), ("A", "C"), ("A", "C")]
        self.assertEqual(assemble(condition, parsed),
                         frozenset({("A", "D"), ("B", "D"), ("A", "C")}))
        self.assertEqual(assemble(dict(node="D", parents=[]), [("A", "C"), ("B", "D")]),
                         frozenset({("A", "C")}))
        self.assertEqual(assemble(dict(node="D", parents=["C"]), []),
                         frozenset({("C", "D")}))

    def test_every_official_solution_stays_reachable_under_assembly(self):
        upstream = Path(os.environ.get("HYPOSPACE_UPSTREAM", ROOT / ".cache/hypospace"))
        if not upstream.is_dir():
            self.skipTest("Pinned causal checkout unavailable")
        for case in Dataset(upstream).cases.values():
            public = {key: case[key] for key in ("nodes", "observations", "max_edges")}
            for seed in (17, 42):
                plan = skeleton_plan(public, seed, 8, "complete")
                for graph in case["ground_truth_graphs"]:
                    row = next(row for row in plan
                               if tuple(row["parents"]) == tuple(sorted(
                                   tail for tail, head in graph["edges"] if head == row["node"])))
                    graph_edges = frozenset(map(tuple, graph["edges"]))
                    assembled = assemble(row, graph["edges"])
                    self.assertEqual(graph_edges - assembled, set())
                    self.assertEqual(assembled, graph_edges)
