"""Scoring regression fixtures, never experimental outputs."""
import importlib.util,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'methods/common/szh-baseline-common'))
sys.path.insert(0,str(ROOT/"src"))
import run
sys.path.insert(0,str(ROOT/"experiments"))
from integration_paths import configure
configure(run)
class DomainTests(unittest.TestCase):
    def test_causal_official_denominators_and_empty_graph(self):
        mod=run.official(ROOT.parent/'upstream-hypospace','causal')
        bench=mod.CausalBenchmarkEnhanced(str(ROOT/'data/baseline-all-domains/causal.json'))
        case=next(c for c in bench.all_observation_sets if c['observation_set_id']=='n1_017')
        def rec(s):return {'response':s,'usage':{'prompt_tokens':0,'completion_tokens':0,'total_tokens':0}}
        out=run.score(bench,case,[rec('Graph: No edges'),rec('Graph: No edges'),rec('bad!')])
        self.assertEqual(out['n_queries'],3);self.assertEqual(out['n_unique_all'],1)
        self.assertEqual(out['novelty_rate'],1/3)
        text=run.prompt(bench,case,[rec('Graph: No edges')],'causal')
        self.assertNotIn('ground_truth',text)
        self.assertIn('Graph: No edges',text)
    def test_boolean_mechanistic_identity_and_denominators(self):
        mod=run.official(ROOT.parent/'upstream-hypospace','genetic')
        bench=mod.BooleanBenchmarkRefined(str(ROOT/'data/baseline-all-domains/boolean-basic.json'))
        self.assertEqual(bench.get_expression_mechanistic_key('x AND y'),bench.get_expression_mechanistic_key('y AND x'))
        case=bench.all_observation_sets[0]
        rec=lambda s:{'response':s,'usage':{'prompt_tokens':0,'completion_tokens':0,'total_tokens':0}}
        out=run.score(bench,case,[rec('Expression: x'),rec('Expression: x'),rec('Expression: z')])
        self.assertEqual(out['n_queries'],3);self.assertEqual(out['n_unique_all'],1)
        self.assertEqual(len(run.history(bench,[rec('Expression: x'),rec('Expression: x')],'genetic')),1)
    def test_development_and_test_are_disjoint(self):
        cfg=run.read(ROOT/'methods/common/szh-baseline-common/protocol.json')
        for d in ['causal','genetic']:
            self.assertFalse(set(cfg[d]['splits']['dev']) & set(cfg[d]['splits']['test']))
        self.assertFalse(set(cfg['causal']['splits']['dev']) & set(cfg['causal']['aligned_test']))
if __name__=='__main__':unittest.main()
