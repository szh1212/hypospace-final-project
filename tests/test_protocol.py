import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from hypospace_runner import upstream, Replay
m,_=upstream()
class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.b=object.__new__(m.Benchmark3D); self.b.metadata={'max_height':3}
        self.obs={'observation_id':'fixture','observation':'100000000','ground_truth_structures':[{'layers':['100000000']},{'layers':['100000000','100000000']},{'layers':['100000000']*3}]}
    def test_denominators_include_parse_failure_and_invalid_unique(self):
        texts=['Structure:\nLayer 1:\n1 0 0\n0 0 0\n0 0 0']*2+['bad output','Structure:\nLayer 1:\n0 1 0\n0 0 0\n0 0 0']
        result=self.b.evaluate_single_observation_set(Replay([{'response':t} for t in texts]),self.obs,n_queries=4,max_retries=1,verbose=False)
        self.assertEqual(result['valid_rate'],.5); self.assertEqual(result['novelty_rate'],.5); self.assertEqual(result['recovery_rate'],1/3)
    def test_trailing_zero_layers_are_equivalent(self):
        a=m.Structure3D([[[1,0,0],[0,0,0],[0,0,0]]]); b=m.Structure3D([a.layers[0].tolist(),[[0]*3]*3])
        self.assertEqual(a.get_hash(),b.get_hash())
    def test_floating_voxel_invalid(self):
        s=m.Structure3D([[[0]*3]*3,[[1,0,0],[0,0,0],[0,0,0]]])
        self.assertFalse(self.b.validate_structure_matches_observations(s,self.obs['observation']))
    def test_upstream_height_limit_gap_is_documented(self):
        s=m.Structure3D([[[1,0,0],[0,0,0],[0,0,0]]]*4)
        self.assertTrue(self.b.validate_structure_matches_observations(s,self.obs['observation']))
        self.assertGreater(s.height,self.b.metadata['max_height'])
if __name__=='__main__': unittest.main()
