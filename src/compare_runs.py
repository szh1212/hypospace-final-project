"""Reject incomparable experiments and report paired differences, not independent CIs."""
import argparse,json
from pathlib import Path
import numpy as np
p=argparse.ArgumentParser();p.add_argument('baseline');p.add_argument('method');p.add_argument('--out',required=True);a=p.parse_args()
x=json.loads(Path(a.baseline).read_text(encoding='utf-8'));y=json.loads(Path(a.method).read_text(encoding='utf-8'))
for k in ['config','model_fingerprint','split','dataset_sha256','smoke']:
    if x['identity'][k]!=y['identity'][k]: raise ValueError(f'Incomparable {k}')
if x['identity']['mode']!='llm' or y['identity']['mode']!='llm': raise ValueError('Real model runs required')
xr={(r['seed'],r['observation_set_id']):r for r in x['results']};yr={(r['seed'],r['observation_set_id']):r for r in y['results']}
if xr.keys()!=yr.keys(): raise ValueError('Task/repeat mismatch')
if any(xr[k]['n_queries']!=yr[k]['n_queries'] for k in xr): raise ValueError('Unequal generation budget')
report={'baseline':a.baseline,'method':a.method,'paired_task_repeats':len(xr),'resource_totals':{'baseline':x['resource_totals'],'method':y['resource_totals']},'differences':{}}
for metric in ['valid_rate','novelty_rate','recovery_rate']:
    delta=[yr[k][metric]-xr[k][metric] for k in xr]
    report['differences'][metric]={'mean_delta':float(np.mean(delta)),'sample_sd_delta':float(np.std(delta,ddof=1))}
Path(a.out).parent.mkdir(parents=True,exist_ok=True);Path(a.out).write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
