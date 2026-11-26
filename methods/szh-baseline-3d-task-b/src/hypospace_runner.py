"""Pinned official evaluator + auditable transport and method prompt hooks."""
import argparse, hashlib, importlib, json, os, platform, random, subprocess, sys, time
from pathlib import Path
from ollama_client import OllamaClient
import numpy as np
import requests
ROOT = next(p for p in Path(__file__).resolve().parents if (p / ".git").exists())
sys.path.insert(0, str(ROOT / 'src'))
UP = ROOT / '.cache' / 'hypospace'
PIN = 'c69e9318577b34b5b896996571aefd4ba6053f58'

class TransportAbort(BaseException):
    pass

def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

def save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding='utf-8')

def upstream():
    revision = subprocess.check_output(['git','-c',f'safe.directory={UP.as_posix()}','-C',str(UP),'rev-parse','HEAD'],text=True).strip()
    if revision != PIN:
        raise ValueError('Wrong upstream revision')
    sys.path.insert(0,str(UP/'3d'))
    official=importlib.import_module('run_3d_benchmark')
    if not getattr(official.Structure3D,'_zero_array_fix',False):
        original=official.Structure3D.normalize
        def normalize(self):
            if self.layers and all(not np.any(layer) for layer in self.layers):
                return official.Structure3D([(self.layers[0]*0).tolist()])
            return original(self)
        official.Structure3D.normalize=normalize
        official.Structure3D._zero_array_fix=True
    return official, importlib.import_module('generate_3d_dataset_complete')

def prepare(cfg):
    official, gen = upstream()
    g=gen.Dataset3DGenerator(grid_size=cfg['grid_size'],max_blocks=max(cfg['blocks']),max_height=cfg['max_height'])
    g.generate_all_top_views(); g.generate_all_structures(); g.generate_observation_sets()
    ds={'metadata':{'grid_size':cfg['grid_size'],'max_height':cfg['max_height']},'observation_sets':g.observation_sets}
    save(ROOT/'data/3d.json',ds)
    rng=random.Random(cfg['split_seed']); splits={'dev':[], 'test':[]}
    for b in cfg['blocks']:
        pool=sorted([x['observation_id'] for x in g.observation_sets if x['observation'].count('1')==b])
        rng.shuffle(pool)
        splits['dev']+=pool[:cfg['dev_per_stratum']]
        splits['test']+=pool[cfg['dev_per_stratum']:cfg['dev_per_stratum']+cfg['test_per_stratum']]
    manifest={'dataset_sha256':digest(ds),'splits':splits,'protocol_sha256':digest(cfg)}
    save(ROOT/'methods/szh-baseline-3d-task-b/experiments/manifest.json',manifest)
    print('Prepared',len(g.observation_sets),'observations;',len(splits['test']),'test,',len(splits['dev']),'dev')
    return official

class RecordedClient:
    def __init__(self, cfg, mode, folder, obs, seed, method):
        self.cfg,self.mode,self.folder,self.obs=cfg,mode,folder,obs
        self.seed=seed; self.records=[]; self.method=method
        self.local=OllamaClient(cfg) if mode=='llm' else None
    def query_with_usage(self,prompt):
        q=len(self.records)
        if self.method:
            # Hook receives observation and past responses only, never enumerated answers.
            prompt=self.method(prompt, {'observation':self.obs['observation'],'query_index':q,
                'history':[r['response'] for r in self.records]})
        request=self.local.request(prompt,(self.seed+q)%2147483647) if self.local else {'prompt':prompt,'model':self.cfg['model']}
        path=self.folder/f'{q:04d}.json'; key=digest(request)
        if path.exists():
            record=json.loads(path.read_text(encoding='utf-8'))
            if record['request_sha256']!=key: raise RuntimeError('Cache prompt mismatch; use a new output directory')
        else:
            start=time.perf_counter()
            if self.mode=='offline':
                rng=random.Random(self.seed)
                # Advance by completed proposals so resumed offline runs are identical.
                for _ in range(q * self.obs['observation'].count('1')): rng.randint(1,self.cfg['max_height'])
                heights=[rng.randint(1,self.cfg['max_height']) if c=='1' else 0 for c in self.obs['observation']]
                rows=[]
                for z in range(max(heights)):
                    rows.append(f'Layer {z+1}:')
                    rows.extend(' '.join(str(int(h>z)) for h in heights[i:i+3]) for i in range(0,9,3))
                response='Structure:\n'+'\n'.join(rows); usage={'prompt_tokens':0,'completion_tokens':0,'total_tokens':0}; resolved_model='uniform-height-control'
            else:
                try:
                    generated=self.local.generate(request)
                except Exception as exc:
                    raise TransportAbort(f'Local model call failed ({type(exc).__name__}); resume saved run after fixing the service.') from None
                response=generated['response']; usage=generated['usage']; resolved_model=generated['resolved_model']
            record={'request_sha256':key,'request':request,'prompt':prompt,'response':response,'usage':usage,'resolved_model':resolved_model,'elapsed_s':time.perf_counter()-start}
            if self.local: record.update(generated)
            save(path,record)
        self.records.append(record)
        return {'response':record['response'],'usage':record['usage'],'cost':0.0}

class Replay:
    def __init__(self,records): self.it=iter(records)
    def query_with_usage(self,prompt): return next(self.it)

