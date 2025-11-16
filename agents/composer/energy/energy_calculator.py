# agents/composer/energy/energy_calculator.py

from ..schemas import EngineDirective
from .elasticity import estimate_elasticity_from_liquidity


def compute_total_energy(
    hedge: EngineDirective,
    liquidity: EngineDirective,
    sentiment: EngineDirective,
) -> float:
    """
    Aggregate total price-move energy (resistance) across engines.

    v1.0:
    - Hedge.energy ~ gamma curvature / dealer resistance
    - Liquidity.energy ~ impact / thin-book friction
    - Sentiment.energy ~ exhaustion / trend fatigue
    """
    liq_elasticity = estimate_elasticity_from_liquidity(liquidity)

    total_energy = (
        hedge.energy * 1.2
        + liquidity.energy * liq_elasticity
        + sentiment.energy * 0.8
    )
    return max(0.0, total_energy)
