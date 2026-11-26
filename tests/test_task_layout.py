"""Path-only relocation regression tests; no model calls."""
import sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'experiments'))
from integration_paths import MAPPING,RelocatedRoot
class LayoutTests(unittest.TestCase):
 def test_all_compatibility_destinations_exist(self):
  for old,new in MAPPING.items():self.assertTrue((ROOT/new).exists(),(old,new))
 def test_historical_transport_uses_one_common_implementation(self):
  self.assertEqual(RelocatedRoot()/'src/ollama_client.py',ROOT/'methods/common/szh-baseline-common/compat/ollama_client.py')
if __name__=='__main__':unittest.main()
