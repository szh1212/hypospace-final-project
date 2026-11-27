"""Paired analysis: final method vs baselines on identical (case, seed, budget) units.

Reads the final test summary (this repo) and the SZH baseline metrics.json
(frozen in the baseline branch), pairs units on (observation_id, seed), and runs
a 10,000-resample paired bootstrap for dV / dU / dR. Also builds the macro table,
prefix-recovery table and per-case table for the results document.
"""
import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))


def unit_map(summary, key):
    out = {}
    for r in summary['results']:
        out[(r['observation_set_id'], r['seed'])] = r
    return out


def curve_map(summary):
    """(oid, seed) -> {k: {valid_rate, novelty_rate, recovery_rate}}."""
    out = {}
    for c in summary['curves']:
        out.setdefault((c['observation_id'], c['seed']), {})[c['k']] = c
    return out


def macro_means(results, key):
    return {m: float(np.mean([r[m] for r in results])) for m in
            ['valid_rate', 'novelty_rate', 'recovery_rate']}


def prefix_recovery(curves, units, ks):
    """Macro R@k over units, clamping each unit at its own budget n_gt."""
    out = {}
    for k in ks:
        vals = []
        for key in units:
            cmap = curves.get(key, {})
            kk = min(k, max(cmap.keys()))
            vals.append(cmap[kk]['recovery_rate'])
        out[k] = float(np.mean(vals)) if vals else float('nan')
    return out


def paired_bootstrap(a_units, b_units, metrics, n_resample=10000, rng=None):
    """Paired bootstrap over units: mean(a-b), 95% CI, win count, P(<=0)."""
    rng = rng or np.random.default_rng(33550336)
    keys = sorted(set(a_units) & set(b_units))
    report = {}
    for m in metrics:
        d = np.array([a_units[k][m] - b_units[k][m] for k in keys])
        boots = []
        for _ in range(n_resample):
            idx = rng.integers(0, len(d), len(d))
            boots.append(d[idx].mean())
        boots = np.array(boots)
        report[m] = {
            'n_units': len(d),
            'mean': float(d.mean()),
            'ci95': [float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))],
            'wins': int((d > 0).sum()),
            'ties': int((d == 0).sum()),
            'p_above_zero': float((boots > 0).mean()),
        }
    return keys, report


