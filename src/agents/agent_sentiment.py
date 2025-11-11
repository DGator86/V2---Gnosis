"""
Sentiment Interpreter Agent
Validates or contradicts direction via sentiment and Wyckoff phase.
"""

from ..schemas.features import EngineSnapshot
from ..schemas.signals import AgentFinding


def analyze_sentiment(snap: EngineSnapshot) -> AgentFinding:
    """
    Analyze sentiment fields and produce a finding.
    
    Parameters
    ----------
    snap : EngineSnapshot
        Combined engine snapshot
        
    Returns
    -------
    AgentFinding
        Agent analysis with score and notes
    """
    sent = snap.sentiment
    
    # Base score from news sentiment (-1..1 -> 0..1)
    base_score = (sent.news_sentiment + 1.0) / 2.0
    
    # Weight by regime
    regime_weights = {
        "calm": 0.6,
        "normal": 0.7,
        "elevated": 0.75,
        "squeeze_risk": 0.8,
        "gamma_storm": 0.5,  # reduced confidence in extreme vol
        "unknown": 0.5,
    }
    
    regime_weight = regime_weights.get(sent.regime, 0.6)
    score = float(base_score * regime_weight)
    
    # Wyckoff phase adjustment
    # Accumulation/Markup phases -> bullish bias
    # Distribution/Markdown phases -> bearish bias
    wyckoff_adjustments = {
        "accumulation": 0.1,   # slight bullish bias
        "markup": 0.15,        # stronger bullish
        "distribution": -0.1,  # slight bearish bias
        "markdown": -0.15,     # stronger bearish
        "unknown": 0.0,
    }
    
    wyckoff_adj = wyckoff_adjustments.get(sent.wyckoff_phase, 0.0)
    
    # Apply Wyckoff adjustment to score
    if sent.news_sentiment >= 0:
        # Positive sentiment: Wyckoff confirms or contradicts
        score = max(0.0, min(1.0, score + wyckoff_adj))
    else:
        # Negative sentiment: inverse Wyckoff adjustment
        score = max(0.0, min(1.0, score - wyckoff_adj))
    
    # Generate notes
    notes = (
        f"regime={sent.regime}, wyckoff={sent.wyckoff_phase}, "
        f"news={sent.news_sentiment:.2f}"
    )
    
    if sent.social_sentiment is not None:
        notes += f", social={sent.social_sentiment:.2f}"
    
    features = {
        "news_sentiment": sent.news_sentiment,
        "regime_weight": regime_weight,
        "wyckoff_adjustment": wyckoff_adj,
    }
    
    if sent.social_sentiment is not None:
        features["social_sentiment"] = sent.social_sentiment
    
    return AgentFinding(
        ts=snap.ts,
        symbol=snap.symbol,
        source="sentiment",
        score=score,
        notes=notes,
        features=features
    )
