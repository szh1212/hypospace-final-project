"""Pinned official evaluator + auditable transport and method prompt hooks."""
import argparse, hashlib, importlib, json, os, platform, random, subprocess, sys, time
from pathlib import Path
import numpy as np
import requests
ROOT = Path(__file__).resolve().parents[1]
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
    return importlib.import_module('run_3d_benchmark'), importlib.import_module('generate_3d_dataset_complete')

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
    save(ROOT/'experiments/manifest.json',manifest)
    print('Prepared',len(g.observation_sets),'observations;',len(splits['test']),'test,',len(splits['dev']),'dev')
    return official

class RecordedClient:
    def __init__(self, cfg, mode, folder, obs, seed, method):
        self.cfg,self.mode,self.folder,self.obs=cfg,mode,folder,obs
        self.seed=seed; self.records=[]; self.method=method
    def query_with_usage(self,prompt):
        q=len(self.records)
        if self.method:
            # Hook receives observation and past responses only, never enumerated answers.
            prompt=self.method(prompt, {'observation':self.obs['observation'],'query_index':q,
                'history':[r['response'] for r in self.records]})
        request={'model':self.cfg['model'],'temperature':self.cfg['temperature'],'max_tokens':self.cfg['max_tokens'],
                 'messages':[{'role':'user','content':prompt}]}
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
                base=os.environ.get('ANTHROPIC_BASE_URL','https://api.anthropic.com').rstrip('/')
                token=os.environ.get('ANTHROPIC_AUTH_TOKEN') or os.environ.get('ANTHROPIC_API_KEY')
                if not token: raise RuntimeError('Missing Anthropic credential environment variable')
                headers={'anthropic-version':'2023-06-01','content-type':'application/json'}
                headers['authorization' if os.environ.get('ANTHROPIC_AUTH_TOKEN') else 'x-api-key']=('Bearer '+token if os.environ.get('ANTHROPIC_AUTH_TOKEN') else token)
                try:
                    resp=requests.post(base+'/v1/messages',headers=headers,json=request,timeout=120)
                except requests.RequestException:
                    raise TransportAbort('API transport failed; stopped immediately. Cached calls retained.') from None
                if resp.status_code!=200: raise TransportAbort(f'API HTTP {resp.status_code}; stopped immediately. Cached calls retained.')
                body=resp.json(); response='\n'.join(c['text'] for c in body['content'] if c['type']=='text')
                u=body['usage']; usage={'prompt_tokens':u['input_tokens'],'completion_tokens':u['output_tokens'],'total_tokens':u['input_tokens']+u['output_tokens']}
                resolved_model=body.get('model',self.cfg['model'])
            record={'request_sha256':key,'prompt':prompt,'response':response,'usage':usage,'resolved_model':resolved_model,'elapsed_s':time.perf_counter()-start}
            save(path,record)
        self.records.append(record)
        return {'response':record['response'],'usage':record['usage'],'cost':0.0}

class Replay:
    def __init__(self,records): self.it=iter(records)
    def query_with_usage(self,prompt): return next(self.it)

