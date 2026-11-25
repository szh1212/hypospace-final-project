"""Offline contracts for the causal adapter and fixed local model transport."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
UPSTREAM = Path(os.environ.get(
    "HYPOSPACE_UPSTREAM",
    ROOT / ".cache/hypospace",
))


def api():
    if importlib.util.find_spec("causal_benchmark") is None:
        raise AssertionError("Standalone causal benchmark adapter is not implemented")
    import causal_benchmark
    return causal_benchmark


class DatasetTests(unittest.TestCase):
    def dataset(self):
        if not UPSTREAM.is_dir():
            self.skipTest("Set HYPOSPACE_UPSTREAM to the cached official checkout")
        if not hasattr(type(self), "_dataset"):
            type(self)._dataset = api().Dataset(UPSTREAM)
        return type(self)._dataset

    def test_generation_retains_all_observation_counts_and_reference_sets(self):
        dataset = self.dataset()
        self.assertEqual(len(dataset.cases), 236)
        self.assertEqual(sum(row["n_observations"] == 1 for row in dataset.cases.values()), 32)
        self.assertEqual(sum(row["n_observations"] == 2 for row in dataset.cases.values()), 204)
        for key, row in dataset.cases.items():
            self.assertEqual(row["observation_set_id"], key)
            self.assertEqual(row["nodes"], ["A", "B", "C", "D"])
            self.assertEqual(row["max_edges"], 4)
            self.assertEqual(row["n_compatible_graphs"], len(row["ground_truth_graphs"]))
        self.assertTrue(dataset.provenance["sources"])

    def test_replay_counts_invalid_duplicate_and_unparseable_attempts(self):
        fixture = {
            "observation_set_id": "fixture", "nodes": ["A", "B", "C"], "max_edges": 2,
            "observations": [{"perturbed_node": "A", "effects": {"A": 0, "B": 1, "C": 1},
                              "string": "Perturb(A) -> A:0 B:1 C:1"}],
            "ground_truth_graphs": [
                {"nodes": ["A", "B", "C"], "edges": edges}
                for edges in [[("A", "B"), ("B", "C")],
                              [("A", "C"), ("C", "B")],
                              [("A", "B"), ("A", "C")]]
            ],
        }
        result = self.dataset().score(fixture, [
            "Graph: A->B, B->C", "Graph: A->B, B->C", "unparseable", "Graph: B->A",
        ])
        self.assertEqual(result["n_queries"], 4)
        self.assertEqual(result["parse_success_count"], 3)
        self.assertEqual(result["valid_rate"], .5)
        self.assertEqual(result["novelty_rate"], .5)
        self.assertEqual(result["recovery_rate"], 1 / 3)

    def test_public_benchmark_enforces_descendant_semantics_and_dag_constraint(self):
        bench = self.dataset().bench
        observation = [{"perturbed_node": "A", "effects": {"A": 0, "B": 1, "C": 1, "D": 0}}]
        self.assertTrue(bench.validate_hypothesis(bench.parse_llm_response("Graph: A->B, B->C"), observation))
        self.assertFalse(bench.validate_hypothesis(bench.parse_llm_response("Graph: A->B"), observation))
        self.assertIsNone(bench.parse_llm_response("Graph: A->B, B->A"))

    def test_wrong_official_revision_is_rejected_before_import(self):
        with patch("subprocess.check_output", return_value="bad-revision\n"):
            with self.assertRaisesRegex(ValueError, "revision"):
                api().Dataset(UPSTREAM)


class FakeResponse:
    def __init__(self, body, status=200):
        self.status = status
        self.body = json.dumps(body).encode()

    def read(self):
        return self.body


class FakeConnection:
    """Substitute only the network boundary; inspect real serialized requests."""
    responses = {}
    requests = []

    def __init__(self, host, port, timeout):
        if (host, port) != ("127.0.0.1", 11434):
            raise AssertionError("Transport escaped the fixed local endpoint")

    def request(self, method, path, body=None, headers=None):
        self.key = method, path
        self.requests.append((method, path, json.loads(body) if body else None))

    def getresponse(self):
        response = self.responses[self.key]
        return FakeResponse(response) if not isinstance(response, FakeResponse) else response

    def close(self):
        pass


class LocalModelTests(unittest.TestCase):
    def setUp(self):
        FakeConnection.requests = []
        FakeConnection.responses = {
            ("GET", "/api/version"): {"version": "0.40.18"},
            ("GET", "/api/tags"): {"models": [{
                "name": "qwen2.5:3b-instruct-q4_K_M",
                "digest": "357c53fb659c5076de1d65ccb0b397446227b71a42be9d1603d46168015c9e4b",
            }]},
            ("POST", "/api/show"): {"details": {"quantization_level": "Q4_K_M"}, "template": "fixture"},
            ("POST", "/api/chat"): {
                "model": "qwen2.5:3b-instruct-q4_K_M", "done": True,
                "done_reason": "stop", "message": {"role": "assistant", "content": "Graph: A->B"},
                "prompt_eval_count": 20, "eval_count": 6, "total_duration": 500000000,
                "load_duration": 1, "prompt_eval_duration": 2, "eval_duration": 3,
            },
        }
        self.network = patch("http.client.HTTPConnection", FakeConnection)
        self.network.start()
        self.addCleanup(self.network.stop)

    def test_generation_locks_model_and_records_exact_sampling_and_usage(self):
        model = api().LocalModel()
        result = model.generate("Return one DAG.", 123)
        self.assertEqual(result["response"], "Graph: A->B")
        self.assertEqual((result["input_tokens"], result["output_tokens"]), (20, 6))
        self.assertEqual(result["done_reason"], "stop")
        self.assertGreaterEqual(result["seconds"], 0)
        sent = next(body for method, path, body in FakeConnection.requests if path == "/api/chat")
        self.assertEqual(sent["options"], {
            "seed": 123, "temperature": .7, "top_p": .9, "top_k": 40,
            "repeat_penalty": 1.0, "num_predict": 256, "num_ctx": 8192,
            "num_thread": 4, "num_gpu": 99,
        })
        self.assertEqual(sent["messages"][1], {"role": "user", "content": "Return one DAG."})
        self.assertEqual(result["request"], sent)
        self.assertEqual(model.fingerprint()["quantization"], "Q4_K_M")

    def test_fingerprint_rejects_wrong_version_digest_and_quantization(self):
        mutations = [
            (("GET", "/api/version"), {"version": "different"}),
            (("GET", "/api/tags"), {"models": [{"name": "qwen2.5:3b-instruct-q4_K_M", "digest": "wrong"}]}),
            (("POST", "/api/show"), {"details": {"quantization_level": "Q8_0"}, "template": "fixture"}),
        ]
        for route, bad_response in mutations:
            original = FakeConnection.responses[route]
            FakeConnection.responses[route] = bad_response
            with self.subTest(route=route), self.assertRaises(ValueError):
                api().LocalModel().fingerprint()
            FakeConnection.responses[route] = original
        self.assertFalse(any(path == "/api/chat" for _, path, _ in FakeConnection.requests))

    def test_failed_http_and_incomplete_generations_abort_without_retries(self):
        for response in [FakeResponse({}, status=302), FakeResponse({}, status=500), {"done": False}]:
            FakeConnection.responses[("POST", "/api/chat")] = response
            FakeConnection.requests = []
            with self.subTest(response=response), self.assertRaises(RuntimeError):
                api().LocalModel().generate("Return one DAG.", 1)
            self.assertEqual(sum(path == "/api/chat" for _, path, _ in FakeConnection.requests), 1)


if __name__ == "__main__":
    unittest.main()
