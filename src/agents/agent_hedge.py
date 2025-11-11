"""
Hedge/Fields Specialist Agent
Interprets hedge pressure fields and flags gamma environments.
"""

from ..schemas.features import EngineSnapshot
from ..schemas.signals import AgentFinding


def analyze_hedge(snap: EngineSnapshot) -> AgentFinding:
    """
    Analyze hedge fields and produce a finding with confidence score.
    
    Parameters
    ----------
    snap : EngineSnapshot
        Combined engine snapshot
        
    Returns
    -------
    AgentFinding
        Agent analysis with score and notes
    """
    hedge = snap.hedge
    
    # Score based on pressure_score magnitude
    # Higher pressure suggests stronger dealer hedging activity
    score = max(0.0, min(1.0, hedge.pressure_score))
    
    # Additional factors
    if hedge.gamma_flip_level is not None:
        # Proximity to gamma flip increases score
        current_price = snap.liquidity.vpoc  # use VPOC as proxy for current
        distance_to_flip = abs(current_price - hedge.gamma_flip_level) / current_price
        
        if distance_to_flip < 0.02:  # within 2%
            score = min(1.0, score * 1.2)  # boost score
    
    # Generate notes
    notes = (
        f"GEX={hedge.gex:.2e}, vanna={hedge.vanna:.2e}, charm={hedge.charm:.2e}, "
        f"pressure={hedge.pressure_score:.3f}"
    )
    
    if hedge.gamma_flip_level:
        notes += f", flip_level=${hedge.gamma_flip_level:.2f}"
    
    features = {
        "gex": hedge.gex,
        "vanna": hedge.vanna,
        "charm": hedge.charm,
        "pressure_score": hedge.pressure_score,
    }
    
    return AgentFinding(
        ts=snap.ts,
        symbol=snap.symbol,
        source="hedge",
        score=score,
        notes=notes,
        features=features
    )
