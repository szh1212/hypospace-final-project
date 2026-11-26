import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from hypospace_runner import upstream
import coverage_guided as cg
m,_=upstream()
P=object.__new__(m.Benchmark3D)
OBS='010010000'  # cells 1 and 4 occupied -> 3^2 = 9 compatible structures
Z='0 0 0\n0 0 0\n0 0 0'
C1='0 1 0\n0 0 0\n0 0 0'
C4='0 0 0\n0 1 0\n0 0 0'
BOTH='0 1 0\n0 1 0\n0 0 0'
L2=lambda a,b: f'Structure:\nLayer 1:\n{a}\nLayer 2:\n{b}'
L3=lambda a,b,c: f'Structure:\nLayer 1:\n{a}\nLayer 2:\n{b}\nLayer 3:\n{c}'
VALID_two=L2(BOTH,C1)     # cell1 height 2, cell4 height 1
VALID_three=L3(BOTH,C1,C1)
FLOATING=L3(C1,Z,C1)      # top block without support
PARTIAL=L2(C1,Z)          # one cell but two observed
def ctx(history,obs=OBS): return {'observation':obs,'query_index':len(history),'history':list(history)}
class CoverageGuidedTests(unittest.TestCase):
    def test_heights_are_the_column_sums(self):
        self.assertEqual(cg.heights_of(VALID_two,OBS,P),(0,2,0,0,1,0,0,0,0))
        self.assertEqual(cg.heights_of(VALID_three,OBS,P),(0,3,0,0,1,0,0,0,0))
    def test_unsupported_block_is_not_coverage(self):
        self.assertIsNone(cg.heights_of(FLOATING,OBS,P))
    def test_projection_mismatch_is_not_coverage(self):
        self.assertIsNone(cg.heights_of(PARTIAL,OBS,P))
    def test_unparseable_is_not_coverage(self):
        self.assertIsNone(cg.heights_of('I would rather not.',OBS,P))
    def test_denominator_is_three_to_the_occupied_cells(self):
        self.assertIn('1 of 9 compatible structures',cg.transform('p',ctx([VALID_two])))
        self.assertIn('1 of 3 compatible structures',cg.transform('p',ctx([L2('0 0 1\n0 0 0\n0 0 0',Z)],obs='001000000')))
    def test_duplicates_and_invalid_do_not_inflate_coverage(self):
        out=cg.transform('p',ctx([VALID_two,VALID_two,FLOATING,PARTIAL,'bad']))
        self.assertIn('1 of 9 compatible structures',out)
        self.assertIn('2 of 9 compatible structures',cg.transform('p',ctx([VALID_two,VALID_three])))
    def test_report_never_states_a_candidate_structure(self):
        # The baseline prompt legitimately shows the top view; only the appended
        # suffix is the hook's own text, and it must not contain a whole proposal.
        from adapted_baseline import transform as base_transform
        c=ctx([VALID_two])
        out=cg.transform('p',c); base=base_transform('p',c)
        self.assertTrue(out.startswith(base))
        for line in out[len(base):].splitlines():
            fields=line.split()
            if len(fields)==3 and all(f in ('0','1') for f in fields):
                self.fail(f'report contains a structure row: {line!r}')
    def test_transform_is_pure(self):
        c=ctx([VALID_two,VALID_three])
        a=cg.transform('p',c); b=cg.transform('p',c)
        self.assertEqual(a,b)
        self.assertEqual(c['history'],[VALID_two,VALID_three])
    def test_ablations_are_distinguishable(self):
        c=ctx([VALID_two])
        full=cg.transform('p',c); stats=cg.transform_stats_only('p',c); cells=cg.transform_cells_only('p',c)
        self.assertIn('1 of 9',full); self.assertIn('Heights already used',full)
        self.assertNotIn('Heights already used',stats)
        self.assertNotIn('of 9 compatible',cells)
if __name__=='__main__': unittest.main()
