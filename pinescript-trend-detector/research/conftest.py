"""Put the harness package on sys.path so tests run from any directory.

Without this, `pytest research/tests/` from the repo root fails to import
`pgt` while `pytest tests/` from inside research/ works — a confusing
difference to hit when you are just trying to check the thing still passes.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
