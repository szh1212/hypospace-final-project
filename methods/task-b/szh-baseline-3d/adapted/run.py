from pathlib import Path
import sys
ROOT=next(p for p in Path(__file__).resolve().parents if (p/'.git').exists())
sys.path.insert(0,str(ROOT/'src'))
from hypospace_runner import main
sys.argv+=['--method','adapted_baseline:transform']
if __name__=='__main__':main()
