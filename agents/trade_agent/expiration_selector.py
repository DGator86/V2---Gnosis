# agents/trade_agent/expiration_selector.py

from __future__ import annotations

from datetime import date, timedelta

from .schemas import ComposerTradeContext, Timeframe


def select_expiry(ctx: ComposerTradeContext) -> str:
    """
    Deterministic timeframe → expiry mapping.
    For now: uses calendar days; in production, map to real option expiries.
    """
    today = date.today()

    if ctx.timeframe == Timeframe.INTRADAY:
        offset = 0  # 0DTE
    elif ctx.timeframe == Timeframe.SWING:
        offset = 5  # about one week
    else:
        offset = 14  # ~two weeks

    expiry_date = today + timedelta(days=offset)
    return expiry_date.isoformat()
