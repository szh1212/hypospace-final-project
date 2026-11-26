"""Create English figures only after both complete formal runs and replay audits exist."""
from pathlib import Path
import json,statistics
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[2]
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
data={}
for d in ['causal','genetic']:
    folder=ROOT/f'methods/szh-baseline-{d}/reports'
    x=read(folder/'test.json');assert x['completed_calls']==x['planned_calls']
    assert read(folder/'audit.json')['all_requests_and_metrics_match']
    data[d]=x
out=ROOT/'docs/baseline-all-domains/figures';out.mkdir(parents=True,exist_ok=True)
b=read(ROOT/'docs/figures/baseline/metrics.json')
metrics=['valid_rate','novelty_rate','recovery_rate']
labels=['Validity','Uniqueness','Recovery']
fig,axs=plt.subplots(1,3,figsize=(13,4),layout='constrained')
for ax,m,title in zip(axs,metrics,labels):
    for d in data:
        rows=data[d]['results'];ks=sorted(set(int(k) for r in rows for k in r['prefixes']))
        ax.plot(ks,[statistics.mean(r['prefixes'][str(k)][m] for r in rows if str(k) in r['prefixes']) for k in ks],label=d.title())
    ks=sorted({r['k'] for r in b['curves']})
    ax.plot(ks,[statistics.mean(r[m] for r in b['curves'] if r['k']==k) for k in ks],label='3D (archived)')
    ax.set(title=title,xlabel='Calls per observation',ylabel='Macro mean (available cases)',ylim=(-.03,1.05));ax.grid(alpha=.2)
axs[-1].legend();fig.suptitle('Qwen2.5-3B adapted baseline: prefix metrics (case sets vary with budget)')
fig.savefig(out/'budget-curves.png',dpi=180);fig.savefig(out/'budget-curves.pdf');plt.close(fig)
fig,axs=plt.subplots(1,3,figsize=(13,4),layout='constrained')
for ax,(d,x) in zip(axs,data.items()):
    categories=['parse_failure','parsed_invalid','valid_duplicate']
    ax.bar(categories,[sum(r['failure_categories'][c] for r in x['results']) for c in categories],color='#4386b0')
    ax.set(title=d.title(),ylabel='Output count');ax.tick_params(axis='x',labelrotation=20);ax.grid(axis='y',alpha=.2)
axs[2].bar(['parse_failure','parsed_invalid','valid_duplicate'],[b['failure_categories'][k] for k in ['parse failure','invalid structure','valid duplicate']],color='#4386b0')
axs[2].set(title='3D (archived)',ylabel='Output count');axs[2].tick_params(axis='x',labelrotation=20);axs[2].grid(axis='y',alpha=.2)
fig.savefig(out/'failure-categories.png',dpi=180);fig.savefig(out/'failure-categories.pdf');plt.close(fig)
fig,axs=plt.subplots(1,3,figsize=(13,4),layout='constrained')
for ax,m,title in zip(axs,metrics,labels):
    levels=data['genetic']['per_level'];ax.bar(list(levels),[v[m] for v in levels.values()],color='#4386b0');ax.set(title=title,ylabel='Macro mean',ylim=(0,1.05));ax.grid(axis='y',alpha=.2)
fig.suptitle('Boolean operator regimes, depth 2');fig.savefig(out/'boolean-levels.png',dpi=180);fig.savefig(out/'boolean-levels.pdf');plt.close(fig)
print(out)
# Extend plots only from measured artifacts.
b=read(ROOT/'docs/figures/baseline/metrics.json')
resources={'Causal':data['causal']['resource_totals'],'3D (archived)':{'calls':b['resource_totals']['calls'],'input_tokens':b['resource_totals']['input_tokens'],'output_tokens':b['resource_totals']['output_tokens'],'seconds':b['resource_totals']['model_call_seconds']},'Boolean':data['genetic']['resource_totals']}
fig,axs=plt.subplots(1,3,figsize=(13,4),layout='constrained')
for ax,key,title in zip(axs,['calls','input_tokens','seconds'],['LLM calls','Input tokens','Model call seconds']):
    ax.bar(list(resources),[r[key] for r in resources.values()],color='#4386b0');ax.set(title=title);ax.tick_params(axis='x',labelrotation=15);ax.grid(axis='y',alpha=.2)
fig.suptitle('Computational cost: distinct domain protocols (causal includes alignment calls)');fig.savefig(out/'compute-cost.png',dpi=180);fig.savefig(out/'compute-cost.pdf');plt.close(fig)

fig,axs=plt.subplots(1,3,figsize=(13,4),layout='constrained')
for ax,m,title in zip(axs,metrics,labels):
    groups=data['causal']['by_observation_count'];ax.bar(list(groups),[v[m] for v in groups.values()],color='#4386b0');ax.set(title=title,xlabel='Observed interventions (four nodes)',ylabel='Macro mean',ylim=(0,1.05));ax.grid(axis='y',alpha=.2)
fig.suptitle('Causal unified protocol by observation count (not paper difficulty levels)');fig.savefig(out/'causal-observation-count.png',dpi=180);fig.savefig(out/'causal-observation-count.pdf');plt.close(fig)
fig,axs=plt.subplots(1,3,figsize=(13,4),layout='constrained')
for ax,m,title in zip(axs,metrics,labels):
    groups=b['by_blocks'];ax.bar(list(groups),[v[m]['mean'] for v in groups.values()],color='#4386b0');ax.set(title=title,xlabel='Occupied cells',ylabel='Macro mean',ylim=(0,1.05));ax.grid(axis='y',alpha=.2)
fig.suptitle('3D adapted baseline (published results, raw archive replayed)');fig.savefig(out/'3d-levels.png',dpi=180);fig.savefig(out/'3d-levels.pdf');plt.close(fig)
