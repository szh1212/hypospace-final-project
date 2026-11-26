"""Regenerate the pre-inference split using only public interventions and prior case IDs."""
import hashlib
import itertools
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from causal_benchmark import Dataset

SALT = "parent-strata-v1"


def signature(nodes, observations):
    """Canonical intervention sources and reachable sets over all node renamings."""
    encodings = []
    for order in itertools.permutations(nodes):
        patterns = []
        for obs in observations:
            root = order.index(obs["perturbed_node"])
            reachable = "".join(str(i) for i, n in enumerate(order) if obs["effects"][n])
            patterns.append(f"{root}>{reachable}")
        encodings.append(",".join(sorted(patterns)))
    return min(encodings)


def rank(value):
    return hashlib.sha256(f"{SALT}/{value}".encode()).hexdigest()


def main():
    previous = json.loads((ROOT / "experiments/causal-main.json").read_text())
    excluded = set(previous["dev"] + previous["test"] + previous["excluded_old_ids"])
    data = Dataset(ROOT / ".cache/hypospace")
    groups = defaultdict(list)
    seen = set()
    for oid, row in data.cases.items():
        pattern = signature(row["nodes"], row["observations"])
        if oid in excluded:
            seen.add(pattern)
        else:
            groups[pattern].append(oid)
    dev = set()
    for n_obs, quota in [(1, 1), (2, 3)]:
        pool = [p for p in seen if p.count(",") + 1 == n_obs]
        dev.update(sorted(pool, key=rank)[:quota])
    assignment = {
        min(ids, key=rank): {
            "signature": p, "seen_in_previous_study": p in seen,
            "n_observations": p.count(",") + 1, "split": "dev" if p in dev else "test",
        } for p, ids in groups.items()
    }
    config = {
        "dev": sorted(oid for oid, info in assignment.items() if info["split"] == "dev"),
        "test": sorted(oid for oid, info in assignment.items() if info["split"] == "test"),
        "dev_seeds": [17], "test_seeds": [17, 42], "budget": 16,
        "methods": ["official", "unstratified", "edge_count", "parent_set"],
        "primary_metric": "Macro mean official recovery@16 over cases after averaging seeds.",
        "primary_control": "edge_count", "secondary_controls": ["unstratified", "official"],
        "split_rule": (
            "Group public intervention reachability patterns under every node permutation. "
            "Exclude all prior IDs. Assign one previously seen single-intervention type and three "
            "previously seen double-intervention types to development by increasing salted SHA-256. "
            "Assign every other type to test. Within each type choose the unused case ID with "
            "lowest salted SHA-256. Each test type gets equal weight, irrespective of case frequency."
        ),
        "hash_salt": SALT, "excluded_ids": sorted(excluded), "case_types": dict(sorted(assignment.items())),
    }
    print(json.dumps(config, indent=2))


if __name__ == "__main__":
    main()
