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


def plot_coverage(baseline, method, output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import PercentFormatter

    levels = sorted({row['blocks'] for row in baseline['curves']})
    fig, axes = plt.subplots(1, len(levels), figsize=(10, 3.5), sharey=True, layout='constrained')
    labels = {'adapted_baseline:transform': 'Adapted Baseline',
              'spatial_codec:cyclic': 'Cyclic height codec',
              'spatial_codec:row_major': 'Fixed-order height codec',
              'spatial_columns:grid_history': 'Column planning'}
    for level, axis in zip(levels, np.atleast_1d(axes)):
        for run, color, style in ((baseline, '#606b73', '--'), (method, '#006b83', '-')):
            by_prefix = defaultdict(list)
            for row in run['curves']:
                if row['blocks'] == level:
                    by_prefix[row['k']].append(row['recovery_rate'])
            budgets = sorted(by_prefix)
            name = run['identity']['method']
            axis.plot(budgets, [mean(by_prefix[k]) for k in budgets], style,
                      color=color, linewidth=2.2, label=labels.get(name, name))
        axis.set_title(f'Level {level}', loc='left', fontsize=11, fontweight='bold')
        axis.set_xlabel('Proposals per observation')
        axis.set_ylim(0, 1.02)
        ticks = np.linspace(0, len(budgets) - 1, min(len(budgets), 5)).round().astype(int)
        axis.set_xticks([budgets[i] for i in ticks])
        axis.yaxis.set_major_formatter(PercentFormatter(xmax=1, decimals=0))
        axis.grid(axis='y', alpha=0.25)
        axis.spines[['top', 'right']].set_visible(False)
    np.atleast_1d(axes)[0].set_ylabel('Macro Recovery')
    np.atleast_1d(axes)[0].legend(loc='upper left', frameon=False, fontsize=8)
    fig.suptitle('Recovery by proposal budget', fontsize=13, fontweight='bold')
    fig.savefig(output, dpi=180)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('baseline', type=Path)
    parser.add_argument('methods', nargs='+', type=Path)
    parser.add_argument('--select', action='store_true', help='Select among methods on the development split')
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--coverage-plot', type=Path)
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
    if args.coverage_plot:
        if len(candidates) != 1:
            raise ValueError('A coverage plot requires exactly one candidate')
        plot_coverage(baseline, candidates[0], args.coverage_plot)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
