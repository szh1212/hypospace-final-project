"""Local-only Ollama transport. No credentials, commercial providers or cloud fallback.

Copied verbatim from the SZH 3D baseline branch (src/ollama_client.py) so the
experimental conditions (request shape, options, endpoint policy) are identical
to the baseline run.
"""
import hashlib, json, os, time
from urllib.parse import urlparse
import requests

class OllamaClient:
    def __init__(self, config):
        self.config=config
        self.base=os.environ.get('OLLAMA_BASE_URL','http://localhost:11434').rstrip('/')
        u=urlparse(self.base)
        if u.scheme!='http' or u.hostname not in ('localhost','127.0.0.1','::1') or u.username or u.password:
            raise ValueError('Only a local, unauthenticated HTTP Ollama endpoint is permitted')
        self.session=requests.Session(); self.session.trust_env=False
    def fingerprint(self):
        version=self.session.get(self.base+'/api/version',timeout=10); version.raise_for_status()
        tags=self.session.get(self.base+'/api/tags',timeout=10); tags.raise_for_status()
        found=next((m for m in tags.json()['models'] if m['name']==self.config['model']),None)
        if found is None: raise ValueError('Pull the exact configured model tag first')
        show=self.session.post(self.base+'/api/show',json={'model':self.config['model']},timeout=30);show.raise_for_status()
        body=show.json()
        if body['details']['quantization_level']!=self.config['quantization']: raise ValueError('Quantization mismatch')
        if self.config.get('model_digest') and found['digest']!=self.config['model_digest']: raise ValueError('Model digest mismatch')
        if version.json()['version']!=self.config['ollama_version']: raise ValueError('Ollama version mismatch')
        return {'model':found['name'],'digest':found['digest'],'details':body['details'],'ollama_version':version.json()['version'],
                'template_sha256':hashlib.sha256(body.get('template','').encode()).hexdigest()}
    def request(self,prompt,seed):
        c=self.config
        return {'model':c['model'],'messages':[{'role':'system','content':c['system']},{'role':'user','content':prompt}],
                'stream':False,'keep_alive':'30m', 'options':{'seed':seed,'temperature':c['temperature'],'top_p':c['top_p'],
                'top_k':c['top_k'],'repeat_penalty':c['repeat_penalty'],'num_predict':c['max_tokens'],
                'num_ctx':c['num_ctx'],'num_thread':c['num_thread'],'num_gpu':c['num_gpu']}}
    def generate(self,request):
        start=time.perf_counter()
        res=self.session.post(self.base+'/api/chat',json=request,timeout=600);res.raise_for_status();b=res.json()
        if not b.get('done'): raise RuntimeError('Incomplete local response')
        usage={'prompt_tokens':b.get('prompt_eval_count',0),'completion_tokens':b.get('eval_count',0)}
        usage['total_tokens']=sum(usage.values())
        return {'response':b['message']['content'],'usage':usage,'resolved_model':b['model'],
                'elapsed_s':time.perf_counter()-start,'done_reason':b.get('done_reason'),
                'timing_ns':{k:b.get(k,0) for k in ['total_duration','load_duration','prompt_eval_duration','eval_duration']}}
