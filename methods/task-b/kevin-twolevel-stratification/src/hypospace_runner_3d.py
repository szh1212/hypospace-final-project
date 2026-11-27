"""Runner for the 3D voxel method: pinned official evaluator + auditable transport.

Adapted from the SZH baseline branch's src/hypospace_runner.py (same dataset
preparation, same seed formula, same evaluation path, same summary schema) so the
experimental conditions match the baseline run. What differs is the method:

  --gen official : official benchmark prompt, raw responses (官方提示 baseline)
  --gen verbal   : generation 1 - verbal (k2,k3) stratification, no system filter
  --gen free     : generation 2 - no stratification + validity repair (骨架强制)
  --gen k2       : generation 3 - k2-only stratification + repair
  --gen joint    : generation 4 (final) - two-level (k2,k3)+anchor stratification
                   + validity repair + reading-order-minimal fallback

Every raw call is stored; every filtered response is recomputable from the raw
response (see experiments/audit_3d.py).
"""
import argparse, hashlib, importlib, json, os, platform, random, subprocess, sys, time
from pathlib import Path
from ollama_client import OllamaClient
import strata_3d as S
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
# Locate the pinned benchmark checkout: walk up from the method directory until a
# `.cache/hypospace` checkout is found (works at any depth of the methods/ layout).
_candidate = ROOT
UP = None
for _ in range(8):
    probe = _candidate / '.cache' / 'hypospace'
    if probe.exists():
        UP = probe
        break
    _candidate = _candidate.parent
if UP is None:
    UP = ROOT / '.cache' / 'hypospace'
PIN = 'c69e9318577b34b5b896996571aefd4ba6053f58'
DATASET_SHA = '61cebef122826c7b3d92b7fb520f956e096bc7c28025d98668384ad582a9e06e'


class TransportAbort(BaseException):
    pass


def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding='utf-8')


def upstream():
    revision = subprocess.check_output(['git', '-c', f'safe.directory={UP.as_posix()}', '-C', str(UP),
                                        'rev-parse', 'HEAD'], text=True).strip()
    if revision != PIN:
        raise ValueError('Wrong upstream revision')
    sys.path.insert(0, str(UP / '3d'))
    official = importlib.import_module('run_3d_benchmark')
    if not getattr(official.Structure3D, '_zero_array_fix', False):
        original = official.Structure3D.normalize

        def normalize(self):
            if self.layers and all(not np.any(layer) for layer in self.layers):
                return official.Structure3D([(self.layers[0] * 0).tolist()])
            return original(self)

        official.Structure3D.normalize = normalize
        official.Structure3D._zero_array_fix = True
    return official, importlib.import_module('generate_3d_dataset_complete')


def prepare(cfg):
    official, gen = upstream()
    g = gen.Dataset3DGenerator(grid_size=cfg['grid_size'], max_blocks=max(cfg['blocks']),
                               max_height=cfg['max_height'])
    g.generate_all_top_views(); g.generate_all_structures(); g.generate_observation_sets()
    ds = {'metadata': {'grid_size': cfg['grid_size'], 'max_height': cfg['max_height']},
          'observation_sets': g.observation_sets}
    save(ROOT / 'data' / '3d.json', ds)
    assert digest(ds) == DATASET_SHA, 'Regenerated dataset differs from the frozen baseline dataset'
    manifest = {'dataset_sha256': DATASET_SHA, 'splits': cfg['splits']}
    save(ROOT / 'experiments' / 'manifest-3d.json', manifest)
    print('Prepared', len(g.observation_sets), 'observations; sha256 OK')
    return official


def canonicalize(official, obs, text):
    """Parse raw text with the official parser; return the normalized Structure3D or None."""
    parser = object.__new__(official.Benchmark3D)  # parse_llm_response uses no instance state
    struct = parser.parse_llm_response(text)
    if struct is None:
        return None
    return struct.normalize()


