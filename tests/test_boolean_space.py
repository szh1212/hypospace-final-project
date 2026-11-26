"""Properties of the boolean hypothesis-space scaffolding and official replay."""
import ast
import unittest
from itertools import product
from pathlib import Path
import sys

import sympy as sp

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from boolean_benchmark import (COLLECTION, MAX_DEPTH, MECH_OPTS, OPERATORS, Dataset,
                               load_official, VARIABLES)
from boolean_space import (ALL_INPUTS, LITERALS, assemble, canonical, canonical_hole,
                           completion_plan, completions, observed_rows, skeleton_plan,
                           space_rows, template_rows)

UPSTREAM = ROOT / ".cache/hypospace"
DATASET = Dataset(UPSTREAM, ROOT / ".cache" / COLLECTION)
_, MODULE = load_official(UPSTREAM)
BooleanExpression = MODULE.BooleanExpression


def parse(text):
    try:
        be = BooleanExpression(text, list(VARIABLES), set(OPERATORS))
    except Exception:
        return None
    return be if be.sympy_expr is not None else None


class SpaceRoundTripTests(unittest.TestCase):
    def test_space_size_and_semantic_count(self):
        rows = space_rows(UPSTREAM)
        self.assertEqual(len(rows), 34)  # in-space only; deeper official entries are invalid
        tables = {tuple(sorted(table.items())) for _, _, table in rows}
        self.assertEqual(len(tables), 14)

    def test_every_space_expression_is_in_space(self):
        for text, _, _ in space_rows(UPSTREAM):
            be = parse(text)
            self.assertIsNotNone(be, text)

            def d(node):
                return 0 if isinstance(node, sp.Symbol) else 1 + max((d(a) for a in node.args),
                                                                      default=0)
            self.assertLessEqual(d(be.sympy_expr), MAX_DEPTH, text)

    def test_canonical_round_trips_for_every_space_expression(self):
        for text, key, table in space_rows(UPSTREAM):
            be = parse(text)
            self.assertIsNotNone(be, text)
            self.assertEqual(be.mechanistic_key(**MECH_OPTS), key, text)
            self.assertEqual(be.truth_table, table, text)

    def test_collection_ground_truths_round_trip(self):
        for rows in DATASET.bench.complete_dataset["datasets_by_n_observations"].values():
            for case in rows:
                for gt in case["ground_truth_expressions"]:
                    be = parse(gt["formula"])
                    self.assertIsNotNone(be, gt["formula"])
                    stored = ast.literal_eval(gt["mechanistic_key"])
                    self.assertEqual(be.mechanistic_key(**MECH_OPTS), stored, gt["formula"])

    def test_nor_keyword_only_for_plain_arguments(self):
        for text, _, _ in space_rows(UPSTREAM):
            if "NOR(" in text:
                start = text.index("NOR(") + 4
                depth = 0
                for char in text[start:]:
                    if char == "(":
                        depth += 1
                    elif char == ")":
                        if depth == 0:
                            break
                        depth -= 1
                self.assertEqual(depth, 0, text)


class TemplateTests(unittest.TestCase):
    def test_every_template_has_exactly_one_hole(self):
        for template in template_rows(UPSTREAM):
            holes = [n for n in sp.preorder_traversal(template["expr"]) if n == sp.Symbol("h")]
            self.assertEqual(len(holes), 1, template["hole_text"])
            self.assertIn("[?]", template["hole_text"])
            self.assertNotIn("h", template["hole_text"].replace("[?]", ""))

    def test_template_instances_round_trip(self):
        for template in template_rows(UPSTREAM):
            self.assertTrue(set(template["instances"]) <= set(LITERALS), template["hole_text"])
            self.assertTrue(template["instances"], template["hole_text"])  # h -> x always works
            for lit, inst in template["instances"].items():
                be = parse(inst["text"])
                self.assertIsNotNone(be, inst["text"])
                self.assertEqual(be.mechanistic_key(**MECH_OPTS), inst["key"], inst["text"])
                self.assertEqual(be.truth_table, inst["table"], inst["text"])

    def test_templates_cover_the_space(self):
        """Every space expression is an instance of at least one template."""
        space_keys = {key for _, key, _ in space_rows(UPSTREAM)}
        covered = set()
        for template in template_rows(UPSTREAM):
            covered.update(inst["key"] for inst in template["instances"].values())
        self.assertEqual(space_keys, covered)


class CompletionTests(unittest.TestCase):
    def test_completions_extend_observations_and_are_feasible(self):
        for case in DATASET.cases.values():
            if case["n_observations"] >= 4:
                continue  # fully observed cases have no unobserved rows to complete
            public = {k: case[k] for k in ("observations", "variables", "operators", "max_depth")}
            observed = observed_rows(public)
            comps = completions(UPSTREAM, public)
            self.assertTrue(comps, case["observation_set_id"])
            space_tables = [t for _, _, t in space_rows(UPSTREAM)]
            for table in comps:
                for inputs, output in observed.items():
                    self.assertEqual(table[inputs], output)
                self.assertTrue(any(all(s_table[t] == table[t] for t in ALL_INPUTS)
                                    for s_table in space_tables))

    def test_plans_are_deterministic_and_budgeted(self):
        for oid in list(DATASET.cases)[:8]:
            case = DATASET.cases[oid]
            public = {k: case[k] for k in ("observations", "variables", "operators", "max_depth")}
            for seed in (17, 42):
                plan = skeleton_plan(UPSTREAM, public, seed, 16)
                self.assertEqual(len(plan), 16)
                self.assertEqual(skeleton_plan(UPSTREAM, public, seed, 16), plan)
                for cell in plan:
                    self.assertTrue(cell["matches"], oid)
                    for lit, inst in cell["matches"].items():
                        self.assertTrue(all(inst["table"][t] == cell["completion"][t]
                                            for t in ALL_INPUTS), oid)
                v1 = completion_plan(UPSTREAM, public, seed, 16)
                self.assertEqual(len(v1), 16)
                self.assertEqual(completion_plan(UPSTREAM, public, seed, 16), v1)

    def test_plan_rotates_completions(self):
        case = DATASET.cases["n2_inputs_10_11_outputs_11"]
        public = {k: case[k] for k in ("observations", "variables", "operators", "max_depth")}
        plan = skeleton_plan(UPSTREAM, public, 17, 16)
        order = []
        for cell in plan:
            signature = tuple(sorted(cell["completion"].items()))
            if signature not in order:
                order.append(signature)
        self.assertGreaterEqual(len(order), 2)  # two unobserved rows
        for index, cell in enumerate(plan):
            self.assertEqual(tuple(sorted(cell["completion"].items())),
                             order[index % len(order)])


