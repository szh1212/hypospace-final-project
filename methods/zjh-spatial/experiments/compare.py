"""Compare matched runs, preserving all repeats of each sampled observation."""

import argparse
from collections import defaultdict
import json
from pathlib import Path
from statistics import mean

import numpy as np


METRICS = ('valid_rate', 'novelty_rate', 'recovery_rate')
IDENTITY_FIELDS = ('config', 'model_fingerprint', 'split', 'dataset_sha256', 'smoke')


def _rows(run):
    rows = {(r['observation_set_id'], r['seed']): r for r in run['results']}
    if len(rows) != len(run['results']) or sum(r['n_queries'] for r in rows.values()) != run['completed_calls']:
        raise ValueError('Duplicate observation/seed records or an inconsistent call count')
    return rows


def _matched(baseline, method):
    reference, candidate = baseline['identity'], method['identity']
    if reference['mode'] != 'llm' or candidate['mode'] != 'llm':
        raise ValueError('Only real inference results are comparable')
    if differences := [name for name in IDENTITY_FIELDS if reference[name] != candidate[name]]:
        raise ValueError(f'Incomparable run fields: {differences}')
    before, after = _rows(baseline), _rows(method)
    if before.keys() != after.keys() or any(before[k]['n_queries'] != after[k]['n_queries'] for k in before):
        raise ValueError('Instances, seeds and per-observation budgets must match')
    return before, after


def _interval(observation_deltas, observation_levels):
    strata = defaultdict(list)
    for observation, deltas in observation_deltas.items():
        strata[observation_levels[observation]].append(mean(deltas))
    rng = np.random.default_rng(20261125)
    sums = [rng.choice(values, size=(20000, len(values))).sum(axis=1) for values in strata.values()]
    return np.quantile(sum(sums) / len(observation_deltas), [0.025, 0.975]).tolist()


def compare(baseline, method):
    before, after = _matched(baseline, method)
    observation_levels = {oid: r['blocks'] for (oid, _), r in before.items()}
    overall, by_seed, by_level = {}, {}, {}
    for metric in METRICS:
        observation_deltas, seed_deltas, level_deltas = defaultdict(list), defaultdict(list), defaultdict(list)
        for observation, seed in sorted(before):
            key = observation, seed
            change = after[key][metric] - before[key][metric]
            observation_deltas[observation].append(change)
            seed_deltas[seed].append(change)
            level_deltas[before[key]['blocks']].append(change)
        overall[metric] = {
            'baseline': mean(row[metric] for row in before.values()),
            'method': mean(row[metric] for row in after.values()),
            'delta': mean(mean(items) for items in observation_deltas.values()),
            'observation_bootstrap_95': _interval(observation_deltas, observation_levels),
        }
        by_seed[metric] = {seed: mean(deltas) for seed, deltas in seed_deltas.items()}
        by_level[metric] = {level: mean(deltas) for level, deltas in level_deltas.items()}
    return {
        'observations': len({oid for oid, seed in before}),
        'observation_seed_pairs': len(before),
        'overall': overall,
        'delta_by_seed': by_seed,
        'delta_by_level': by_level,
        'resources': method['resource_totals'],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('baseline', type=Path)
    parser.add_argument('methods', nargs='+', type=Path)
    parser.add_argument('--select', action='store_true', help='Select among methods on the development split')
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    baseline = json.loads(args.baseline.read_text(encoding='utf-8'))
    candidates = [json.loads(path.read_text(encoding='utf-8')) for path in args.methods]
    comparisons = {run['identity']['method']: compare(baseline, run) for run in candidates}
    report = {'baseline': baseline['identity']['method'], 'baseline_resources': baseline['resource_totals'],
              'split': baseline['identity']['split'], 'comparisons': comparisons}
    if args.select:
        if report['split'] != 'dev':
            raise ValueError('Method selection requires full development runs')

        def priority(method):
            overall = comparisons[method]['overall']
            validity_delta = overall['valid_rate']['delta']
            return validity_delta >= -1e-12, overall['recovery_rate']['method'], overall['valid_rate']['method']

        report['selected'] = max(comparisons, key=priority)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
