# agents/composer/scenarios/cone_builder.py

from typing import Dict
from ..schemas import ExpectedMoveBand, ExpectedMoveCone, EngineDirective


def _volatility_from_engines(
    hedge: EngineDirective,
    liquidity: EngineDirective,
    sentiment: EngineDirective,
) -> float:
    """
    Estimate a generic volatility level from engine volatility proxies.

    v1.0: average available proxies; fallback to 20.
    """
    vols = [
        v for v in (
            hedge.volatility_proxy,
            liquidity.volatility_proxy,
            sentiment.volatility_proxy,
        ) if v is not None
    ]

    if not vols:
        return 20.0

    return sum(vols) / len(vols)


def build_expected_move_cone(
    reference_price: float,
    direction_sign: int,
    hedge: EngineDirective,
    liquidity: EngineDirective,
    sentiment: EngineDirective,
) -> ExpectedMoveCone:
    """
    Build a simple expected move cone using a volatility estimate and direction.

    v1.0: symmetric percentage bands scaled by volatility and direction bias.
    """
    vol_level = _volatility_from_engines(hedge, liquidity, sentiment)

    # Convert to basic % move per horizon
    # These are heuristics; tune later.
    horizons = {
        "15m": (15, 0.15 * vol_level / 100.0),
        "1h": (60, 0.35 * vol_level / 100.0),
        "1d": (390, 0.80 * vol_level / 100.0),  # ~1 trading day minutes
    }

    bands: Dict[str, ExpectedMoveBand] = {}

    for label, (minutes, pct) in horizons.items():
        # Shift center slightly in favored direction
        directional_shift = 0.2 * direction_sign * pct
        center = reference_price * (1.0 + directional_shift)

        lower = center * (1.0 - pct)
        upper = center * (1.0 + pct)

        bands[label] = ExpectedMoveBand(
            horizon_minutes=minutes,
            lower=lower,
            upper=upper,
            confidence=0.68,  # heuristic; treat as ~1-sigma
        )

    return ExpectedMoveCone(reference_price=reference_price, bands=bands)
