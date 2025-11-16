# agents/composer/fusion/direction_fusion.py

from typing import Literal
from ..schemas import EngineDirective, Direction


def fuse_direction(
    hedge: EngineDirective,
    liquidity: EngineDirective,
    sentiment: EngineDirective,
    weights: dict,
) -> Direction:
    """
    Fuse directional bias across engines.

    v1.0: confidence- and regime-weighted vote in [-1,1],
    then snapped to {-1, 0, 1} with a neutral band.
    """
    weighted_hedge = hedge.direction * hedge.confidence * weights["hedge"]
    weighted_liq = liquidity.direction * liquidity.confidence * weights["liquidity"]
    weighted_sent = sentiment.direction * sentiment.confidence * weights["sentiment"]

    score = weighted_hedge + weighted_liq + weighted_sent

    # Normalize by total effective weight
    total_w = (
        hedge.confidence * weights["hedge"]
        + liquidity.confidence * weights["liquidity"]
        + sentiment.confidence * weights["sentiment"]
    )
    if total_w > 0:
        score /= total_w

    # Snap to {-1, 0, 1} with a neutral band
    # Threshold lowered to 0.15 to allow regime-dominant engines to break through
    if score > 0.15:
        return 1
    if score < -0.15:
        return -1
    return 0
