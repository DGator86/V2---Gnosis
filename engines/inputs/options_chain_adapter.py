from __future__ import annotations

"""Options chain adapter interface."""

from datetime import datetime
from typing import Protocol

import polars as pl


class OptionsChainAdapter(Protocol):
    """Protocol describing an options chain data source."""

    def fetch_chain(self, symbol: str, now: datetime) -> pl.DataFrame:
        """Return a normalized options chain for ``symbol``."""

        raise NotImplementedError
