"""Standalone pinned causal data, official replay, and loopback-only Ollama transport."""
import contextlib
import hashlib
import http.client
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import time
import types

PIN = "c69e9318577b34b5b896996571aefd4ba6053f58"
NODES = ("A", "B", "C", "D")
MAX_EDGES = 4
MODEL = "qwen2.5:3b-instruct-q4_K_M"
MODEL_DIGEST = "357c53fb659c5076de1d65ccb0b397446227b71a42be9d1603d46168015c9e4b"
OLLAMA_VERSION = "0.40.18"
SYSTEM = "You are Qwen, created by Alibaba Cloud. You are a helpful assistant."
SAMPLING = {
    "temperature": .7, "top_p": .9, "top_k": 40, "repeat_penalty": 1.0,
    "num_predict": 256, "num_ctx": 8192, "num_thread": 4, "num_gpu": 99,
}


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _package(name, directory):
    module = types.ModuleType(name)
    module.__path__ = [str(directory)]
    module.__package__ = name
    sys.modules[name] = module
    return module


def _official(upstream):
    """Resolve upstream's absolute local imports without importing another project."""
    folder = upstream / "causal"
    prefix = "_causal_official_" + hashlib.sha256(str(upstream).encode()).hexdigest()[:16]
    _package(prefix, folder)
    names = ("modules", "modules.models", "modules.llm_interface", "generate_causal_dataset")
    missing = object()
    previous = {name: sys.modules.get(name, missing) for name in names}
    try:
        sys.modules["modules"] = _package(prefix + ".modules", folder / "modules")
        for name in ("models", "llm_interface"):
            sys.modules["modules." + name] = _load(prefix + ".modules." + name, folder / "modules" / (name + ".py"))
        generator = _load(prefix + ".generate_causal_dataset", folder / "generate_causal_dataset.py")
        sys.modules["generate_causal_dataset"] = generator
        evaluator = _load(prefix + ".run_causal_benchmark", folder / "run_causal_benchmark.py")
    finally:
        for name, module in previous.items():
            if module is missing:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module
    return evaluator, generator


class Dataset:
    """Exhaustive four-node cases; reference solutions are for scoring only."""
    def __init__(self, upstream: Path):
        upstream = Path(upstream).resolve()
        revision = subprocess.check_output(["git", "-C", str(upstream), "rev-parse", "HEAD"], text=True).strip()
        if revision != PIN:
            raise ValueError("Official upstream revision does not match the fixed pin")
        dirty = subprocess.check_output([
            "git", "-C", str(upstream), "status", "--porcelain", "--untracked-files=all", "--", "causal",
        ], text=True)
        if any(line.endswith(".py") or ".py -> " in line for line in dirty.splitlines()):
            raise ValueError("Official causal source tree must be clean")
        self.provenance = {
            "upstream_commit": revision,
            "sources": {str(path.relative_to(upstream)): hashlib.sha256(path.read_bytes()).hexdigest()
                        for path in sorted((upstream / "causal").rglob("*.py"))},
        }
        evaluator, generator = _official(upstream)
        self._benchmark_class = evaluator.CausalBenchmarkEnhanced
        self.bench = self._benchmark(list(NODES), MAX_EDGES)
        with contextlib.redirect_stdout(io.StringIO()):
            rows = [row for count in (1, 2)
                    for row in generator.CausalDatasetGenerator.generate_all_observation_combinations(
                        list(NODES), count, max_edges=MAX_EDGES)]
        self.cases = {row["observation_set_id"]: row for row in rows}
        if len(self.cases) != len(rows):
            raise ValueError("Official generator produced duplicate case identifiers")

    def _benchmark(self, nodes, max_edges):
        bench = object.__new__(self._benchmark_class)
        bench.nodes, bench.max_edges = list(nodes), max_edges
        return bench

    def score(self, case, outputs):
        """Replay every raw attempt, with no parse retries or candidate filtering."""
        responses = list(outputs)

        class Replay:
            def __init__(self):
                self.responses = iter(responses)

            def query_with_usage(self, prompt):
                return {"response": next(self.responses)}

        bench = self._benchmark(case["nodes"], case["max_edges"])
        return bench.evaluate_single_observation_set(
            Replay(), case, n_queries=len(responses), verbose=False, max_retries=1,
        )


class LocalModel:
    """Fixed unauthenticated loopback HTTP; no proxies, redirects, retries or fallback."""
    def __init__(self):
        self._identity = None

    def _json(self, method, path, payload=None, timeout=600):
        connection = http.client.HTTPConnection("127.0.0.1", 11434, timeout=timeout)
        try:
            connection.request(method, path, body=json.dumps(payload) if payload is not None else None,
                               headers={"Content-Type": "application/json"})
            response = connection.getresponse()
            body = response.read()
            if response.status != 200:
                raise RuntimeError(f"Local Ollama returned HTTP {response.status}")
            result = json.loads(body)
            if not isinstance(result, dict):
                raise RuntimeError("Malformed local Ollama JSON response")
            return result
        finally:
            connection.close()

    def fingerprint(self):
        version = self._json("GET", "/api/version", timeout=30)
        tags = self._json("GET", "/api/tags", timeout=30)
        model = next((row for row in tags["models"] if row["name"] == MODEL), None)
        if version["version"] != OLLAMA_VERSION:
            raise ValueError("Local Ollama version mismatch")
        if model is None or model["digest"] != MODEL_DIGEST:
            raise ValueError("Local Qwen model digest mismatch")
        show = self._json("POST", "/api/show", {"model": MODEL}, timeout=30)
        if show["details"]["quantization_level"] != "Q4_K_M":
            raise ValueError("Local model quantization mismatch")
        self._identity = {
            "model": MODEL, "digest": MODEL_DIGEST, "quantization": "Q4_K_M",
            "ollama_version": OLLAMA_VERSION, "details": show["details"],
            "template_sha256": hashlib.sha256(show["template"].encode()).hexdigest(),
        }
        return dict(self._identity)

    def generate(self, prompt, seed):
        if self._identity is None:
            self.fingerprint()
        request = {
            "model": MODEL,
            "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}],
            "stream": False, "keep_alive": "30m", "options": {**SAMPLING, "seed": seed},
        }
        start = time.perf_counter()
        body = self._json("POST", "/api/chat", request)
        seconds = time.perf_counter() - start
        if body.get("done") is not True:
            raise RuntimeError("Incomplete local model response")
        if body.get("model") != MODEL:
            raise RuntimeError("Local model response resolved to an unexpected model")
        response = body.get("message", {}).get("content")
        counts = [body.get(key) for key in ("prompt_eval_count", "eval_count")]
        if not isinstance(response, str) or any(type(n) is not int or n < 0 for n in counts):
            raise RuntimeError("Local response is missing text or token accounting")
        return {
            "response": response, "input_tokens": counts[0], "output_tokens": counts[1],
            "seconds": seconds, "done_reason": body.get("done_reason"),
            "request": request, "resolved_model": body["model"],
            "timing_ns": {key: body.get(key, 0) for key in
                          ("total_duration", "load_duration", "prompt_eval_duration", "eval_duration")},
        }
