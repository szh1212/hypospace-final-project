"""Run the frozen A/C implementation with relocated artifact paths."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'methods/szh-baseline-common'))
import run
from integration_paths import configure
configure(run)
if __name__=='__main__':run.main()
