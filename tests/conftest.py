"""Pytest configuration and session initialization for PolarNav backend test suite."""
import sys
from pathlib import Path

# Add backend, backend/src, and root to sys.path for unified import resolution
BACKEND_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BACKEND_DIR.parent

for p in [str(BACKEND_DIR), str(BACKEND_DIR / "src"), str(ROOT_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

# Pre-import scikit-learn ensemble and forest to eliminate Python 3.14 module lock deadlock
try:
    import sklearn.ensemble._forest
    import sklearn.ensemble
except ImportError:
    pass
