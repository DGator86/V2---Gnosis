# agents/trade_agent/stock_strategies.py

from __future__ import annotations

from typing import List

from .schemas import (
    ComposerTradeContext,
    TradeIdea,
    StrategyType,
)


def build_stock_trade_idea(ctx: ComposerTradeContext) -> TradeIdea:
    """
    Pure function: generates a single stock trade idea from context.
    No sizing, no state, no Greeks logic beyond description.
    """
    desc_dir = ctx.direction.value.upper()
    description = (
        f"{desc_dir} stock idea based on composer confidence={ctx.confidence:.2f}, "
        f"expected_move={ctx.expected_move.value}, vol_regime={ctx.volatility_regime.value}."
    )

    # Target / stop are relative scalars; risk calculator will refine as needed
    target_price_scalar = _target_scalar_from_expected_move(ctx)
    stop_loss_scalar = _stop_scalar_from_expected_move(ctx)

    return TradeIdea(
        asset=ctx.asset,
        strategy_type=StrategyType.STOCK,
        description=description,
        target_price=target_price_scalar * ctx.elastic_energy,
        stop_loss=stop_loss_scalar * ctx.elastic_energy,
        timeframe=ctx.timeframe,
        confidence=ctx.confidence,
    )


def _target_scalar_from_expected_move(ctx: ComposerTradeContext) -> float:
    mapping = {
        "small": 0.5,
        "medium": 1.0,
        "large": 2.0,
        "explosive": 4.0,
    }
    return mapping[ctx.expected_move.value]


def _stop_scalar_from_expected_move(ctx: ComposerTradeContext) -> float:
    # Slightly tighter scalar than target; adjust later if needed
    mapping = {
        "small": 0.25,
        "medium": 0.5,
        "large": 1.0,
        "explosive": 1.5,
    }
    return mapping[ctx.expected_move.value]
