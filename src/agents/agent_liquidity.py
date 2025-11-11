"""
Liquidity Cartographer Agent
Maps liquidity zones, warns on tightening, identifies stop-runs and liquidity pools.
"""

from ..schemas.features import EngineSnapshot
from ..schemas.signals import AgentFinding


def analyze_liquidity(snap: EngineSnapshot) -> AgentFinding:
    """
    Analyze liquidity fields and produce a finding.
    
    Parameters
    ----------
    snap : EngineSnapshot
        Combined engine snapshot
        
    Returns
    -------
    AgentFinding
        Agent analysis with score and notes
    """
    liq = snap.liquidity
    
    # Score: Lower Kyle's lambda and clear zones -> higher score
    # Lambda typically small (e.g., 1e-6 to 1e-3)
    # Normalize using inverse sigmoid
    if liq.kyle_lambda > 0:
        normalized_lambda = max(0.0, min(1.0, liq.kyle_lambda * 1e6))
        score = float(1.0 / (1.0 + normalized_lambda))
    else:
        score = 0.5
    
    # Adjust for liquidity trend
    if liq.liquidity_trend == "tightening":
        score *= 0.8  # reduce confidence in tight liquidity
    elif liq.liquidity_trend == "loosening":
        score = min(1.0, score * 1.1)  # boost confidence in good liquidity
    
    # Dark pool activity
    if liq.dark_pool_ratio is not None and liq.dark_pool_ratio > 0.4:
        # High dark pool ratio suggests institutional activity
        score = min(1.0, score * 1.05)
    
    # Generate notes
    notes = (
        f"λ={liq.kyle_lambda:.3e}, VPOC=${liq.vpoc:.2f}, "
        f"trend={liq.liquidity_trend}"
    )
    
    if liq.dark_pool_ratio is not None:
        notes += f", dark_pool={liq.dark_pool_ratio:.2%}"
    
    notes += f", zones={len(liq.zones)}"
    
    features = {
        "kyle_lambda": liq.kyle_lambda,
        "amihud": liq.amihud,
        "vpoc": liq.vpoc,
        "zone_count": float(len(liq.zones)),
    }
    
    if liq.dark_pool_ratio is not None:
        features["dark_pool_ratio"] = liq.dark_pool_ratio
    
    return AgentFinding(
        ts=snap.ts,
        symbol=snap.symbol,
        source="liquidity",
        score=score,
        notes=notes,
        features=features
    )
