import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from capture_enclosure import ripple_cover_print
ripple_cover_print()
