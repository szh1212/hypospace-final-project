"""Offline audit: replay every raw call of a run and re-verify everything.

For each (seed, case, query) record the audit recomputes
  1. the exact prompt sent (deterministic from obs, query index, priors),
  2. the request digest,
  3. the filtered response from the raw response (method gens),
  4. the official V/U/R metrics and per-k curves from the stored responses,
and compares all of them with the stored records / summary. Also replays the
SZH baseline run directory when given its layout (records store the prompt and
the response verbatim; metrics are re-checked with the official evaluator).
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from ollama_client import OllamaClient
from hypospace_runner_3d import (build_method_prompt, canonicalize, Replay, S,
                                 digest, upstream)


def audit_run(run_dir, bench, off, dataset):
    summary = json.loads((Path(run_dir) / 'summary.json').read_text(encoding='utf-8'))
    ident = summary['identity']
    cfg = ident['config']
    gen = ident['gen']
    mode = ident['mode']
    checks = 0
    failures = []
    obs_by_id = {x['observation_id']: x for x in dataset['observation_sets']}

    for r in summary['results']:
        oid, seed = r['observation_set_id'], r['seed']
        obs = obs_by_id[oid]['observation']
        n = r['n_queries']
        folder = Path(run_dir) / 'raw' / str(seed) / oid
        records = [json.loads((folder / f'{q:04d}.json').read_text(encoding='utf-8'))
                   for q in range(n)]
        # recompute prompts/filters
        prior_seen = set()
        unique_structures = []  # official-mode evaluator state
        client = OllamaClient(cfg) if mode == 'llm' else None
        for q, rec in enumerate(records):
            if gen == 'official':
                # The official evaluator passes the live unique_structures list
                # (its internal [-10:] trim never reaches create_prompt).
                built = bench.create_prompt(obs, prior_structures=unique_structures)
                meta = {}
            else:
                priors = []
                seen = set()
                for prev in records[:q]:
                    struct = canonicalize(off, obs, prev['response'])
                    if struct is None:
                        continue
                    key = struct.get_hash()
                    if key in seen:
                        continue
                    seen.add(key)
                    s2, s3 = hypospace_sets(obs, struct)
                    priors.append(S.canonical_structure(obs, s2, s3))
                built, meta = build_method_prompt(gen, obs, q, n, priors)
            checks += 1
            if rec['prompt'] != built:
                failures.append(f'{oid}/{seed}/q{q}: prompt mismatch')
            if rec.get('meta') != meta:
                failures.append(f'{oid}/{seed}/q{q}: meta mismatch {rec.get("meta")} != {meta}')
            seed_q = seed + int(hashlib.sha256(oid.encode()).hexdigest()[:8], 16)
            request = client.request(built, (seed_q + q) % 2147483647) if client else \
                {'prompt': built, 'model': cfg['model']}
            checks += 1
            if digest(request) != rec['request_sha256']:
                failures.append(f'{oid}/{seed}/q{q}: request sha mismatch')
            if gen not in ('official', 'verbal'):
                occ = S.occupied_cells(obs)
                struct = canonicalize(off, obs, rec['raw_response'])
                layers = None if struct is None else struct.layers
                if gen == 'free':
                    s2, s3 = S.repair_free(occ, layers)
                elif gen == 'k2':
                    s2, s3 = S.repair_k2(occ, layers, meta['k2'])
                else:
                    anchor = None
                    if meta.get('anchor'):
                        idx, in_s2, s3_branch = meta['anchor']
                        anchor = (occ[idx], bool(in_s2), s3_branch)
                    s2, s3 = S.repair(occ, layers, meta['k2'], meta['k3'], anchor)
                filtered = S.canonical_structure(obs, s2, s3)
                checks += 1
                if filtered != rec['response']:
                    failures.append(f'{oid}/{seed}/q{q}: filter mismatch')
            struct = canonicalize(off, obs, rec['response'])
            if struct is not None:
                h = struct.get_hash()
                if h not in prior_seen:
                    prior_seen.add(h)
                    unique_structures.append(struct)

        # recompute metrics from stored responses with the official evaluator
        for k in (n,):
            v = bench.evaluate_single_observation_set(Replay(records), obs_by_id[oid],
                                                      n_queries=k, verbose=False, max_retries=1)
            for m in ['valid_rate', 'novelty_rate', 'recovery_rate']:
                checks += 1
                if abs(v[m] - r[m]) > 1e-9:
                    failures.append(f'{oid}/{seed}: metric {m} mismatch {v[m]} != {r[m]}')
        cmap = {c['k']: c for c in summary['curves'] if c['observation_id'] == oid and c['seed'] == seed}
        for k in range(1, n + 1):
            v = bench.evaluate_single_observation_set(Replay(records[:k]), obs_by_id[oid],
                                                      n_queries=k, verbose=False, max_retries=1)
            for m in ['valid_rate', 'novelty_rate', 'recovery_rate']:
                checks += 1
                if abs(v[m] - cmap[k][m]) > 1e-9:
                    failures.append(f'{oid}/{seed}/k{k}: curve {m} mismatch')
    return checks, failures


def hypospace_sets(obs, struct):
    occ = S.occupied_cells(obs)
    s2 = set()
    s3 = set()
    if len(struct.layers) >= 2:
        for rr, row in enumerate(struct.layers[1]):
            for cc, v in enumerate(row):
                if v:
                    s2.add((rr, cc))
    if len(struct.layers) >= 3:
        for rr, row in enumerate(struct.layers[2]):
            for cc, v in enumerate(row):
                if v:
                    s3.add((rr, cc))
    s2 &= set(occ)
    s3 &= s2
    return s2, s3


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('run_dirs', nargs='+')
    args = ap.parse_args()
    off, _ = upstream()
    bench = off.Benchmark3D(str(ROOT / 'data' / '3d.json'))
    dataset = json.loads((ROOT / 'data' / '3d.json').read_text(encoding='utf-8'))
    total_checks = 0
    all_failures = []
    for d in args.run_dirs:
        checks, failures = audit_run(d, bench, off, dataset)
        total_checks += checks
        all_failures += failures
        print(f'{d}: {checks} checks, {len(failures)} failures')
        for f in failures[:10]:
            print('  ', f)
        if len(failures) > 10:
            print(f'   ... {len(failures) - 10} more')
    print(f'TOTAL: {total_checks} checks, {len(all_failures)} failures')
    sys.exit(1 if all_failures else 0)


if __name__ == '__main__':
    main()
