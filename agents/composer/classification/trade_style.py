# agents/composer/classification/trade_style.py

from ..schemas import EngineDirective, Direction


def classify_trade_style(
    direction: Direction,
    confidence: float,
    energy: float,
    hedge: EngineDirective,
    liquidity: EngineDirective,
    sentiment: EngineDirective,
) -> str:
    """
    Classify trade style: momentum, mean_revert, breakout, or no_trade.

    v1.0:
    - Low confidence → 'no_trade'
    - Mixed engine directions → 'mean_revert' (even if fused direction is neutral)
    - High confidence, low energy → 'momentum'
    - High confidence, high energy but strong levels → 'breakout'
    """
    # Check direction disagreement FIRST (before checking fused direction)
    signs = {
        "hedge": 1 if hedge.direction > 0 else -1 if hedge.direction < 0 else 0,
        "liquidity": 1 if liquidity.direction > 0 else -1 if liquidity.direction < 0 else 0,
        "sentiment": 1 if sentiment.direction > 0 else -1 if sentiment.direction < 0 else 0,
    }
    unique_signs = {s for s in signs.values() if s != 0}

    # If engines disagree significantly, it's a mean revert setup
    if len(unique_signs) > 1 and confidence >= 0.4:
        return "mean_revert"

    # Low confidence or neutral direction with no conflicts
    if direction == 0 or confidence < 0.4:
        return "no_trade"

    # Single-direction alignment; energy determines style
    if energy < 1.0:
        return "momentum"

    # Higher resistance, but aligned direction: likely breakout-style setups
    return "breakout"
