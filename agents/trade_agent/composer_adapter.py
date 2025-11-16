# agents/trade_agent/composer_adapter.py

"""
Adapter to convert CompositeMarketDirective to ComposerTradeContext.

Maps Composer output to Trade Agent input format, filling in reasonable
defaults where direct mappings don't exist.
"""

from __future__ import annotations

from agents.composer.schemas import CompositeMarketDirective
from .schemas import (
    ComposerTradeContext,
    Direction,
    ExpectedMove,
    Timeframe,
    VolatilityRegime,
)


def directive_to_context(
    directive: CompositeMarketDirective,
    asset: str,
    timeframe: Timeframe | None = None,
) -> ComposerTradeContext:
    """
    Convert CompositeMarketDirective to ComposerTradeContext.
    
    Args:
        directive: Output from ComposerAgent
        asset: Symbol (not in directive, must be provided)
        timeframe: Optional timeframe override (defaults to SWING)
        
    Returns:
        ComposerTradeContext ready for Trade Agent
    """
    
    # Map direction literal [-1, 0, 1] to Direction enum
    if directive.direction > 0:
        direction = Direction.BULLISH
    elif directive.direction < 0:
        direction = Direction.BEARISH
    else:
        direction = Direction.NEUTRAL
    
    # Map strength [0-100] to expected move category
    expected_move = _strength_to_expected_move(directive.strength, directive.confidence)
    
    # Map volatility [0-100] to volatility regime
    volatility_regime = _volatility_to_regime(directive.volatility, directive.trade_style)
    
    # Default timeframe based on trade style
    if timeframe is None:
        timeframe = _trade_style_to_timeframe(directive.trade_style)
    
    # Extract Greeks from raw_engines if available
    gamma_exposure, vanna_exposure, charm_exposure = _extract_greeks(directive)
    
    # Liquidity score: extract from raw engines or default to mid-range
    liquidity_score = _extract_liquidity_score(directive)
    
    return ComposerTradeContext(
        asset=asset,
        direction=direction,
        confidence=directive.confidence,
        expected_move=expected_move,
        volatility_regime=volatility_regime,
        timeframe=timeframe,
        elastic_energy=directive.energy_cost,
        gamma_exposure=gamma_exposure,
        vanna_exposure=vanna_exposure,
        charm_exposure=charm_exposure,
        liquidity_score=liquidity_score,
    )


def _strength_to_expected_move(strength: float, confidence: float) -> ExpectedMove:
    """Map strength [0-100] and confidence to expected move category."""
    # Combine strength and confidence for more accurate classification
    weighted_strength = strength * confidence
    
    if weighted_strength >= 60:
        return ExpectedMove.EXPLOSIVE
    elif weighted_strength >= 40:
        return ExpectedMove.LARGE
    elif weighted_strength >= 20:
        return ExpectedMove.MEDIUM
    else:
        return ExpectedMove.SMALL


def _volatility_to_regime(volatility: float, trade_style: str) -> VolatilityRegime:
    """Map volatility [0-100] and trade style to volatility regime."""
    
    # Check trade style for explicit vol signals
    if "breakout" in trade_style.lower():
        return VolatilityRegime.VOL_EXPANSION
    
    # Otherwise use volatility level
    if volatility >= 70:
        return VolatilityRegime.HIGH
    elif volatility >= 50:
        return VolatilityRegime.MID
    elif volatility >= 30:
        return VolatilityRegime.LOW
    else:
        return VolatilityRegime.VOL_CRUSH


def _trade_style_to_timeframe(trade_style: str) -> Timeframe:
    """Map trade style to timeframe."""
    style_lower = trade_style.lower()
    
    if "breakout" in style_lower or "momentum" in style_lower:
        return Timeframe.SWING
    elif "mean_revert" in style_lower:
        return Timeframe.INTRADAY
    else:
        return Timeframe.SWING  # Default


def _extract_greeks(directive: CompositeMarketDirective) -> tuple[float, float, float]:
    """
    Extract gamma, vanna, charm from raw_engines if available.
    Returns (gamma_exposure, vanna_exposure, charm_exposure).
    """
    if directive.raw_engines is None:
        return (0.0, 0.0, 0.0)
    
    # Try to extract from hedge engine features
    hedge = directive.raw_engines.get("hedge", {})
    if isinstance(hedge, dict):
        features = hedge.get("features", {})
        gamma = features.get("hedge.gamma_field", 0.0)
        vanna = features.get("hedge.vanna_field", 0.0)
        charm = features.get("hedge.charm_field", 0.0)
        return (float(gamma), float(vanna), float(charm))
    
    return (0.0, 0.0, 0.0)


def _extract_liquidity_score(directive: CompositeMarketDirective) -> float:
    """
    Extract liquidity score from raw_engines if available.
    Returns value in [0, 1].
    """
    if directive.raw_engines is None:
        return 0.7  # Default to mid-high liquidity
    
    # Try to extract from liquidity engine features
    liquidity = directive.raw_engines.get("liquidity", {})
    if isinstance(liquidity, dict):
        features = liquidity.get("features", {})
        score = features.get("liquidity.liquidity_score", 0.7)
        return max(0.0, min(1.0, float(score)))
    
    return 0.7