def fmt_pct(x):
    return f'{x * 100:.2f}%'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--final', default='runs/joint-test/summary.json')
    ap.add_argument('--final-dev', default='runs/joint-dev/summary.json')
    ap.add_argument('--baseline', required=True, help='SZH baseline metrics.json')
    ap.add_argument('--official', default='runs/official-test/summary.json')
    ap.add_argument('--offline', default='runs/offline-test/summary.json')
    ap.add_argument('--gen1', default='runs/verbal-dev-smoke/summary.json')
    ap.add_argument('--gen2', default='runs/free-dev-smoke/summary.json')
    ap.add_argument('--gen3', default='runs/k2-dev-smoke/summary.json')
    ap.add_argument('--final-dev-smoke', default='runs/joint-dev-smoke/summary.json')
    ap.add_argument('--out', default='runs/analysis-3d.json')
    args = ap.parse_args()

    def load(path):
        if not os.path.exists(path):
            return None
        return json.load(open(path, encoding='utf-8'))

    final = load(ROOT / args.final)
    base = load(args.baseline)
    official = load(ROOT / args.official)
    offline = load(ROOT / args.offline)
    gen1 = load(ROOT / args.gen1)
    gen2 = load(ROOT / args.gen2)
    gen3 = load(ROOT / args.gen3)
    final_dev = load(ROOT / args.final_dev)
    final_dev_smoke = load(ROOT / args.final_dev_smoke)

    if final is None or base is None:
        raise SystemExit('final or baseline summary missing')

    metrics = ['valid_rate', 'novelty_rate', 'recovery_rate']
    funits, bunits = unit_map(final, 'x'), unit_map(base, 'x')
    fcurves, bcurves = curve_map(final), curve_map(base)
    assert set(funits) == set(bunits), 'unit mismatch between final and baseline'

    ks = [1, 2, 3, 4, 6, 9, 16, 27]
    keys, diffs = paired_bootstrap(funits, bunits, metrics)

    out = {'paired': {'final_vs_baseline': {'keys': [list(k) for k in keys], 'metrics': diffs}},
           'macros': {}, 'prefix_recovery': {}}

    def macros_of(name, summ):
        if summ is None:
            return None
        return {m: round(v, 6) for m, v in macro_means(summ['results'], 'x').items()}

    out['macros']['final_test'] = macros_of('final', final)
    out['macros']['baseline'] = macros_of('baseline', base)
    out['macros']['official_test'] = macros_of('official', official)
    out['macros']['offline_test'] = macros_of('offline', offline)
    out['macros']['gen1_dev_smoke'] = macros_of('gen1', gen1)
    out['macros']['gen2_dev_smoke'] = macros_of('gen2', gen2)
    out['macros']['gen3_dev_smoke'] = macros_of('gen3', gen3)
    out['macros']['final_dev'] = macros_of('final_dev', final_dev)
    out['macros']['final_dev_smoke'] = macros_of('final_dev_smoke', final_dev_smoke)

    for name, curves, summ in [('final', fcurves, final), ('baseline', bcurves, base)]:
        units = unit_map(summ, 'x')
        out['prefix_recovery'][name] = {k: round(v, 6) for k, v in
                                        prefix_recovery(curves, units, ks).items()}
    for name, summ in [('official', official), ('offline', offline)]:
        if summ is None:
            continue
        units = unit_map(summ, 'x')
        out['prefix_recovery'][name] = {k: round(v, 6) for k, v in
                                        prefix_recovery(curve_map(summ), units, ks).items()}

    # Paired comparisons against the other references, when available
    for ref_name, ref_sum in [('official', official), ('offline', offline)]:
        if ref_sum is None:
            continue
        runits = unit_map(ref_sum, 'x')
        _, d = paired_bootstrap(funits, runits, metrics)
        out['paired'][f'final_vs_{ref_name}'] = {'metrics': d}

    # Per-case table (15 rows, macro over seeds)
    cases = sorted({oid for oid, _ in funits})
    per_case = []
    for oid in cases:
        fu = [funits[(oid, s)] for s in (17, 42, 2026) if (oid, s) in funits]
        bu = [bunits[(oid, s)] for s in (17, 42, 2026) if (oid, s) in bunits]
        per_case.append({
            'case': oid,
            'blocks': fu[0]['blocks'],
            'baseline': {m: round(float(np.mean([r[m] for r in bu])), 6) for m in metrics},
            'final': {m: round(float(np.mean([r[m] for r in fu])), 6) for m in metrics},
        })
    out['per_case'] = per_case

    by_blocks = {}
    for b in (1, 2, 3):
        fu = [funits[k] for k in funits if funits[k]['blocks'] == b]
        bu = [bunits[k] for k in bunits if bunits[k]['blocks'] == b]
        by_blocks[str(b)] = {
            'baseline': {m: round(float(np.mean([r[m] for r in bu])), 6) for m in metrics},
            'final': {m: round(float(np.mean([r[m] for r in fu])), 6) for m in metrics},
        }
    out['by_blocks'] = by_blocks

    (ROOT / args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(ROOT / args.out, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    # Console report
    print('=== macros ===')
    for name, m in out['macros'].items():
        if m is None:
            continue
        print(f"{name:22s} V {fmt_pct(m['valid_rate']):>8s}  U {fmt_pct(m['novelty_rate']):>8s}  R {fmt_pct(m['recovery_rate']):>8s}")
    print('\n=== paired final - baseline (bootstrap 10k over units) ===')
    for m, d in diffs.items():
        lo, hi = d['ci95']
        print(f"d{m[:1].upper()}: {d['mean'] * 100:+7.2f}pp  CI95 [{lo * 100:+6.2f}, {hi * 100:+6.2f}]  "
              f"wins {d['wins']}/{d['n_units']}  P(>0)={d['p_above_zero']:.4f}")
    print('\n=== prefix recovery (macro) ===')
    for name in ('baseline', 'final'):
        print(name, {k: fmt_pct(v) for k, v in out['prefix_recovery'][name].items()})
    print('\n=== per case (macro over seeds) ===')
    for row in per_case:
        print(f"{row['case']} b{row['blocks']}  base V {fmt_pct(row['baseline']['valid_rate'])} U {fmt_pct(row['baseline']['novelty_rate'])} R {fmt_pct(row['baseline']['recovery_rate'])}"
              f"   final V {fmt_pct(row['final']['valid_rate'])} U {fmt_pct(row['final']['novelty_rate'])} R {fmt_pct(row['final']['recovery_rate'])}")
    print('\n=== by blocks ===')
    for b, v in by_blocks.items():
        print(f"blocks {b}: baseline V {fmt_pct(v['baseline']['valid_rate'])} U {fmt_pct(v['baseline']['novelty_rate'])} R {fmt_pct(v['baseline']['recovery_rate'])}"
              f"   final V {fmt_pct(v['final']['valid_rate'])} U {fmt_pct(v['final']['novelty_rate'])} R {fmt_pct(v['final']['recovery_rate'])}")
    print(f'\nwritten: {ROOT / args.out}')


if __name__ == '__main__':
    main()
