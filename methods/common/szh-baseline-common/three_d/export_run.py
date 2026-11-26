"""Export small auditable metrics and failure categories from a completed real run."""
import argparse,json,hashlib
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from hypospace_runner import upstream,save
p=argparse.ArgumentParser();p.add_argument('run',type=Path);p.add_argument('--out',required=True,type=Path);a=p.parse_args()
d=json.loads((a.run/'summary.json').read_text(encoding='utf-8'))
if d['identity']['mode']!='llm': raise ValueError('This exporter accepts only real LLM runs')
off,_=upstream();b=object.__new__(off.Benchmark3D)
categories={'parse failure':0,'invalid structure':0,'valid duplicate':0,'new valid':0};artifacts=[]
for task in d['results']:
    records=sorted((a.run/'raw'/str(task['seed'])/task['observation_set_id']).glob('*.json'))
    assert len(records)==task['n_queries']
    seen=set()
    for path in records:
        raw=json.loads(path.read_text(encoding='utf-8'));s=b.parse_llm_response(raw['response'])
        prompt=raw['prompt']; key='parse failure'
        # Read observation from prepared data by ID; never send this evaluator's ground truths to generator.
        from hypospace_runner import ROOT
        ds=json.loads((ROOT/'data/3d.json').read_text(encoding='utf-8'))
        obs=next(x for x in ds['observation_sets'] if x['observation_id']==task['observation_set_id'])
        if s:
            s=s.normalize()
            if not b.validate_structure_matches_observations(s,obs['observation']): key='invalid structure'
            elif s.get_hash() in seen: key='valid duplicate'
            else: key='new valid';seen.add(s.get_hash())
        categories[key]+=1
        artifacts.append({'file':path.relative_to(a.run).as_posix(),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
# Strip bulky raw hypothesis texts; raw files remain available on SSD and hashed.
compact={k:v for k,v in d.items() if k!='results'}
compact['results']=[{k:v for k,v in row.items() if k not in ['all_hypotheses','unique_structures']} for row in d['results']]
compact['failure_categories']=categories
save(a.out/'metrics.json',compact);save(a.out/'raw-manifest.json',artifacts)
fig,ax=plt.subplots(figsize=(8,4),layout='constrained')
ax.bar(list(categories),list(categories.values()),color=['#a65757','#bd8851','#8a94a2','#408876'])
ax.set(ylabel='Generated proposals (count)',xlabel='Official parser / validator outcome',title=d['identity']['config']['model']+'\nAll real outputs, including failures and duplicates')
for i,n in enumerate(categories.values()): ax.text(i,n,str(n),ha='center',va='bottom')
ax.set_ylim(0,max(categories.values())*1.18+1);fig.savefig(a.out/'outcomes.png',dpi=180);plt.close(fig)
print(json.dumps({'aggregate':d['aggregate'],'resource_totals':d['resource_totals'],'categories':categories},indent=2))
