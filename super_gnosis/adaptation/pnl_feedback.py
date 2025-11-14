"""PNL feedback mechanisms for adaptation layer."""

from __future__ import annotations

from typing import Protocol


class PnLFeedbackStrategy(Protocol):
    """Protocol describing how realized PnL feeds into adaptations."""

    def update(self, realized_pnl: float) -> None:
        ...
