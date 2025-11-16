# agents/composer/energy/elasticity.py

from ..schemas import EngineDirective


def estimate_elasticity_from_liquidity(liquidity: EngineDirective) -> float:
    """
    Estimate a crude price elasticity / resistance term from liquidity features.

    v1.0: if you have namespace-prefixed features like `liq_kyle_lambda`,
    `liq_amihud`, use them; otherwise fallback to 1.0.
    """
    lam_kyle = liquidity.features.get("liq_kyle_lambda", 0.0)
    amihud = liquidity.features.get("liq_amihud", 0.0)

    # Simple heuristic: higher lambda/amihud = more resistance
    base = 1.0 + 0.5 * lam_kyle + 0.5 * amihud
    return max(0.1, base)
