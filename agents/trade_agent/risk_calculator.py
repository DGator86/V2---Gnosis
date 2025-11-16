# agents/trade_agent/risk_calculator.py

from __future__ import annotations

from typing import Iterable, List

from .schemas import ComposerTradeContext, TradeIdea
from .sizing_engine import SizingConfig, SizingEngine


def apply_risk_and_sizing(
    ideas: Iterable[TradeIdea],
    ctx: ComposerTradeContext,
    capital: float,
) -> List[TradeIdea]:
    """
    Backwards-compatible wrapper around the new SizingEngine.

    - Uses capital as max_capital
    - Leaves existing_portfolio_risk at 0.0 (stateless)
    """

    cfg = SizingConfig(max_capital=float(capital))
    engine = SizingEngine(cfg)

    return engine.size_ideas(list(ideas), ctx, existing_portfolio_risk=0.0)
