from __future__ import annotations

"""Backtest runner skeleton."""

from datetime import datetime
from typing import Any, Callable, Dict


class BacktestRunner:
    """Event-driven backtest wrapper around the pipeline."""

    def __init__(self, pipeline_factory: Callable[[str], Any], data_source: Any, config: Dict[str, Any]) -> None:
        self.pipeline_factory = pipeline_factory
        self.data_source = data_source
        self.config = config

    def run_backtest(self, symbol: str, start: datetime, end: datetime) -> Dict[str, float]:
        return {"sharpe": 0.0, "hit_rate": 0.0}
