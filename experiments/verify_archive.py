"""Replay the published baseline requests and scores, then archive exact raw JSON bytes."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from adapted_baseline import transform
from hypospace_runner import digest, upstream
from ollama_client import OllamaClient


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


class VerifiedReplay:
    def __init__(self, records, observation, seed, adapted, config):
        self.records = records
        self.history = []
        self.obs = observation
        self.seed = seed
        self.adapted = adapted
        self.client = OllamaClient(config)

    def query_with_usage(self, prompt):
        index = len(self.history)
        if self.adapted:
            prompt = transform(prompt, {"observation": self.obs, "history": self.history, "query_index": index})
        record = self.records[index]
        request = self.client.request(prompt, (self.seed + index) % 2147483647)
        if request != record["request"] or digest(request) != record["request_sha256"] or prompt != record["prompt"]:
            raise ValueError("Recorded prompt or generation settings differ")
        self.history.append(record["response"])
        return {"response": record["response"], "usage": record["usage"], "cost": 0.0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("export", type=Path)
    args = parser.parse_args()
    metrics = read(args.export / "metrics.json")
    hashes = {r["file"]:r["sha256"] for r in read(args.export / "raw-manifest.json")}
    if len(hashes) != 585 or metrics["completed_calls"] != 585:
        raise ValueError("Formal runs require 585 records")
    archive = args.export / "raw.jsonl.gz"
    benchmark = upstream()[0].Benchmark3D(str(ROOT / "data/3d.json"))
    observations = {o["observation_id"]:o for o in benchmark.all_observation_sets}
    visited = set()
    with TemporaryDirectory(dir=args.export) as tmp:
        path = Path(tmp) / "verified.gz"
        with path.open("wb") as out, gzip.GzipFile(fileobj=out,filename="",mode="wb",mtime=0) as z:
            for row in metrics["results"]:
                oid = row["observation_set_id"]
                seed = row["seed"]
                records = []
                for index in range(row["n_queries"]):
                    name = f"raw/{seed}/{oid}/{index:04d}.json"
                    raw = (args.run / name).read_bytes()
                    if hashlib.sha256(raw).hexdigest() != hashes[name] or name in visited:
                        raise ValueError(f"Raw checksum mismatch: {name}")
                    visited.add(name)
                    records.append(json.loads(raw))
                    z.write((json.dumps({"path":name, "utf8":raw.decode("utf-8")},ensure_ascii=False)+"\n").encode())
                base = seed + int(hashlib.sha256(oid.encode()).hexdigest()[:8],16)
                replay = VerifiedReplay(records, observations[oid]["observation"], base,
                                        metrics["identity"]["method"] == "adapted_baseline:transform",
                                        metrics["identity"]["config"])
                scores = benchmark.evaluate_single_observation_set(replay, observations[oid], n_queries=len(records),
                                                                   verbose=False,max_retries=1)
                for key in ("n_valid","n_unique","n_recovered_gts","valid_rate","novelty_rate","recovery_rate","token_usage"):
                    if scores[key] != row[key] or len(replay.history) != len(records):
                        raise ValueError(f"{seed}/{oid} replay mismatch: {key}")
        if visited != hashes.keys():
            raise ValueError("Raw manifest and task records differ")
        path.replace(archive)
    print(f"Verified {len(visited)} requests and responses: {archive.stat().st_size} compressed bytes")


if __name__ == "__main__":
    main()
