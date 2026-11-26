"""JSON summaries preserve metric changes while normalizing causal edge tuples."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiments'))
from audit_all_domains import JsonSummary
class AuditSummaryTests(unittest.TestCase):
 def test_json_edge_containers_match(self):
  self.assertTrue(JsonSummary({'edges':[['A','B']],'n_valid':1})=={'edges':[('A','B')],'n_valid':1})
 def test_metric_difference_is_rejected(self):
  self.assertFalse(JsonSummary({'edges':[['A','B']],'n_valid':1})=={'edges':[('A','B')],'n_valid':2})
if __name__=='__main__':unittest.main()