class AssemblyTests(unittest.TestCase):
    def _case(self, oid):
        case = DATASET.cases[oid]
        public = {k: case[k] for k in ("observations", "variables", "operators", "max_depth")}
        return case, public

    def test_completion_variant_accepts_parsed_output(self):
        case, public = self._case("n3_inputs_00_01_10_outputs_111")
        condition = completion_plan(UPSTREAM, public, 17, 16)[0]
        text = assemble(DATASET, condition, "Expression: x OR y", "completion")
        self.assertEqual(text, "x OR y")
        self.assertIsNone(assemble(DATASET, condition, "no expression here", "completion"))

    def test_skeleton_variant_enforces_stratum(self):
        case, public = self._case("n2_inputs_10_11_outputs_11")
        plan = skeleton_plan(UPSTREAM, public, 17, 16)
        cell = plan[0]
        good = next(iter(cell["matches"].values()))
        out = assemble(DATASET, cell, "Expression: " + good["text"], "skeleton")
        self.assertEqual(out, good["text"])
        observed = observed_rows(public)
        other = None
        for text, _, table in space_rows(UPSTREAM):
            if all(table[t] == observed[t] for t in observed) and not all(
                    table[t] == cell["completion"][t] for t in ALL_INPUTS):
                other = text
                break
        self.assertIsNotNone(other)
        self.assertIsNone(assemble(DATASET, cell, "Expression: " + other, "skeleton"))

    def test_skeleton_valid_rescues_and_keeps_valid_holes(self):
        case, public = self._case("n2_inputs_10_11_outputs_11")
        for cell in skeleton_plan(UPSTREAM, public, 17, 16):
            good = next(iter(cell["matches"].values()))
            kept = assemble(DATASET, cell, "Expression: " + good["text"], "skeleton_valid")
            self.assertIsNotNone(kept)
            be = parse(kept)
            self.assertTrue(all(be.truth_table[t] == cell["completion"][t] for t in ALL_INPUTS))
            garbage = assemble(DATASET, cell, "this is not an expression", "skeleton_valid")
            self.assertIsNotNone(garbage)  # rescue always lands in the stratum
            be2 = parse(garbage)
            self.assertTrue(all(be2.truth_table[t] == cell["completion"][t] for t in ALL_INPUTS))
            # a wrong-but-parseable hole is repaired into the stratum as well
            wrong = assemble(DATASET, cell, "Expression: x AND NOT y", "skeleton_valid")
            if wrong is not None:
                be3 = parse(wrong)
                self.assertTrue(all(be3.truth_table[t] == cell["completion"][t]
                                    for t in ALL_INPUTS))


class EvaluatorSemanticsTests(unittest.TestCase):
    @staticmethod
    def _compatible(oid):
        """Canonical texts of every space expression matching the case's observations."""
        case = DATASET.cases[oid]
        public = {k: case[k] for k in ("observations", "variables", "operators", "max_depth")}
        observed = observed_rows(public)
        out = []
        for text, _, table in space_rows(UPSTREAM):
            if all(table[t] == observed[t] for t in observed):
                out.append(text)
        return case, out

    def test_official_scoring_recovers_all_recoverable_ground_truths(self):
        oid = "n3_inputs_00_01_10_outputs_111"
        case, texts = self._compatible(oid)
        outputs = ["Expression: " + t for t in texts]
        scored = DATASET.score(case, outputs)
        self.assertEqual(scored["n_valid"], len(outputs))
        self.assertEqual(scored["valid_rate"], 1.0)
        recoverable = {k for _, k, _ in space_rows(UPSTREAM)}
        stored = [ast.literal_eval(gt["mechanistic_key"])
                  for gt in case["ground_truth_expressions"]]
        expected = len([k for k in stored if k in recoverable]) / len(stored)
        self.assertAlmostEqual(scored["recovery_rate"], expected)

    def test_repetition_collapses_uniqueness(self):
        oid = "n3_inputs_00_01_10_outputs_111"
        case, texts = self._compatible(oid)
        outputs = ["Expression: " + texts[0]] * 16
        scored = DATASET.score(case, outputs)
        self.assertEqual(scored["valid_rate"], 1.0)
        self.assertAlmostEqual(scored["novelty_rate"], 1 / 16)

    def test_invalid_attempt_counts_nothing(self):
        oid = "n3_inputs_00_01_10_outputs_111"
        case, texts = self._compatible(oid)
        outputs = [""] * 8 + ["Expression: " + texts[0]] * 8
        scored = DATASET.score(case, outputs)
        self.assertEqual(scored["valid_rate"], 0.5)


if __name__ == "__main__":
    unittest.main()
