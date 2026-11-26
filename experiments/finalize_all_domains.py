"""Post-audit comparison table using explicitly reported teammate values."""
import json,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
d=read(ROOT/'methods/szh-baseline-causal/reports/test.json')
assert read(ROOT/'methods/szh-baseline-causal/reports/audit.json')['all_requests_and_metrics_match']
lines=['','## Same-case, same-call-budget comparison with the reported LWT final method','','| Test cases | Seeds | Calls per case | Adapted baseline R | LWT final R (reported) |','| --- | --- | ---: | ---: | ---: |']
for budget,seeds,reported in [(4,['17','42'],.3634),(8,['17','42'],.4734),(13,['17','42','2026'],.5343),(16,['17','42'],.5666)]:
 value=statistics.mean(d['aligned'][str(budget)][seed]['recovery_rate'] for seed in seeds)
 lines.append(f'| Same 13 cases | {", ".join(seeds)} | {budget} | {value:.2%} | {reported:.2%} |')
lines+=['','LWT figures are quoted from [its final formal report](https://github.com/szh1212/hypospace-final-project/blob/47c9500c22e4c35a931a76544677fb31baef74a3/docs/experiment-results.md). Historical Replay Not Verified. This table aligns task, case identities, call budgets and the listed seeds. It does not claim identical decoding: LWT used 256 output tokens and GPU execution, while the adapted baseline preserves 512 output tokens and CPU execution from the frozen 3D configuration. No paired confidence intervals or independently verified LWT prefix scores are claimed.','', '## Development overhead','','Two smoke passes used 60 additional calls, reported separately from formal budgets. See development-study.json for exact per-pass token and time accounting; development-raw.jsonl.gz preserves those requests. The only prompt revision was Boolean input formatting and allowed-operator descriptions, performed before formal freeze.','']
p=ROOT/'docs/baseline-all-domains/results.md';s=p.read_text(encoding='utf-8');assert '## Same-case, same-call-budget comparison' not in s;p.write_text(s+'\n'.join(lines),encoding='utf-8')
# Supplement the human-readable report with the statistical definitions already frozen.
p=ROOT/'docs/baseline-all-domains/results.md'
s=p.read_text(encoding='utf-8')
s+='\n## Seed uncertainty and pooled metrics\n\nSample standard deviations below are calculated from the three seed-level macro means (ddof=1), not from all instance-seed cells. Micro rates pool numerators and denominators while keeping each seed as a separate trial.\n\n| Domain | V mean +/- seed std | U mean +/- seed std | R mean +/- seed std | Micro V | Micro U | Micro R |\n| --- | ---: | ---: | ---: | ---: | ---: | ---: |\n'
metrics=['valid_rate','novelty_rate','recovery_rate']
summaries={}
for title,key in [('Causal','causal'),('3D','3d'),('Boolean','genetic')]:
 if key=='3d':
  x=read(ROOT/'docs/baseline-all-domains/published-3d-statistics.json');stats=x['across_seeds'];micro=x['micro']
 else:
  x=read(ROOT/f'methods/szh-baseline-{key}/reports/test.json');stats=x['unified_across_seeds'];micro=x['unified_micro']
 summaries[key]={'across_seeds':stats,'micro':micro}
 s+='| '+title+' | '+' | '.join(f"{stats[m]['mean']:.2%} +/- {stats[m]['std']:.2%}" for m in metrics)+' | '+' | '.join(f'{micro[m]:.2%}' for m in metrics)+' |\n'
p.write_text(s,encoding='utf-8')
(ROOT/'docs/baseline-all-domains/three-domain-statistics.json').write_text(json.dumps(summaries,indent=2),encoding='utf-8')
