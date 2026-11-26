"""Pinned official evaluators, local transport, resumable calls and independent replay."""
import argparse, contextlib, gzip, hashlib, importlib, io, json, random, subprocess, sys, statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from ollama_client import OllamaClient
import prompts
PIN='c69e9318577b34b5b896996571aefd4ba6053f58'
METRICS=['valid_rate','novelty_rate','recovery_rate']
def digest(x): return hashlib.sha256(json.dumps(x,sort_keys=True).encode()).hexdigest()
def read(p): return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def save(p,x):
    p=Path(p); p.parent.mkdir(parents=True,exist_ok=True)
    tmp=p.with_suffix('.tmp'); tmp.write_text(json.dumps(x,indent=2,ensure_ascii=False),encoding='utf-8'); tmp.replace(p)
def official(up,domain):
    rev=subprocess.check_output(['git','-c',f'safe.directory={up.as_posix()}','-C',str(up),'rev-parse','HEAD'],text=True).strip()
    assert rev==PIN
    assert not subprocess.check_output(['git','-c',f'safe.directory={up.as_posix()}','-C',str(up),'diff','HEAD','--',('causal' if domain=='causal' else 'boolean')],text=True)
    folder=up/('causal' if domain=='causal' else 'boolean')
    saved={n:m for n,m in sys.modules.items() if n=='modules' or n.startswith('modules.')}
    oldpath=list(sys.path)
    try:
        for n in saved: del sys.modules[n]
        sys.path.insert(0,str(folder))
        return importlib.import_module('run_causal_benchmark' if domain=='causal' else 'boolean_benchmark')
    finally:
        for n in list(sys.modules):
            if n=='modules' or n.startswith('modules.'): del sys.modules[n]
        sys.modules.update(saved)
        sys.path[:]=oldpath

def score(bench,case,records):
    class Replay:
        def __init__(self): self.it=iter(records)
        def query_with_usage(self,p): return next(self.it)
    with contextlib.redirect_stdout(io.StringIO()):
        return bench.evaluate_single_observation_set(Replay(),case,n_queries=len(records),verbose=False,max_retries=1)

def history(bench,records,domain):
    seen={}
    for r in records:
        h=bench.parse_llm_response(r['response'])
        if h is not None:
            if domain=='causal': key=h.get_hash(); text='Graph: '+(', '.join(a+'->'+b for a,b in sorted(h.edges)) or 'No edges')
            else: key=bench.get_expression_mechanistic_key(h); text='Expression: '+h
            if key is not None: seen.setdefault(str(key),text)
    return list(seen.values())

def prompt(bench,case,records,domain):
    if domain=='causal':
        meta={'nodes':bench.nodes,'max_edges':bench.max_edges}
        obs='\n'.join(o['string'] for o in case['observations'])
    else:
        meta=bench.metadata
        obs=' '.join(meta['variables'])+' | output\n'+'\n'.join(' '.join(str(o['inputs'][v]) for v in meta['variables'])+' | '+str(o['output']) for o in case['observations'])
    return getattr(prompts,domain)(meta,obs,history(bench,records,domain))

