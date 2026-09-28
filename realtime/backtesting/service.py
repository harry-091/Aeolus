"""POLARNAV — Phase 13: Offline Backtest Service.

Provides singleton access to the offline historical backtest engine.
"""

from typing import List, Dict, Any, Optional
from .engine import OfflineHistoricalBacktestEngine
from .models import HistoricalVoyageMetadata, HistoricalBacktestResult


class OfflineBacktestService:
    """Service wrapper for offline historical voyage backtesting."""

    def __init__(self):
        self._engine: Optional[OfflineHistoricalBacktestEngine] = None

    @property
    def engine(self) -> OfflineHistoricalBacktestEngine:
        if self._engine is None:
            self._engine = OfflineHistoricalBacktestEngine()
        return self._engine

    def list_voyages(self) -> List[HistoricalVoyageMetadata]:
        """Return catalog of available historical Antarctic voyages."""
        return self.engine.get_available_voyages()

    def run_backtest(
        self,
        voyage_id: str,
        polar_class: str = "PC5",
        speed_knots: float = 14.0,
        draft_m: float = 8.0,
        beam_m: float = 20.0,
        length_m: float = 104.0,
    ) -> HistoricalBacktestResult:
        """Run complete prospective backtest on selected historical voyage."""
        return self.engine.run_backtest(
            voyage_id=voyage_id,
            polar_class=polar_class,
            speed_knots=speed_knots,
            draft_m=draft_m,
            beam_m=beam_m,
            length_m=length_m,
        )


# Global singleton service
offline_backtest_service = OfflineBacktestService()
