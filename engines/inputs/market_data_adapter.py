from __future__ import annotations

"""Market data adapter interfaces."""

from datetime import datetime
from typing import Protocol

import polars as pl


class MarketDataAdapter(Protocol):
    """Protocol describing access to market data feeds."""

    def fetch_ohlcv(self, symbol: str, lookback: int, now: datetime) -> pl.DataFrame:
        """Return OHLCV data for ``symbol``."""

        raise NotImplementedError

    def fetch_intraday_trades(self, symbol: str, lookback_minutes: int, now: datetime) -> pl.DataFrame:
        """Return intraday trade data for ``symbol``."""

        raise NotImplementedError