def main():
    p=argparse.ArgumentParser(); p.add_argument('--prepare',action='store_true'); p.add_argument('--config',default='experiments/protocol.json')
    p.add_argument('--mode',choices=['offline','llm'],default='offline'); p.add_argument('--split',choices=['dev','test'],default='test')
    p.add_argument('--out',default='runs/offline'); p.add_argument('--method',help='Python module:function prompt hook')
    p.add_argument('--allow-api-calls',type=int,default=0,help='Explicit call budget; total planned calls must fit')
    args=p.parse_args(); cfg=json.loads((ROOT/args.config).read_text())
    if args.prepare: prepare(cfg); return
    off,_=upstream(); manifest=json.loads((ROOT/'experiments/manifest.json').read_text())
    ds=json.loads((ROOT/'data/3d.json').read_text()); assert digest(ds)==manifest['dataset_sha256']
    assert digest(cfg)==manifest['protocol_sha256'], 'Run --prepare after intentional protocol changes'
    model=cfg['model'] or os.environ.get('ANTHROPIC_MODEL')
    if args.mode=='llm' and not (os.environ.get('ANTHROPIC_AUTH_TOKEN') or os.environ.get('ANTHROPIC_API_KEY')): raise ValueError('Missing API credential environment variable')
    if args.mode=='llm' and not model: raise ValueError('Set explicit model in config or ANTHROPIC_MODEL')
    cfg['model']=model if args.mode=='llm' else 'uniform-height-control'
    chosen=[x for x in ds['observation_sets'] if x['observation_id'] in manifest['splits'][args.split]]
    calls=sum(max(1,int(x['n_compatible_structures']*cfg['query_multiplier'])) for x in chosen)*len(cfg['repeat_seeds'])
    if args.mode=='llm' and args.allow_api_calls<calls: raise ValueError(f'Planned {calls} calls; pass --allow-api-calls {calls} after budget approval')
    hook=None
    if args.method:
        mod,fn=args.method.split(':'); hook=getattr(importlib.import_module(mod),fn)
    out=ROOT/args.out; out.mkdir(parents=True,exist_ok=True)
    identity={'config':cfg,'mode':args.mode,'split':args.split,'method':args.method or 'official-history', 'method_source_sha256':hashlib.sha256(Path(importlib.import_module(args.method.split(':')[0]).__file__).read_bytes()).hexdigest() if args.method else None, 'dataset_sha256':manifest['dataset_sha256']}
    if (out/'identity.json').exists():
        assert json.loads((out/'identity.json').read_text())==identity,'Output identity mismatch'
    save(out/'identity.json',identity)
    bench=off.Benchmark3D(str(ROOT/'data/3d.json')); results=[]; curves=[]
    for seed in cfg['repeat_seeds']:
        for obs in chosen:
            oid=obs['observation_id']; n=max(1,int(obs['n_compatible_structures']*cfg['query_multiplier']))
            client=RecordedClient(cfg,args.mode,out/'raw'/str(seed)/oid,obs,seed+int(hashlib.sha256(oid.encode()).hexdigest()[:8],16),hook)
            # Official evaluator catches transport errors, so verify call count afterwards and fail instead of reporting a completed run.
            result=bench.evaluate_single_observation_set(client,obs,n_queries=n,verbose=False,max_retries=1)
            if len(client.records)!=n: raise RuntimeError('Incomplete API run; cached successful requests retained. Resume same command.')
            result.update(seed=seed,blocks=obs['observation'].count('1'))
            result.pop('cost',None) # upstream zero fallback is NOT a measured price
            result['latency_s']=sum(r['elapsed_s'] for r in client.records)
            result['strict_valid_count']=sum(1 for r in client.records if (s:=bench.parse_llm_response(r['response'])) is not None and s.height<=cfg['max_height'] and bench.validate_structure_matches_observations(s,obs['observation']))
            results.append(result)
            for k in range(1,n+1):
                v=bench.evaluate_single_observation_set(Replay(client.records[:k]),obs,n_queries=k,verbose=False,max_retries=1)
                curves.append({'seed':seed,'observation_id':oid,'blocks':result['blocks'],'k':k,**{m:v[m] for m in ['valid_rate','novelty_rate','recovery_rate']}})
            save(out/'partial.json',results)
            print(args.mode,seed,oid,'V/U/R',*[round(result[m],3) for m in ['valid_rate','novelty_rate','recovery_rate']],flush=True)
    summary={'schema_version':1,'identity':identity,'planned_calls':calls,'completed_calls':sum(r['n_queries'] for r in results),
             'runner_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'python':platform.python_version(),'platform':platform.platform(),'cost_usd':None,
             'aggregate':{},'by_blocks':{},'results':results,'curves':curves}
    for label,subset in [('aggregate',results)]+[(str(b),[r for r in results if r['blocks']==b]) for b in cfg['blocks']]:
        stats={m:{'mean':float(np.mean([r[m] for r in subset])),'std':float(np.std([r[m] for r in subset],ddof=1))} for m in ['valid_rate','novelty_rate','recovery_rate']}
        if label=='aggregate': summary['aggregate']=stats
        else: summary['by_blocks'][label]=stats
    save(out/'summary.json',summary)
    print('Completed',calls,'calls;',out/'summary.json')
if __name__=='__main__': main()
