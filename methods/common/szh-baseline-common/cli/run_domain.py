"""Run the frozen A/C implementation with relocated artifact paths."""
import sys
from pathlib import Path
_REPO=next(p for p in Path(__file__).resolve().parents if (p/".git").exists())
sys.path[:0]=[str(_REPO/"src"),str(_REPO/"experiments")]

sys.path.insert(0,str(next(p for p in Path(__file__).resolve().parents if (p / ".git").exists())/'methods/common/szh-baseline-common'))
import run
from integration_paths import configure
configure(run)
if __name__=='__main__':run.main()
