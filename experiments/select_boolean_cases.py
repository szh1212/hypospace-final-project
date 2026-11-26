"""Select the frozen dev/test boolean cases from the official collection.

Cases are drawn deterministically (fixed seeds) and stratified across
observation counts (n_observations 2 and 3, which leave unobserved rows for the
completion strata). No case statistics are used to filter the sample beyond the
bucket membership; the ids are frozen in the protocol before any inference.
"""
import json
import sys
from pathlib import Path
from random import Random

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from boolean_benchmark import COLLECTION, Dataset, MAX_DEPTH, OPERATORS, VARIABLES  # noqa: E402

DEV_BUCKETS = {"2": 2, "3": 2}
TEST_BUCKETS = {"2": 6, "3": 6}
DEV_SEED = 31415
TEST_SEED = 27182


def main():
    collection = json.loads((ROOT / ".cache" / COLLECTION).read_text())
    buckets = collection["datasets_by_n_observations"]
    selected = {"dev": [], "test": []}
    for split, sizes in (("dev", DEV_BUCKETS), ("test", TEST_BUCKETS)):
        rng = Random({"dev": DEV_SEED, "test": TEST_SEED}[split])
        dev_ids = set(selected["dev"])
        for n_obs, size in sizes.items():
            ids = [oid for oid in sorted(row["observation_set_id"] for row in buckets[n_obs])
                   if oid not in dev_ids]
            for oid in rng.sample(ids, size):
                selected[split].append(oid)
    dataset = Dataset(ROOT / ".cache/hypospace", ROOT / ".cache" / COLLECTION)
    print(f"space: variables={list(VARIABLES)} operators={list(OPERATORS)} depth={MAX_DEPTH}")
    for split, ids in selected.items():
        print(f"\n{split}:")
        for oid in ids:
            case = dataset.cases[oid]
            obs = " ".join(f"({v['string']})" for v in case["observations"])
            print(f"  {oid}  n_gt={case['n_compatible_expressions']:3d}  {obs}")
    print("\nJSON:")
    print(json.dumps(selected, indent=2))


if __name__ == "__main__":
    main()
