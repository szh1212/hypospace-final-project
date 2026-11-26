"""Write final English results only after complete inference and successful replay."""
from pathlib import Path
import json,statistics
ROOT=Path(__file__).resolve().parents[2]
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
d={k:read(ROOT/f'methods/szh-baseline-{k}/reports/test.json') for k in ['causal','genetic']}
for k,x in d.items():
    assert x['planned_calls']==x['completed_calls']
    assert read(ROOT/f'methods/szh-baseline-{k}/reports/audit.json')['all_requests_and_metrics_match']
b=read(ROOT/'docs/figures/baseline/metrics.json');ms=['valid_rate','novelty_rate','recovery_rate']
pct=lambda v:f'{100*v:.2f}%'
rows=[]
for title,k in [('Causal Graph Inference','causal'),('3D Voxel Reconstruction',None),('Boolean Genetic Interaction','genetic')]:
    values=d[k]['unified_macro'] if k else {m:b['aggregate'][m]['mean'] for m in ms}
    calls=d[k]['unified_calls'] if k else 585
    rows.append('| '+title+' | Qwen2.5-3B | '+' | '.join(pct(values[m]) for m in ms)+f' | {calls} |')
section='''## Baseline Results Across Three Domains

| Domain | Model | Validity | Uniqueness | Recovery | LLM Calls |
| --- | --- | ---: | ---: | ---: | ---: |
'''+ '\n'.join(rows)+'''

These are within-domain diagnostic measurements, not a fair comparison of algorithm performance across domains. The unified baseline uses the frozen 3D sampling parameters, task-adapted prompts and official scoring. New runs use seeds 17/42/2026 and one call per compatible hypothesis on their frozen test subsets. The causal study uses four nodes and at most four edges; Boolean studies basic/extended/full operators at depth two. The 3D figures are preserved from the archived report; its published 585-call compressed raw archive has been independently replayed on this machine (see historical-3d-replay.json).

The causal alignment protocol reuses a single batch on LWT's 13 final test cases at budgets 4/8/13/16. Total new causal calls including alignment are '''+str(d['causal']['completed_calls'])+'''. Macro means weight instances equally; micro pooling and across-seed sample standard deviations are reported separately. Different official budgets and solution-space sizes make cross-domain Recovery incomparable as an algorithm ranking.

See [all-domain report](docs/baseline-all-domains/results.md), [shared reproduction commands](methods/szh-baseline-common/README.md), and task-specific tracked reports and raw SHA256 manifests.
'''
report=section+'\n## Measured resources\n\n| Domain | Calls | Input tokens | Output tokens | Model seconds | Commercial cost |\n| --- | ---: | ---: | ---: | ---: | ---: |\n'
for k,x in d.items():
    r=x['resource_totals'];report+=f"| {k} | {r['calls']} | {r['input_tokens']} | {r['output_tokens']} | {r['seconds']:.2f} | $0 |\n"
report+='\n## Causal aligned baseline prefixes\n\n| Seeds | Budget | Validity | Uniqueness | Recovery |\n| --- | ---: | ---: | ---: | ---: |\n'
for seeds in [['17','42'],['17','42','2026']]:
    for k,v in d['causal']['aligned'].items():
        report+='| '+','.join(seeds)+' | '+k+' | '+' | '.join(pct(statistics.mean(v[s][m] for s in seeds)) for m in ms)+' |\n'
report+='\nLWT source reports final R@4=36.34%, R@8=47.34%, R@16=56.66% for seeds 17/42, and R@13=53.43% for three seeds. These are teammate-reported values, not independently replayed measurements here (Historical Replay Not Verified). Its 256-token GPU configuration differs from the 512-token CPU baseline. Raw teammate data are required before claiming a fully audited fair comparison.\n\n## Failure accounting\n\n| Domain | Invalid | Parsing failures | Valid duplicates |\n| --- | ---: | ---: | ---: |\n'
for k,x in d.items():
    report+='| '+k+' | '+' | '.join(str(sum(r[f] for r in x['results'])) for f in ['invalid_outputs','parsing_failures','valid_duplicates'])+' |\n'
report+='\nPer-call scores, per-instance/seed/level metrics, prefix curves, micro rates and seed standard deviations are in each task reports/test.json. New raw records remain in ignored runs/all-domains/. Replay checks every reconstructed request, response manifest, prefix score and summary.\n'
out=ROOT/'docs/baseline-all-domains/results.md';out.write_text(report,encoding='utf-8')
p=ROOT/'README.md';text=p.read_text(encoding='utf-8');assert '## Baseline Results Across Three Domains' not in text;p.write_text(text+'\n'+section,encoding='utf-8')
for k in d:
    p=ROOT/f'methods/szh-baseline-{k}/README.md';s=p.read_text(encoding='utf-8-sig').replace('Status: NOT_RUN for formal experiments.','Status: COMPLETE for formal inference and local replay; LWT values are cited from its formal report (Historical Replay Not Verified).');p.write_text(s,encoding='utf-8')
print(out)
