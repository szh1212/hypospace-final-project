"""Standalone pinned boolean (gene-interaction) data and official replay.

The upstream HypoSpace boolean module (variables x = mother, y = father) is
loaded once with the same shim technique as the causal module. Scoring always
replays the official evaluator on parsed output strings, so V/U/R keep the
official semantics. The loopback-only Ollama transport is shared with the
causal module (same local model, sampling and identity checks).
"""
import contextlib
import hashlib
import importlib.util
import io
import json
import subprocess
import sys
import types
from pathlib import Path

from causal_benchmark import (LocalModel, MODEL, MODEL_DIGEST, OLLAMA_VERSION,
                              SAMPLING, SYSTEM)  # noqa: F401  (re-exported transport)

PIN = "c69e9318577b34b5b896996571aefd4ba6053f58"
VARIABLES = ("x", "y")
OPERATORS = ("AND", "OR", "NOT", "NOR")
MAX_DEPTH = 2
MECH_OPTS = dict(apply_commutativity=True, apply_idempotence_and_or=True,
                 flatten_associativity=True)
COLLECTION = "boolean-datasets-full-d2-s2026.json"


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
    """Resolve the upstream boolean module's absolute local imports in isolation."""
    folder = upstream / "boolean"
    prefix = "_boolean_official_" + hashlib.sha256(str(upstream).encode()).hexdigest()[:16]
    _package(prefix, folder)
    names = ("modules", "modules.models", "modules.llm_interface", "boolean_dataset")
    missing = object()
    previous = {name: sys.modules.get(name, missing) for name in names}
    try:
        sys.modules["modules"] = _package(prefix + ".modules", folder / "modules")
        sys.modules["modules.models"] = _load(prefix + ".modules.models",
                                              folder / "modules" / "models.py")
        sys.modules["modules.llm_interface"] = _load(prefix + ".modules.llm_interface",
                                                     folder / "modules" / "llm_interface.py")
        dataset_module = _load(prefix + ".boolean_dataset", folder / "boolean_dataset.py")
        sys.modules["boolean_dataset"] = dataset_module
        evaluator = _load(prefix + ".boolean_benchmark", folder / "boolean_benchmark.py")
    finally:
        for name, module in previous.items():
            if module is missing:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module
    return evaluator, dataset_module


_official_cache = {}


def load_official(upstream):
    """Load (benchmark_module, dataset_module) once per resolved upstream path."""
    key = str(Path(upstream).resolve())
    if key not in _official_cache:
        _official_cache[key] = _official(Path(upstream))
    return _official_cache[key]


class Dataset:
    """All official boolean observation sets; ground truths are for scoring only."""

    def __init__(self, upstream: Path, collection: Path = None):
        upstream = Path(upstream).resolve()
        self._upstream = upstream
        revision = subprocess.check_output(["git", "-C", str(upstream), "rev-parse", "HEAD"],
                                           text=True).strip()
        if revision != PIN:
            raise ValueError("Official upstream revision does not match the fixed pin")
        dirty = subprocess.check_output([
            "git", "-C", str(upstream), "status", "--porcelain", "--untracked-files=all",
            "--", "boolean",
        ], text=True)
        if any(line.endswith(".py") or ".py -> " in line for line in dirty.splitlines()):
            raise ValueError("Official boolean source tree must be clean")
        self.provenance = {
            "upstream_commit": revision,
            "sources": {str(path.relative_to(upstream)): hashlib.sha256(path.read_bytes()).hexdigest()
                        for path in sorted((upstream / "boolean").rglob("*.py"))},
        }
        evaluator, _ = load_official(upstream)
        self._benchmark_class = evaluator.BooleanBenchmarkRefined
        self.collection_path = Path(collection) if collection else (
            Path(__file__).resolve().parents[1] / ".cache" / COLLECTION)
        with contextlib.redirect_stdout(io.StringIO()):
            self.bench = self._benchmark_class(str(self.collection_path))
        self.cases = {}
        for rows in self.bench.complete_dataset["datasets_by_n_observations"].values():
            for row in rows:
                self.cases[row["observation_set_id"]] = row

    def score(self, case, outputs):
        """Replay raw outputs through the official evaluator (no retries, no filtering)."""
        responses = list(outputs)

        class Replay:
            def __init__(self):
                self.responses = iter(responses)

            def query_with_usage(self, prompt):
                return {"response": next(self.responses),
                        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}}

        return self.bench.evaluate_single_observation_set(
            Replay(), case, n_queries=len(responses), verbose=False, max_retries=1)