class RecordedClient:
    """One observation set: builds prompts, calls the model, applies the method
    filter, and hands the (possibly repaired) response to the official evaluator."""

    def __init__(self, cfg, mode, folder, obs, oid, seed, gen, official):
        self.cfg, self.mode, self.folder, self.obs, self.oid = cfg, mode, folder, obs, oid
        self.seed = seed
        self.gen = gen
        self.official = official
        self.records = []
        self.local = OllamaClient(cfg) if mode == 'llm' else None
        self.prior_parsed = []   # canonical deduped prior strings (gens 2-4)
        self.prior_seen = set()

    def _prior_canonicals(self):
        out = []
        seen = set()
        for r in self.records:
            struct = canonicalize(self.official, self.obs['observation'], r['response'])
            if struct is None:
                continue
            key = struct.get_hash()
            if key in seen:
                continue
            seen.add(key)
            s2, s3 = layers_to_sets(self.obs['observation'], struct)
            out.append(S.canonical_structure(self.obs['observation'], s2, s3))
        return out

    def _filter(self, raw):
        obs = self.obs['observation']
        occ = S.occupied_cells(obs)
        struct = canonicalize(self.official, obs, raw)
        if self.gen == 'free':
            s2, s3 = S.repair_free(occ, None if struct is None else struct.layers)
        elif self.gen == 'k2':
            s2, s3 = S.repair_k2(occ, None if struct is None else struct.layers, self._stratum[0])
        else:
            k2, k3 = self._stratum
            anchor = None
            if self._anchor:
                idx, in_s2, s3_branch = self._anchor
                anchor = (occ[idx], bool(in_s2), s3_branch)
            s2, s3 = S.repair(occ, None if struct is None else struct.layers, k2, k3, anchor)
        return S.canonical_structure(obs, s2, s3)

    def query_with_usage(self, prompt):
        q = len(self.records)
        obs = self.obs['observation']
        b = S.n_blocks(obs)
        use_raw = self.gen in ('official', 'verbal')
        if self.gen == 'official':
            built, meta = prompt, {}
        else:
            built, meta = build_method_prompt(self.gen, obs, q, self._n_queries, self._prior_canonicals())
        self._stratum = (meta.get('k2'), meta.get('k3'))
        self._anchor = meta.get('anchor')

        request = self.local.request(built, (self.seed + q) % 2147483647) if self.local else \
            {'prompt': built, 'model': self.cfg['model']}
        path = self.folder / f'{q:04d}.json'
        key = digest(request)
        if path.exists():
            record = json.loads(path.read_text(encoding='utf-8'))
            if record['request_sha256'] != key:
                raise RuntimeError('Cache prompt mismatch; use a new output directory')
        else:
            start = time.perf_counter()
            if self.mode == 'offline':
                rng = random.Random(self.seed)
                for _ in range(q * b):
                    rng.randint(1, self.cfg['max_height'])
                heights = [rng.randint(1, self.cfg['max_height']) if c == '1' else 0 for c in obs]
                rows = []
                for z in range(max(heights)):
                    rows.append(f'Layer {z + 1}:')
                    rows.extend(' '.join(str(int(h > z)) for h in heights[i:i + 3]) for i in range(0, 9, 3))
                raw = 'Structure:\n' + '\n'.join(rows)
                usage = {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0}
                resolved_model = 'uniform-height-control'
                extra = {}
            else:
                try:
                    generated = self.local.generate(request)
                except Exception as exc:
                    raise TransportAbort(f'Local model call failed ({type(exc).__name__}); resume saved run after fixing the service.') from None
                raw = generated['response']
                usage = generated['usage']
                resolved_model = generated['resolved_model']
                extra = {k: generated[k] for k in ['elapsed_s', 'done_reason', 'timing_ns'] if k in generated}
            filtered = raw if use_raw else self._filter(raw)
            record = {'request_sha256': key, 'request': request, 'prompt': built, 'raw_response': raw,
                      'response': filtered, 'meta': meta, 'usage': usage, 'resolved_model': resolved_model,
                      'elapsed_s': time.perf_counter() - start, **extra}
            save(path, record)
        self.records.append(record)
        return {'response': record['response'], 'usage': record['usage'], 'cost': 0.0}


def layers_to_sets(obs, struct):
    occ = S.occupied_cells(obs)
    s2 = set()
    s3 = set()
    if len(struct.layers) >= 2:
        for r, row in enumerate(struct.layers[1]):
            for c, v in enumerate(row):
                if v:
                    s2.add((r, c))
    if len(struct.layers) >= 3:
        for r, row in enumerate(struct.layers[2]):
            for c, v in enumerate(row):
                if v:
                    s3.add((r, c))
    s2 &= set(occ)
    s3 &= s2
    return s2, s3


def build_method_prompt(gen, obs, q, n_queries, prior_canonicals):
    """Deterministic prompt for query q; returns (prompt, meta)."""
    b = S.n_blocks(obs)
    meta = {}
    if gen == 'verbal':
        alloc = S.allocation(b, n_queries)
        meta = {'k2': alloc[q][0], 'k3': alloc[q][1], 'anchor': None}
        return S.build_prompt_verbal(obs, alloc[q][0], alloc[q][1], prior_canonicals), meta
    if gen == 'free':
        meta = {'k2': None, 'k3': None, 'anchor': None}
        return S.build_prompt_free(obs, prior_canonicals), meta
    if gen == 'k2':
        alloc = S.single_level_allocation(b, n_queries)
        meta = {'k2': alloc[q], 'k3': None, 'anchor': None}
        return S.build_prompt_k2(obs, alloc[q], prior_canonicals), meta
    alloc = S.allocation(b, n_queries)
    k2, k3 = alloc[q]
    rank = sum(1 for i in range(q) if alloc[i] == (k2, k3))
    anchor = S.anchor_for(b, k2, k3, rank)
    meta = {'k2': k2, 'k3': k3, 'anchor': list(anchor) if anchor else None}
    return S.build_prompt(obs, k2, k3, anchor, prior_canonicals), meta


