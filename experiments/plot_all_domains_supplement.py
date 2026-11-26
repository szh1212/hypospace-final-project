"""Constant-cohort recovery curves from measured prefixes, without new inference."""
from pathlib import Path
import json,statistics
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
data={d:read(ROOT/f'methods/task-{"a" if d=="causal" else "c"}/szh-baseline-{d}/reports/test.json') for d in ['causal','genetic']}
b=read(ROOT/'methods/task-b/szh-baseline-3d/adapted/reports/metrics.json')
fig,axs=plt.subplots(1,2,figsize=(12,4),layout='constrained')
for domain,label in [('causal','Causal'),('genetic','Boolean')]:
 rows=[r for r in data[domain]['results'] if r['unified_protocol']];cap=max(r['official_budget'] for r in rows)
 means=[0]+[statistics.mean(r['prefixes'][str(min(k,r['official_budget']))]['recovery_rate'] for r in rows) for k in range(1,cap+1)]
 axs[0].plot(range(cap+1),means,label=label)
lookup={(r['seed'],r['observation_id'],r['k']):r['recovery_rate'] for r in b['curves']}
means=[0]+[statistics.mean(lookup[r['seed'],r['observation_set_id'],min(k,r['n_queries'])] for r in b['results']) for k in range(1,28)]
axs[0].plot(range(28),means,label='3D (archived)')
axs[0].set(title='Unified protocols: fixed test cohorts',xlabel='Calls per observation (capped at official budget)',ylabel='Macro Recovery');axs[0].legend();axs[0].grid(alpha=.2)
for seeds,label in [(['17','42'],'Seeds 17/42'),(['17','42','2026'],'Seeds 17/42/2026')]:
 ks=[4,8,13,16];rs=[statistics.mean(data['causal']['aligned'][str(k)][s]['recovery_rate'] for s in seeds) for k in ks]
 axs[1].plot(ks,rs,marker='o',label=label)
axs[1].set(title='Causal aligned protocol: same 13 cases',xlabel='Actual calls per observation',ylabel='Macro Recovery',xticks=[4,8,13,16]);axs[1].legend();axs[1].grid(alpha=.2)
fig.suptitle('Measured prefix recovery; constant case sets, no cross-domain algorithm ranking')
out=ROOT/'docs/baseline-all-domains/figures';fig.savefig(out/'recovery-fixed-cohort.png',dpi=180);fig.savefig(out/'recovery-fixed-cohort.pdf');plt.close(fig)