def prepare():
    cfg=read(ROOT/'experiments/protocol.json')
    cfg.update(protocol='all-domains-adapted-v1',baseline_method='task-adapted-history',status='DRAFT')
    cfg.pop('baseline_source_sha256',None)
    data=ROOT/'data/baseline-all-domains'
    out=ROOT/'methods/szh-baseline-common'
    aligned=json.loads(subprocess.check_output(['git','-c',f'safe.directory={ROOT.as_posix()}','show','origin/kevin/causal-main:experiments/parent-strata.json'],text=True))
    cases=read(data/'causal.json')['datasets_by_n_observations']
    rng=random.Random(cfg['split_seed']); splits={'dev':[], 'test':[]}
    for n,rows in sorted(cases.items()):
        ids=sorted(r['observation_set_id'] for r in rows if r['observation_set_id'] not in aligned['test'])
        rng.shuffle(ids); splits['dev']+=ids[:2]; splits['test']+=ids[2:7]
    cfg['causal']={'splits':splits,'aligned_test':aligned['test'],'aligned_budget':16,'budget':'one call per compatible graph; aligned prefixes reused'}
    # Share observation identities across operator levels to prevent dev/test overlap.
    common=set.intersection(*[set(r['observation_set_id'] for rows in read(data/f'boolean-{level}.json')['datasets_by_n_observations'].values() for r in rows) for level in ['basic','extended','full']])
    ids=sorted(common); rng.shuffle(ids)
    cfg['genetic']={'levels':['basic','extended','full'],'splits':{'dev':ids[:2],'test':ids[2:7]},'budget':'one call per compatible expression','max_depth':2}
    cfg['data_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in data.glob('*.json')}
    save(out/'protocol.json',cfg)

def main():
    p=argparse.ArgumentParser(); p.add_argument('--prepare',action='store_true');p.add_argument('--upstream',type=Path,default=ROOT.parent/'upstream-hypospace');p.add_argument('--domain',choices=['causal','genetic']);p.add_argument('--stage',choices=['smoke','test','audit','freeze','plan'],default='smoke');a=p.parse_args()
    if a.prepare: prepare();return
    cfg=read(ROOT/'methods/szh-baseline-common/protocol.json')
    sources={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob('*.py')}
    freeze=ROOT/'methods/szh-baseline-common/freeze.json'
    if a.stage=='freeze':
        for d in ['causal','genetic']:
            sm=read(ROOT/f'methods/szh-baseline-{d}/reports/smoke.json'); assert sm['completed_calls']==sm['planned_calls'] and sm['macro']['valid_rate']>0
        cfg['status']='FROZEN'
        save(ROOT/'methods/szh-baseline-common/protocol.json',cfg)
        save(freeze,{'config_sha256':digest(cfg),'sources':sources});return
    if a.stage in ['test','audit']: assert read(freeze)=={'config_sha256':digest(cfg),'sources':sources},'Freeze mismatch'
    domain=a.domain; mod=official(a.upstream.resolve(),domain)
    levels=['causal'] if domain=='causal' else cfg['genetic']['levels']
    plans=[]
    for level in levels:
        ds_path=ROOT/'data/baseline-all-domains'/('causal.json' if domain=='causal' else f'boolean-{level}.json')
        assert hashlib.sha256(ds_path.read_bytes()).hexdigest()==cfg['data_sha256'][ds_path.name]
        bench=mod.CausalBenchmarkEnhanced(str(ds_path)) if domain=='causal' else mod.BooleanBenchmarkRefined(str(ds_path))
        ds=read(ds_path); rows=[r for rs in ds['datasets_by_n_observations'].values() for r in rs]
        selected=cfg[domain]['splits']['dev' if a.stage=='smoke' else 'test']
        if domain=='causal' and a.stage!='smoke': selected=list(dict.fromkeys(selected+cfg[domain]['aligned_test']))
        for seed in ([17] if a.stage=='smoke' else cfg['repeat_seeds']):
            for row in rows:
                oid=row['observation_set_id']
                if oid not in selected: continue
                gt=row['n_compatible_graphs' if domain=='causal' else 'n_compatible_expressions']
                n=3 if a.stage=='smoke' else gt
                if domain=='causal' and a.stage!='smoke' and oid in cfg['causal']['aligned_test']: n=max(n,16)
                plans.append((level,bench,row,seed,n,gt))
    total=sum(x[4] for x in plans); done=0; failures=0; results=[]; manifest=[]
    if a.stage=='plan':
        print(json.dumps({'domain':domain,'planned_calls':total,'units':len(plans)},indent=2));return
    stage='test' if a.stage=='audit' else a.stage
    out=ROOT/f'runs/all-domains/{domain}/{stage}'
    report=ROOT/f'methods/szh-baseline-{domain}/reports/{stage}.json'
    client=OllamaClient(cfg)
    fingerprint=None if a.stage=='audit' else client.fingerprint()
    if fingerprint is not None: assert fingerprint==read(ROOT/'experiments/model-lock.json'),'Model template/identity mismatch'
    identity={'config':cfg,'sources':sources,'transport_sha256':hashlib.sha256((ROOT/'src/ollama_client.py').read_bytes()).hexdigest(),'official_sources':{str(p.relative_to(a.upstream)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(a.upstream.rglob('*.py'))},'data':cfg['data_sha256']}
    if (out/'identity.json').exists(): assert read(out/'identity.json')['identity']==identity
    elif a.stage=='audit': raise RuntimeError('No run to audit')
    else: save(out/'identity.json',{'identity':identity,'fingerprint':fingerprint})
    for level,bench,case,seed,n,gt in plans:
        oid=case['observation_set_id']; records=[]; call_scores=[]
        for q in range(n):
            path=out/'raw'/level/str(seed)/oid/f'{q:04}.json'
            text=prompt(bench,case,records,domain)
            call_seed=(seed+int(hashlib.sha256(oid.encode()).hexdigest()[:8],16)+q)%2147483647
            req=client.request(text,call_seed)
            if path.exists():
                r=read(path); assert r['request']==req and r['request_sha256']==digest(req)
            else:
                if a.stage=='audit': raise RuntimeError(f'Missing {path}')
                r={**client.generate(req),'request':req,'request_sha256':digest(req),'repeat_seed':seed,'query_index':q,'cost':0.0}; save(path,r)
            records.append(r); done+=1
            single=score(bench,case,[r]); call_scores.append({k:single[k] for k in ['n_valid','n_unique_all','n_recovered_gts','parse_success_rate']}); failures+=int(single['n_valid']==0)
            manifest.append({'file':str(path.relative_to(out)),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
            progress={'domain':domain,'stage':a.stage,'completed_calls':done,'total_calls':total,'percent':round(100*done/total,2),'case':oid,'seed':seed,'invalid_outputs':failures}
            save(out/'progress.json',progress); print(json.dumps(progress),flush=True)
        res=score(bench,case,records)
        res.update(level=level,seed=seed,call_scores=call_scores,latency_s=sum(r['elapsed_s'] for r in records))
        res['prefixes']={str(k):{m:score(bench,case,records[:k])[m] for m in METRICS} for k in range(1,n+1) if k<=n}
        res['unified_protocol']=oid in cfg[domain]['splits']['test']
        res['official_budget']=gt
        unified_score=score(bench,case,records[:gt]) if len(records)>=gt else None
        res['unified_score']={k:unified_score[k] for k in METRICS+['n_queries','n_valid','n_unique_all','n_recovered_gts','n_ground_truths']} if unified_score else None
        res['invalid_outputs']=n-res['n_valid'];res['valid_duplicates']=res['n_valid']-res['n_unique_valid']
        res['parsing_failures']=round(n*(1-res['parse_success_rate']))
        res['failure_categories']={'parse_failure':res['parsing_failures'],'parsed_invalid':res['invalid_outputs']-res['parsing_failures'],'valid_duplicate':res['valid_duplicates']}
        results.append(res)
        save(out/'partial.json',results)
    macro={m:statistics.mean(r[m] for r in results) for m in METRICS}
    per_seed={str(s):{m:statistics.mean(r[m] for r in results if r['seed']==s) for m in METRICS} for s in sorted({r['seed'] for r in results})}
    summary={'status':'COMPLETE','planned_calls':total,'completed_calls':done,'macro':macro,'per_seed':per_seed,'across_seeds':{m:{'mean':statistics.mean(v[m] for v in per_seed.values()),'std':statistics.stdev(v[m] for v in per_seed.values()) if len(per_seed)>1 else None} for m in METRICS},'micro':{'valid_rate':sum(r['n_valid'] for r in results)/total,'novelty_rate':sum(r['n_unique_all'] for r in results)/total,'recovery_rate':sum(r['n_recovered_gts'] for r in results)/sum(r['n_ground_truths'] for r in results)},'per_level':{l:{m:statistics.mean(r[m] for r in results if r['level']==l) for m in METRICS} for l in levels},'resource_totals':{'calls':done,'input_tokens':sum(r['token_usage']['prompt_tokens'] for r in results),'output_tokens':sum(r['token_usage']['completion_tokens'] for r in results),'seconds':sum(r['latency_s'] for r in results),'commercial_cost_usd':0},'results':results}
    if stage=='test':
        u=[r['unified_score'] | {'seed':r['seed'],'n_observations':r['n_observations'],'level':r['level']} for r in results if r['unified_protocol']]
        summary['unified_per_seed']={str(seed):{m:statistics.mean(r[m] for r in u if r['seed']==seed) for m in METRICS} for seed in cfg['repeat_seeds']}
        summary['unified_across_seeds']={m:{'mean':statistics.mean(v[m] for v in summary['unified_per_seed'].values()),'std':statistics.stdev(v[m] for v in summary['unified_per_seed'].values())} for m in METRICS}
        summary['unified_micro']={m:sum(r[num] for r in u)/sum(r[den] for r in u) for m,num,den in [('valid_rate','n_valid','n_queries'),('novelty_rate','n_unique_all','n_queries'),('recovery_rate','n_recovered_gts','n_ground_truths')]}
        summary['unified_calls']=sum(r['n_queries'] for r in u)
        summary['by_observation_count']={str(n):{m:statistics.mean(r[m] for r in u if r['n_observations']==n) for m in METRICS} for n in sorted({r['n_observations'] for r in u})}
    summary['unified_macro']={m:statistics.mean(r['prefixes'][str(r['official_budget'])][m] for r in results if r['unified_protocol']) for m in METRICS} if stage=='test' else None
    if domain=='causal' and stage=='test':
        summary['aligned']={str(k):{str(seed):{m:statistics.mean(r['prefixes'][str(k)][m] for r in results if r['observation_set_id'] in cfg['causal']['aligned_test'] and r['seed']==seed) for m in METRICS} for seed in cfg['repeat_seeds']} for k in [4,8,13,16]}
    if a.stage=='audit':
        assert read(report)==summary; assert read(report.with_name(stage+'-manifest.json'))==manifest
        save(report.with_name('audit.json'),{'all_requests_and_metrics_match':True,'calls_replayed':done})
        with report.with_name('raw.jsonl.gz').open('wb') as stream, gzip.GzipFile(fileobj=stream,filename='',mode='wb',mtime=0) as archive:
            for entry in manifest:
                raw=(out/entry['file']).read_bytes()
                assert hashlib.sha256(raw).hexdigest()==entry['sha256']
                archive.write((json.dumps({'path':entry['file'],'utf8':raw.decode('utf-8')},ensure_ascii=False)+'\n').encode('utf-8'))
    else: save(report,summary);save(report.with_name(stage+'-manifest.json'),manifest)
if __name__=='__main__':main()
