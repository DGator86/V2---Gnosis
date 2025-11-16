# agents/trade_agent/options_strategies.py

from __future__ import annotations

from typing import List

from .expiration_selector import select_expiry
from .schemas import (
    ComposerTradeContext,
    OptionLeg,
    StrategyGreeks,
    StrategyType,
    TradeIdea,
)


# --------- Core directional strategies --------- #


def build_long_call(ctx: ComposerTradeContext, underlying_price: float) -> TradeIdea:
    expiry = select_expiry(ctx)
    strike = _choose_directional_strike(
        underlying_price=underlying_price,
        direction="call",
        ctx=ctx,
    )

    leg = OptionLeg(
        side="long",
        option_type="call",
        strike=strike,
        expiry=expiry,
        quantity=1,
    )

    desc = (
        f"Long call targeting {ctx.expected_move.value} move in a "
        f"{ctx.volatility_regime.value} regime. "
        f"Expiry={expiry}, strike≈{strike:.2f}."
    )

    return TradeIdea(
        asset=ctx.asset,
        strategy_type=StrategyType.LONG_CALL,
        description=desc,
        legs=[leg],
        timeframe=ctx.timeframe,
        confidence=ctx.confidence,
        greeks_profile=StrategyGreeks(
            delta=0.6,
            gamma=0.3,
            theta=-0.6,
            vega=0.7,
        ),
    )


def build_long_put(ctx: ComposerTradeContext, underlying_price: float) -> TradeIdea:
    expiry = select_expiry(ctx)
    strike = _choose_directional_strike(
        underlying_price=underlying_price,
        direction="put",
        ctx=ctx,
    )

    leg = OptionLeg(
        side="long",
        option_type="put",
        strike=strike,
        expiry=expiry,
        quantity=1,
    )

    desc = (
        f"Long put targeting {ctx.expected_move.value} downside move in "
        f"{ctx.volatility_regime.value} regime. Expiry={expiry}, strike≈{strike:.2f}."
    )

    return TradeIdea(
        asset=ctx.asset,
        strategy_type=StrategyType.LONG_PUT,
        description=desc,
        legs=[leg],
        timeframe=ctx.timeframe,
        confidence=ctx.confidence,
        greeks_profile=StrategyGreeks(
            delta=-0.6,
            gamma=0.3,
            theta=-0.6,
            vega=0.7,
        ),
    )


def build_call_debit_spread(
    ctx: ComposerTradeContext,
    underlying_price: float,
) -> TradeIdea:
    expiry = select_expiry(ctx)

    lower, upper = _vertical_strikes(underlying_price, "call", ctx)

    long_leg = OptionLeg(
        side="long",
        option_type="call",
        strike=lower,
        expiry=expiry,
        quantity=1,
    )
    short_leg = OptionLeg(
        side="short",
        option_type="call",
        strike=upper,
        expiry=expiry,
        quantity=1,
    )

    desc = (
        "Bullish call debit spread to capture upside while capping risk. "
        f"Long {lower:.2f}C / Short {upper:.2f}C, expiry={expiry}."
    )

    return TradeIdea(
        asset=ctx.asset,
        strategy_type=StrategyType.CALL_DEBIT_SPREAD,
        description=desc,
        legs=[long_leg, short_leg],
        timeframe=ctx.timeframe,
        confidence=ctx.confidence,
        greeks_profile=StrategyGreeks(
            delta=0.35,
            gamma=0.2,
            theta=-0.2,
            vega=0.3,
        ),
    )


def build_put_debit_spread(
    ctx: ComposerTradeContext,
    underlying_price: float,
) -> TradeIdea:
    expiry = select_expiry(ctx)

    lower, upper = _vertical_strikes(underlying_price, "put", ctx)

    long_leg = OptionLeg(
        side="long",
        option_type="put",
        strike=upper,
        expiry=expiry,
        quantity=1,
    )
    short_leg = OptionLeg(
        side="short",
        option_type="put",
        strike=lower,
        expiry=expiry,
        quantity=1,
    )

    desc = (
        "Bearish put debit spread to capture downside with defined risk. "
        f"Long {upper:.2f}P / Short {lower:.2f}P, expiry={expiry}."
    )

    return TradeIdea(
        asset=ctx.asset,
        strategy_type=StrategyType.PUT_DEBIT_SPREAD,
        description=desc,
        legs=[long_leg, short_leg],
        timeframe=ctx.timeframe,
        confidence=ctx.confidence,
        greeks_profile=StrategyGreeks(
            delta=-0.35,
            gamma=0.2,
            theta=-0.2,
            vega=0.3,
        ),
    )


# --------- Neutral / vol strategies --------- #


