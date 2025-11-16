# agents/composer/resolution/regime_weights.py

from typing import Dict
from ..schemas import EngineDirective


def infer_global_regime(
    hedge: EngineDirective,
    liquidity: EngineDirective,
    sentiment: EngineDirective,
) -> str:
    """
    Infer a coarse global regime from individual engine regimes.

    For v1.0: prioritize special regimes over "normal", since extreme
    conditions (jump, vacuum, etc.) should override normal state.
    """
    # Collect all non-"normal" regimes
    regimes = [hedge.regime, liquidity.regime, sentiment.regime]
    special_regimes = [r for r in regimes if r and r.lower() != "normal"]
    
    # If any agent detects a special regime, use it
    if special_regimes:
        return special_regimes[0]
    
    # Otherwise, fall back to first available regime
    return sentiment.regime or hedge.regime or liquidity.regime or "normal"


def compute_regime_weights(
    hedge: EngineDirective,
    liquidity: EngineDirective,
    sentiment: EngineDirective,
) -> Dict[str, float]:
    """
    Compute regime-aware weights for each engine.

    v1.0: simple heuristic mapping based on global regime string,
    falling back to equal weighting.
    """
    global_regime = infer_global_regime(hedge, liquidity, sentiment).lower()

    # Default equal weights
    weights = {"hedge": 1.0, "liquidity": 1.0, "sentiment": 1.0}

    if any(key in global_regime for key in ("jump", "panic", "crash", "double_well")):
        # Dealer and liquidity matter more in violent regimes
        weights = {"hedge": 2.5, "liquidity": 1.5, "sentiment": 0.5}
    elif any(key in global_regime for key in ("vacuum", "transition", "rotation")):
        # Liquidity structure dominates
        weights = {"hedge": 0.8, "liquidity": 2.5, "sentiment": 0.7}
    elif any(key in global_regime for key in ("markup", "markdown", "trend", "distribution", "accumulation")):
        # Sentiment + trend matter more
        weights = {"hedge": 0.6, "liquidity": 0.9, "sentiment": 2.5}

    # Normalize to sum=1
    total = sum(weights.values())
    for k in weights:
        weights[k] /= total

    return weights
