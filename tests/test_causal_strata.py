"""A-priori parent sets must partition all compatible DAGs without consulting them."""
from collections import Counter
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from causal_benchmark import Dataset
from parent_strata import (assemble, enforce_limit, filtered_completion, forced_edges,
                           joint_skeleton_plan, parent_plan, skeleton_plan)


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

    def test_forced_edges_appear_in_every_official_solution(self):
        upstream = Path(os.environ.get("HYPOSPACE_UPSTREAM", ROOT / ".cache/hypospace"))
        if not upstream.is_dir():
            self.skipTest("Pinned causal checkout unavailable")
        for case in Dataset(upstream).cases.values():
            public = {key: case[key] for key in ("nodes", "observations", "max_edges")}
            forced = forced_edges(public)
            for graph in case["ground_truth_graphs"]:
                edges = {tuple(edge) for edge in graph["edges"]}
                self.assertTrue(forced <= edges, (case["observation_set_id"], forced - edges))
                self.assertLessEqual(len(edges), case["max_edges"])

    def test_complete_forced_fixes_the_whole_backbone(self):
        public = {"nodes": ["A", "B", "C", "D"], "max_edges": 4, "observations": [
            {"perturbed_node": "B", "effects": {"A": 1, "B": 0, "C": 0, "D": 0}},
            {"perturbed_node": "C", "effects": {"A": 1, "B": 0, "C": 0, "D": 1}},
        ]}
        forced = forced_edges(public)
        self.assertIn(("C", "D"), forced)
        for seed in (17, 42):
            plan = skeleton_plan(public, seed, 16, "complete_forced")
            anchor = plan[0]["node"]
            for row in plan:
                fixed = {tuple(edge) for edge in row["fixed_edges"]}
                self.assertTrue(forced <= fixed, (seed, forced - fixed))
                self.assertEqual(row["node"], anchor)
                self.assertIn(f"at most {max(4 - len(fixed), 0)} more", row["prompt"])
                assembled = assemble(row, [])
                self.assertTrue(forced <= assembled)

    def test_enforce_limit_drops_later_additions_only(self):
        condition = dict(node="D", parents=["A", "B"],
                         fixed_edges=[("A", "D"), ("B", "D"), ("C", "D")])
        final = enforce_limit(condition, [("C", "D"), ("B", "A"), ("D", "A")], 3)
        self.assertEqual(final, frozenset({("A", "D"), ("B", "D"), ("C", "D")}))
        final = enforce_limit(condition, [("B", "A"), ("D", "A")], 4)
        self.assertEqual(final, frozenset({("A", "D"), ("B", "D"), ("C", "D"), ("B", "A")}))
        self.assertEqual(enforce_limit(condition, [], 3), frozenset({("A", "D"), ("B", "D"), ("C", "D")}))
        self.assertEqual(enforce_limit(condition, [("B", "A")], 5), frozenset(
            {("A", "D"), ("B", "D"), ("C", "D"), ("B", "A")}))

    def test_filtered_completion_keeps_valid_unions_untouched(self):
        public = {"nodes": ["A", "B", "C", "D"], "max_edges": 4, "observations": [
            {"perturbed_node": "A", "effects": {"A": 0, "B": 1, "C": 0, "D": 0}},
        ]}
        condition = dict(node="D", parents=[], fixed_edges=[])
        for edges in ([("A", "B")], [("D", "B"), ("A", "B")]):
            self.assertEqual(filtered_completion(condition, edges, public),
                             frozenset(map(tuple, edges)))

    def test_filtered_completion_drops_unwanted_edges_and_cycles(self):
        public = {"nodes": ["A", "B", "C", "D"], "max_edges": 4, "observations": [
            {"perturbed_node": "A", "effects": {"A": 0, "B": 1, "C": 0, "D": 0}},
        ]}
        condition = dict(node="D", parents=[], fixed_edges=[])
        # A->C makes A reach C (forbidden); D->B is fine afterwards.
        final = filtered_completion(condition, [("A", "C"), ("D", "B")], public)
        self.assertEqual(final, frozenset({("D", "B")}))
        # A 2-cycle in the additions is rejected while the acyclic part survives.
        final = filtered_completion(condition, [("A", "B"), ("B", "A")], public)
        self.assertEqual(final, frozenset({("A", "B")}))
        # An addition into the anchor that is not in the stratum is dropped.
        final = filtered_completion(condition, [("A", "B"), ("A", "D")], public)
        self.assertEqual(final, frozenset({("A", "B")}))

    def test_filtered_completion_reproduces_every_truth(self):
        upstream = Path(os.environ.get("HYPOSPACE_UPSTREAM", ROOT / ".cache/hypospace"))
        if not upstream.is_dir():
            self.skipTest("Pinned causal checkout unavailable")
        for case in Dataset(upstream).cases.values():
            public = {key: case[key] for key in ("nodes", "observations", "max_edges")}
            for seed in (17, 42):
                plan = skeleton_plan(public, seed, 8, "complete_forced_valid")
                for graph in case["ground_truth_graphs"]:
                    row = next(row for row in plan
                               if tuple(row["parents"]) == tuple(sorted(
                                   tail for tail, head in graph["edges"] if head == row["node"])))
                    graph_edges = frozenset(map(tuple, graph["edges"]))
                    self.assertEqual(filtered_completion(row, graph["edges"], public), graph_edges)

    def test_joint_plan_covers_every_official_solution(self):
        upstream = Path(os.environ.get("HYPOSPACE_UPSTREAM", ROOT / ".cache/hypospace"))
        if not upstream.is_dir():
            self.skipTest("Pinned causal checkout unavailable")
        for case in Dataset(upstream).cases.values():
            public = {key: case[key] for key in ("nodes", "observations", "max_edges")}
            forced = forced_edges(public)
            for seed in (17, 42):
                # 64 calls schedule the full joint product (<= 8 x 8 strata).
                plan = joint_skeleton_plan(public, seed, 64)
                anchor = plan[0]["node"]
                strata = {(tuple(row["parents"]),
                           row["node2"],
                           tuple(row.get("parents2", ()))) for row in plan}
                for graph in case["ground_truth_graphs"]:
                    edges = {tuple(edge) for edge in graph["edges"]}
                    parents1 = tuple(sorted(tail for tail, head in edges if head == anchor))
                    found = False
                    for row in plan:
                        if tuple(row["parents"]) != parents1:
                            continue
                        if row["node2"] is None:
                            found = True
                            continue
                        parents2 = tuple(sorted(tail for tail, head in edges if head == row["node2"]))
                        if (parents1, row["node2"], parents2) in strata:
                            found = True
                    self.assertTrue(found, (case["observation_set_id"], parents1))
                    for row in plan:
                        fixed = {tuple(edge) for edge in row["fixed_edges"]}
                        self.assertTrue(forced <= fixed)

    def test_joint_plan_guards_both_anchors(self):
        public = {"nodes": ["A", "B", "C", "D"], "max_edges": 4, "observations": [
            {"perturbed_node": "B", "effects": {"A": 1, "B": 0, "C": 0, "D": 0}},
            {"perturbed_node": "C", "effects": {"A": 1, "B": 0, "C": 0, "D": 1}},
        ]}
        for seed in (17, 42):
            plan = joint_skeleton_plan(public, seed, 16)
            anchor = plan[0]["node"]
            self.assertEqual(len({row["node"] for row in plan}), 1)
            for row in plan:
                self.assertEqual(row["node"], anchor)
                self.assertIn(f"No other edge may end at {anchor}.", row["prompt"])
                self.assertEqual(row["guarded"][0], anchor)
                if row["node2"] is not None:
                    self.assertIn(f"No other edge may end at {row['node2']}.", row["prompt"])
                    self.assertEqual(row["guarded"], [anchor, row["node2"]])
                remaining = 4 - len(row["fixed_edges"])
                self.assertIn(f"at most {max(remaining, 0)} more", row["prompt"])
