# agents/composer/fusion/confidence_fusion.py

from ..schemas import EngineDirective


def fuse_confidence(
    hedge: EngineDirective,
    liquidity: EngineDirective,
    sentiment: EngineDirective,
    weights: dict,
    lookahead: EngineDirective = None,
) -> float:
    """
    Fuse confidence across engines using regime weights.

    v1.0: simple weighted average, clipped to [0,1].
    v2.0: Added optional Transformer lookahead prediction with 0.3 fixed weight.
    """
    num = (
        hedge.confidence * weights["hedge"]
        + liquidity.confidence * weights["liquidity"]
        + sentiment.confidence * weights["sentiment"]
    )
    den = weights["hedge"] + weights["liquidity"] + weights["sentiment"]

    # 🧠 Add Transformer lookahead prediction with 0.3 fixed weight
    if lookahead is not None:
        lookahead_weight = 0.3
        num += lookahead.confidence * lookahead_weight
        den += lookahead_weight

    if den == 0:
        return 0.0

    fused = num / den
    return max(0.0, min(1.0, fused))