def build_iron_condor(
    ctx: ComposerTradeContext,
    underlying_price: float,
) -> TradeIdea:
    expiry = select_expiry(ctx)

    wings = _iron_condor_wings(underlying_price, ctx)

    short_put, long_put, short_call, long_call = wings

    desc = (
        "Market-neutral iron condor targeting range-bound price action. "
        f"Short {short_put.strike:.2f}P / Long {long_put.strike:.2f}P / "
        f"Short {short_call.strike:.2f}C / Long {long_call.strike:.2f}C, "
        f"expiry={expiry}."
    )

    return TradeIdea(
        asset=ctx.asset,
        strategy_type=StrategyType.IRON_CONDOR,
        description=desc,
        legs=[short_put, long_put, short_call, long_call],
        timeframe=ctx.timeframe,
        confidence=ctx.confidence,
        greeks_profile=StrategyGreeks(
            delta=0.0,
            gamma=-0.1,
            theta=0.6,
            vega=-0.4,
        ),
    )


def build_straddle(ctx: ComposerTradeContext, underlying_price: float) -> TradeIdea:
    expiry = select_expiry(ctx)
    k = round(underlying_price)  # ATM approximation

    long_call = OptionLeg(
        side="long",
        option_type="call",
        strike=k,
        expiry=expiry,
        quantity=1,
    )
    long_put = OptionLeg(
        side="long",
        option_type="put",
        strike=k,
        expiry=expiry,
        quantity=1,
    )

    desc = (
        "Long straddle for large move in either direction under vol expansion. "
        f"ATM strikes at {k:.2f}, expiry={expiry}."
    )

    return TradeIdea(
        asset=ctx.asset,
        strategy_type=StrategyType.STRADDLE,
        description=desc,
        legs=[long_call, long_put],
        timeframe=ctx.timeframe,
        confidence=ctx.confidence,
        greeks_profile=StrategyGreeks(
            delta=0.0,
            gamma=0.5,
            theta=-0.9,
            vega=0.9,
        ),
    )


def build_strangle(ctx: ComposerTradeContext, underlying_price: float) -> TradeIdea:
    expiry = select_expiry(ctx)

    call_strike = underlying_price * 1.02
    put_strike = underlying_price * 0.98

    long_call = OptionLeg(
        side="long",
        option_type="call",
        strike=call_strike,
        expiry=expiry,
        quantity=1,
    )
    long_put = OptionLeg(
        side="long",
        option_type="put",
        strike=put_strike,
        expiry=expiry,
        quantity=1,
    )

    desc = (
        "Long strangle: OTM call and put to capture large move with lower premium "
        f"than straddle. Expiry={expiry}."
    )

    return TradeIdea(
        asset=ctx.asset,
        strategy_type=StrategyType.STRANGLE,
        description=desc,
        legs=[long_call, long_put],
        timeframe=ctx.timeframe,
        confidence=ctx.confidence,
        greeks_profile=StrategyGreeks(
            delta=0.0,
            gamma=0.4,
            theta=-0.7,
            vega=0.8,
        ),
    )


# --------- Helpers --------- #


def _choose_directional_strike(
    underlying_price: float,
    direction: str,
    ctx: ComposerTradeContext,
) -> float:
    # Simple heuristic: higher confidence → closer to ATM
    moneyness = 0.02 * (1.0 - ctx.confidence)  # 0–2% OTM by default

    if direction == "call":
        return underlying_price * (1.0 + moneyness)
    else:
        return underlying_price * (1.0 - moneyness)


def _vertical_strikes(
    underlying_price: float,
    option_kind: str,
    ctx: ComposerTradeContext,
) -> tuple[float, float]:
    """
    Returns (lower_strike, upper_strike) for verticals.
    For calls: lower=long, upper=short.
    For puts: lower=short, upper=long.
    """
    width = 0.02  # 2% wide spread baseline; can be tuned by vol later

    if option_kind == "call":
        lower = underlying_price * 1.0
        upper = underlying_price * (1.0 + width)
    else:
        lower = underlying_price * (1.0 - width)
        upper = underlying_price * 1.0

    return lower, upper


def _iron_condor_wings(
    underlying_price: float,
    ctx: ComposerTradeContext,
) -> tuple[OptionLeg, OptionLeg, OptionLeg, OptionLeg]:
    expiry = select_expiry(ctx)

    wing_width = 0.04
    body_width = 0.02

    short_put_k = underlying_price * (1.0 - body_width)
    long_put_k = underlying_price * (1.0 - wing_width)
    short_call_k = underlying_price * (1.0 + body_width)
    long_call_k = underlying_price * (1.0 + wing_width)

    short_put = OptionLeg(
        side="short",
        option_type="put",
        strike=short_put_k,
        expiry=expiry,
        quantity=1,
    )
    long_put = OptionLeg(
        side="long",
        option_type="put",
        strike=long_put_k,
        expiry=expiry,
        quantity=1,
    )
    short_call = OptionLeg(
        side="short",
        option_type="call",
        strike=short_call_k,
        expiry=expiry,
        quantity=1,
    )
    long_call = OptionLeg(
        side="long",
        option_type="call",
        strike=long_call_k,
        expiry=expiry,
        quantity=1,
    )

    return short_put, long_put, short_call, long_call
