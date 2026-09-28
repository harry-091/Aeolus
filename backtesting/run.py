"""CLI runner for python -m backtesting.run
Executes offline backtesting of PolarNav route optimizer against historical AIS tracks.
"""

import sys
from pathlib import Path

# Add backend directory to sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from run_offline_backtest import main

if __name__ == "__main__":
    main()
