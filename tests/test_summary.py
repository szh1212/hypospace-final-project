"""Checks for complete cells, observation-level contrasts, and real resource totals."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))


def api():
    if importlib.util.find_spec("summarize_causal") is None:
        raise AssertionError("Causal summary implementation is missing")
    import summarize_causal
    return summarize_causal


class SummaryTests(unittest.TestCase):
    def config(self, methods=None):
        return {"methods": methods or ["official", "adaptive"], "budget": 16,
                "dev": ["one", "two"], "test": ["one", "two"],
                "dev_seeds": [17, 42], "test_seeds": [17, 42]}

    def cell(self, method, case, seed, rate=.5):
        return {
            "method": method, "case_id": case, "seed": seed, "attempts": 16,
            "calls": 16, "input_tokens": 10, "output_tokens": 5, "seconds": 1.5,
            "prefixes": {str(k): {"V": 1., "U": .5, "R": min(rate, k / 16)} for k in [4, 8, 16]},
            "V": 1., "U": .5, "R": rate, "parsed": 16, "valid": 16,
            "recovered": int(rate * 16), "solution_count": 16, "activated": 2,
        }

    def summary(self, methods=None):
        config = self.config(methods)
        return {"protocol": config, "split": "test", "identity": {"fixture": True},
                "rows": [self.cell(method, case, seed) for method in config["methods"]
                         for case in config["test"] for seed in config["test_seeds"]]}

    def test_completeness_rejects_missing_extra_duplicate_and_wrong_budget_cells(self):
        module = api()
        for mutation in ["missing", "extra", "duplicate", "budget"]:
            source = self.summary()
            if mutation == "missing":
                source["rows"].pop()
            elif mutation == "extra":
                source["rows"].append(self.cell("unconfigured", "one", 17))
            elif mutation == "duplicate":
                source["rows"].append(dict(source["rows"][0]))
            else:
                source["rows"][0]["attempts"] = 15
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                module.verify_cells(source["rows"], source["protocol"], source["split"])
        source = self.summary()
        counts = module.verify_cells(source["rows"], source["protocol"], source["split"])
        self.assertEqual(counts["actual_cells"], 8)
        self.assertEqual(counts["n_cases"], 2)

    def test_bootstrap_uses_case_deltas_after_averaging_seeds(self):
        source = self.summary()
        rates = {("official", "one", 17): 0., ("official", "one", 42): .5,
                 ("official", "two", 17): 0., ("official", "two", 42): .25,
                 ("adaptive", "one", 17): .25, ("adaptive", "one", 42): .75,
                 ("adaptive", "two", 17): .5, ("adaptive", "two", 42): .75}
        source["rows"] = [self.cell(row["method"], row["case_id"], row["seed"],
                                    rates[row["method"], row["case_id"], row["seed"]])
                          for row in source["rows"]]
        report = api().summarize(source)
        contrast = report["contrasts"][0]
        self.assertEqual(contrast["n_cases"], 2)
        self.assertEqual(contrast["per_case_deltas"], {"one": .25, "two": .5})
        self.assertEqual(contrast["mean_delta"], .375)
        self.assertEqual(contrast["ci95"], [.25, .5])
        self.assertEqual(report["methods"]["official"]["macro"]["R"], .1875)
        self.assertEqual(report["bootstrap"]["replicates"], 2000)

    def test_identical_case_differences_give_identical_interval_and_reproduce(self):
        source = self.summary()
        for row in source["rows"]:
            if row["method"] == "adaptive":
                row["R"] = .75
                row["recovered"] = 12
                row["prefixes"]["16"]["R"] = .75
        first = api().summarize(source)
        self.assertEqual(first, api().summarize(source))
        self.assertEqual(first["contrasts"][0]["ci95"], [.25, .25])

    def test_totals_preserve_planning_calls_zero_call_controls_and_activation(self):
        source = self.summary(["official", "action_uniform"])
        for row in source["rows"]:
            row["calls"] = 17 if row["method"] == "official" else 0
        report = api().summarize(source)
        self.assertEqual(report["methods"]["official"]["totals"], {
            "attempts": 64, "calls": 68, "input_tokens": 40, "output_tokens": 20,
            "total_tokens": 60, "seconds": 6., "parsed": 64, "valid": 64,
            "recovered": 32, "activated": 8,
        })
        self.assertEqual(report["methods"]["action_uniform"]["totals"]["calls"], 0)

    def test_requested_primary_and_ablation_contrasts_are_present(self):
        methods = ["official", "edge_count", "reachability", "feedback", "adaptive",
                   "action_llm", "action_uniform"]
        report = api().summarize(self.summary(methods))
        pairs = {(row["baseline"], row["method"]) for row in report["contrasts"]}
        for method in methods[1:]:
            self.assertIn(("official", method), pairs)
        for method in methods[2:]:
            self.assertIn(("edge_count", method), pairs)
        for pair in [("feedback", "adaptive"), ("reachability", "feedback"),
                     ("action_uniform", "action_llm")]:
            self.assertIn(pair, pairs)

    def test_inconsistent_terminal_metrics_and_impossible_counters_are_rejected(self):
        for field, value in [("R", .75), ("valid", 17), ("input_tokens", -1)]:
            source = self.summary()
            source["rows"][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                api().summarize(source)

    def test_cli_exports_inspectable_standard_json(self):
        api()
        with TemporaryDirectory() as temporary:
            folder = Path(temporary)
            source, output = folder / "summary.json", folder / "causal-test.json"
            source.write_text(json.dumps(self.summary()))
            result = subprocess.run([sys.executable, str(ROOT / "experiments/summarize_causal.py"),
                                     "--input", str(source), "--output", str(output)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(output.read_text())
            self.assertEqual(report["counts"]["actual_cells"], 8)
            self.assertEqual(report["split"], "test")


if __name__ == "__main__":
    unittest.main()
