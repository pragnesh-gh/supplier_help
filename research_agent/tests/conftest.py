import sys
from pathlib import Path

# Allow `pytest research_agent/tests` from the repo root without installation.
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
