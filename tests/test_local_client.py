import os,sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from ollama_client import OllamaClient
class LocalClientTests(unittest.TestCase):
    def test_external_hosts_rejected(self):
        for host in ['https://api.anthropic.com','http://example.org:11434','http://secret@localhost:11434']:
            with patch.dict(os.environ,{'OLLAMA_BASE_URL':host}):
                with self.assertRaises(ValueError): OllamaClient({})
    def test_explicit_sampling_and_seed(self):
        c=dict(model='local',system='system',temperature=.7,top_p=.9,top_k=40,repeat_penalty=1,num_ctx=8192,num_thread=4,num_gpu=0,max_tokens=512)
        with patch.dict(os.environ,{'OLLAMA_BASE_URL':'http://localhost:11434'}):
            request=OllamaClient(c).request('task',123)
        self.assertEqual(request['options']['seed'],123)
        self.assertEqual(request['options']['num_predict'],512)
        self.assertEqual(request['messages'][-1]['content'],'task')
        self.assertFalse(request['stream'])
if __name__=='__main__': unittest.main()