class Replay:
    def __init__(self, records):
        self.it = iter(records)

    def query_with_usage(self, prompt):
        return next(self.it)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--prepare', action='store_true')
    p.add_argument('--config', default='experiments/protocol-3d.json')
    p.add_argument('--gen', choices=['official', 'verbal', 'free', 'k2', 'joint'], default='joint')
    p.add_argument('--mode', choices=['offline', 'llm'], default='llm')
    p.add_argument('--split', choices=['dev', 'test', 'dev-smoke'], default='dev-smoke')
    p.add_argument('--out', default='runs/joint-dev-smoke')
    args = p.parse_args()
    cfg = json.loads((ROOT / args.config).read_text(encoding='utf-8'))
    if args.prepare:
        prepare(cfg)
        return
    off, _ = upstream()
    manifest = json.loads((ROOT / 'experiments' / 'manifest-3d.json').read_text(encoding='utf-8'))
    ds = json.loads((ROOT / 'data' / '3d.json').read_text(encoding='utf-8'))
    assert digest(ds) == manifest['dataset_sha256']
    fingerprint = OllamaClient(cfg).fingerprint() if args.mode == 'llm' else None
    if args.mode == 'offline':
        cfg['model'] = 'uniform-height-control'
    chosen = [x for x in ds['observation_sets'] if x['observation_id'] in manifest['splits'][args.split if args.split != 'dev-smoke' else 'dev']]
    if args.split == 'dev-smoke':
        chosen = [next(x for x in chosen if f'_b{b}_' in x['observation_id']) for b in cfg['blocks']]
        cfg['repeat_seeds'] = [cfg['repeat_seeds'][0]]
    calls = sum(max(1, int(x['n_compatible_structures'] * cfg['query_multiplier'])) for x in chosen) * len(cfg['repeat_seeds'])
    print('Planned local calls:', calls, flush=True)
    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    src_sha = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT / 'src').glob('*.py')}
    identity = {'config': cfg, 'mode': args.mode, 'gen': args.gen, 'model_fingerprint': fingerprint,
                'split': args.split, 'source_sha256': src_sha, 'dataset_sha256': manifest['dataset_sha256']}
    if (out / 'identity.json').exists():
        assert json.loads((out / 'identity.json').read_text(encoding='utf-8')) == identity, 'Output identity mismatch'
    save(out / 'identity.json', identity)
    bench = off.Benchmark3D(str(ROOT / 'data' / '3d.json'))
    results = []
    curves = []
    for seed in cfg['repeat_seeds']:
        for obs in chosen:
            oid = obs['observation_id']
            n = max(1, int(obs['n_compatible_structures'] * cfg['query_multiplier']))
            client = RecordedClient(cfg, args.mode, out / 'raw' / str(seed) / oid, obs, oid,
                                    seed + int(hashlib.sha256(oid.encode()).hexdigest()[:8], 16),
                                    args.gen, off)
            client._n_queries = n
            result = bench.evaluate_single_observation_set(client, obs, n_queries=n, verbose=False, max_retries=1)
            if len(client.records) != n:
                raise RuntimeError('Incomplete API run; cached successful requests retained. Resume same command.')
            result.update(seed=seed, blocks=obs['observation'].count('1'))
            result.pop('cost', None)
            result['truncated_count'] = sum(r.get('done_reason') == 'length' for r in client.records)
            result['latency_s'] = sum(r['elapsed_s'] for r in client.records)
            results.append(result)
            for k in range(1, n + 1):
                v = bench.evaluate_single_observation_set(Replay(client.records[:k]), obs, n_queries=k,
                                                          verbose=False, max_retries=1)
                curves.append({'seed': seed, 'observation_id': oid, 'blocks': result['blocks'], 'k': k,
                               **{m: v[m] for m in ['valid_rate', 'novelty_rate', 'recovery_rate']}})
            save(out / 'partial.json', results)
            print(args.mode, args.gen, seed, oid, 'V/U/R',
                  *[round(result[m], 3) for m in ['valid_rate', 'novelty_rate', 'recovery_rate']], flush=True)
    summary = {'schema_version': 1, 'identity': identity, 'planned_calls': calls,
               'completed_calls': sum(r['n_queries'] for r in results),
               'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               'python': platform.python_version(), 'platform': platform.platform(), 'cost_usd': 0.0,
               'aggregate': {}, 'by_blocks': {}, 'results': results, 'curves': curves}
    for label, subset in [('aggregate', results)] + [(str(b), [r for r in results if r['blocks'] == b]) for b in cfg['blocks']]:
        stats = {m: {'mean': float(np.mean([r[m] for r in subset])),
                     'std': float(np.std([r[m] for r in subset], ddof=1)) if len(subset) > 1 else None}
                 for m in ['valid_rate', 'novelty_rate', 'recovery_rate']}
        if label == 'aggregate':
            summary['aggregate'] = stats
        else:
            summary['by_blocks'][label] = stats
    summary['resource_totals'] = {'calls': calls,
                                  'input_tokens': sum(r['token_usage']['prompt_tokens'] for r in results),
                                  'output_tokens': sum(r['token_usage']['completion_tokens'] for r in results),
                                  'model_call_seconds': sum(r['latency_s'] for r in results),
                                  'truncated_outputs': sum(r['truncated_count'] for r in results)}
    save(out / 'summary.json', summary)
    print('Completed', calls, 'calls;', out / 'summary.json')


if __name__ == '__main__':
    main()