def main():
    p=argparse.ArgumentParser(); p.add_argument('--prepare',action='store_true'); p.add_argument('--config',default='methods/szh-baseline-3d-task-b/experiments/protocol.json')
    p.add_argument('--mode',choices=['offline','llm'],default='llm'); p.add_argument('--smoke',action='store_true'); p.add_argument('--smoke-index',type=int,default=0); p.add_argument('--split',choices=['dev','test'],default='test')
    p.add_argument('--out',default='runs/baseline'); p.add_argument('--method',help='Python module:function prompt hook')
    args=p.parse_args(); cfg=json.loads((ROOT/args.config).read_text(encoding='utf-8'))
    if args.prepare: prepare(cfg); return
    off,_=upstream(); manifest=json.loads((ROOT/'methods/szh-baseline-3d-task-b/experiments/manifest.json').read_text(encoding='utf-8'))
    ds=json.loads((ROOT/'data/3d.json').read_text(encoding='utf-8')); assert digest(ds)==manifest['dataset_sha256']
    assert digest(cfg)==manifest['protocol_sha256'], 'Run --prepare after intentional protocol changes'
    fingerprint=OllamaClient(cfg).fingerprint() if args.mode=='llm' else None
    cfg['model']=cfg['model'] if args.mode=='llm' else 'uniform-height-control'
    chosen=[x for x in ds['observation_sets'] if x['observation_id'] in manifest['splits'][args.split]]
    if args.smoke:
        chosen=[next(x for x in ds['observation_sets'] if x['observation_id']==[i for i in manifest['splits']['dev'] if f'_b{b}_' in i][args.smoke_index]) for b in cfg['blocks']]
        cfg['repeat_seeds']=[cfg['repeat_seeds'][0]]
    calls=sum((3 if args.smoke else max(1,int(x['n_compatible_structures']*cfg['query_multiplier']))) for x in chosen)*len(cfg['repeat_seeds'])
    print('Planned local calls:',calls,flush=True)
    hook=None
    if args.method:
        mod,fn=args.method.split(':'); hook=getattr(importlib.import_module(mod),fn)
    out=ROOT/args.out; out.mkdir(parents=True,exist_ok=True)
    identity={'config':cfg,'mode':args.mode,'model_fingerprint':fingerprint,'smoke':args.smoke,'split':'dev-smoke' if args.smoke else args.split,'method':args.method or 'official-history', 'method_source_sha256':hashlib.sha256(Path(importlib.import_module(args.method.split(':')[0]).__file__).read_bytes()).hexdigest() if args.method else None, 'dataset_sha256':manifest['dataset_sha256']}
    if (out/'identity.json').exists():
        assert json.loads((out/'identity.json').read_text(encoding='utf-8'))==identity,'Output identity mismatch'
    save(out/'identity.json',identity)
    bench=off.Benchmark3D(str(ROOT/'data/3d.json')); results=[]; curves=[]
    for seed in cfg['repeat_seeds']:
        for obs in chosen:
            oid=obs['observation_id']; n=3 if args.smoke else max(1,int(obs['n_compatible_structures']*cfg['query_multiplier']))
            client=RecordedClient(cfg,args.mode,out/'raw'/str(seed)/oid,obs,seed+int(hashlib.sha256(oid.encode()).hexdigest()[:8],16),hook)
            # Official evaluator catches transport errors, so verify call count afterwards and fail instead of reporting a completed run.
            result=bench.evaluate_single_observation_set(client,obs,n_queries=n,verbose=False,max_retries=1)
            if len(client.records)!=n: raise RuntimeError('Incomplete API run; cached successful requests retained. Resume same command.')
            result.update(seed=seed,blocks=obs['observation'].count('1'))
            result.pop('cost',None) # upstream zero fallback is NOT a measured price
            result['truncated_count']=sum(r.get('done_reason')=='length' for r in client.records)
            result['latency_s']=sum(r['elapsed_s'] for r in client.records)
            result['strict_valid_count']=sum(1 for r in client.records if (s:=bench.parse_llm_response(r['response'])) is not None and s.height<=cfg['max_height'] and bench.validate_structure_matches_observations(s,obs['observation']))
            results.append(result)
            for k in range(1,n+1):
                v=bench.evaluate_single_observation_set(Replay(client.records[:k]),obs,n_queries=k,verbose=False,max_retries=1)
                curves.append({'seed':seed,'observation_id':oid,'blocks':result['blocks'],'k':k,**{m:v[m] for m in ['valid_rate','novelty_rate','recovery_rate']}})
            save(out/'partial.json',results)
            print(args.mode,seed,oid,'V/U/R',*[round(result[m],3) for m in ['valid_rate','novelty_rate','recovery_rate']],flush=True)
    summary={'schema_version':1,'identity':identity,'planned_calls':calls,'completed_calls':sum(r['n_queries'] for r in results),
             'source_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'src').glob('*.py')},'runner_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'python':platform.python_version(),'platform':platform.platform(),'cost_usd':0.0,
             'aggregate':{},'by_blocks':{},'results':results,'curves':curves}
    for label,subset in [('aggregate',results)]+[(str(b),[r for r in results if r['blocks']==b]) for b in cfg['blocks']]:
        stats={m:{'mean':float(np.mean([r[m] for r in subset])),'std':float(np.std([r[m] for r in subset],ddof=1)) if len(subset)>1 else None} for m in ['valid_rate','novelty_rate','recovery_rate']}
        if label=='aggregate': summary['aggregate']=stats
        else: summary['by_blocks'][label]=stats
    summary['resource_totals']={'calls':calls,'input_tokens':sum(r['token_usage']['prompt_tokens'] for r in results),'output_tokens':sum(r['token_usage']['completion_tokens'] for r in results),'model_call_seconds':sum(r['latency_s'] for r in results),'truncated_outputs':sum(r['truncated_count'] for r in results)}
    save(out/'summary.json',summary)
    print('Completed',calls,'calls;',out/'summary.json')
if __name__=='__main__': main()
