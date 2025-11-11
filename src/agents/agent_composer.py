"""
Composer Agent
Merges findings from all agents into a coherent thesis with direction, conviction, and risk flags.
"""

from typing import List
from ..schemas.features import EngineSnapshot
from ..schemas.signals import AgentFinding, ComposerOutput


def compose_thesis(
    snap: EngineSnapshot,
    findings: List[AgentFinding]
) -> ComposerOutput:
    """
    Fuse agent views using weighted voting and conflict resolution.
    Output unified thesis with direction, conviction, horizon, levels, and risk flags.
    
    Parameters
    ----------
    snap : EngineSnapshot
        Combined engine snapshot
    findings : list[AgentFinding]
        Findings from all agents
        
    Returns
    -------
    ComposerOutput
        Unified trading thesis
    """
    # Weighted averaging of agent scores
    # Hedge gets more weight in high gamma environments
    # Liquidity gets more weight in normal conditions
    # Sentiment provides directional bias
    
    # Extract findings by source
    findings_dict = {f.source: f for f in findings}
    
    hedge_finding = findings_dict.get("hedge")
    liquidity_finding = findings_dict.get("liquidity")
    sentiment_finding = findings_dict.get("sentiment")
    
    # Base weights
    weights = {
        "hedge": 0.45,
        "liquidity": 0.35,
        "sentiment": 0.20,
    }
    
    # Adjust weights based on regime
    if snap.sentiment.regime in ("gamma_storm", "squeeze_risk"):
        # Increase hedge weight in high gamma environments
        weights["hedge"] = 0.55
        weights["liquidity"] = 0.25
        weights["sentiment"] = 0.20
    elif snap.sentiment.regime == "calm":
        # Increase sentiment weight in calm markets
        weights["hedge"] = 0.35
        weights["liquidity"] = 0.35
        weights["sentiment"] = 0.30
    
    # Compute weighted conviction
    conviction = 0.0
    if hedge_finding:
        conviction += weights["hedge"] * hedge_finding.score
    if liquidity_finding:
        conviction += weights["liquidity"] * liquidity_finding.score
    if sentiment_finding:
        conviction += weights["sentiment"] * sentiment_finding.score
    
    # Determine direction from sentiment bias
    # Positive news sentiment and accumulation/markup -> long
    # Negative news sentiment and distribution/markdown -> short
    news_sent = snap.sentiment.news_sentiment
    wyckoff = snap.sentiment.wyckoff_phase
    
    if news_sent >= 0.1 and wyckoff in ("accumulation", "markup"):
        direction = "long"
    elif news_sent <= -0.1 and wyckoff in ("distribution", "markdown"):
        direction = "short"
    elif news_sent >= 0:
        direction = "long"
    elif news_sent < 0:
        direction = "short"
    else:
        direction = "neutral"
    
    # If conviction is too low, force neutral
    if conviction < 0.4:
        direction = "neutral"
    
    # Time horizon based on regime
    if snap.sentiment.regime in ("calm", "normal"):
        horizon_hours = 24.0
    elif snap.sentiment.regime == "elevated":
        horizon_hours = 12.0
    else:
        horizon_hours = 6.0  # shorter in extreme regimes
    
    # Build thesis notes
    thesis_parts = []
    if hedge_finding:
        thesis_parts.append(f"Hedge: {hedge_finding.notes}")
    if liquidity_finding:
        thesis_parts.append(f"Liquidity: {liquidity_finding.notes}")
    if sentiment_finding:
        thesis_parts.append(f"Sentiment: {sentiment_finding.notes}")
    
    thesis = " | ".join(thesis_parts)
    
    # Key levels from liquidity zones and hedge gamma flip
    key_levels = snap.liquidity.zones.copy()
    if snap.hedge.gamma_flip_level is not None:
        key_levels.append(snap.hedge.gamma_flip_level)
    
    # Sort and deduplicate
    key_levels = sorted(set(key_levels))
    
    # Risk flags
    risk_flags = []
    if snap.liquidity.liquidity_trend == "tightening":
        risk_flags.append("liquidity_tightening")
    if snap.sentiment.regime == "gamma_storm":
        risk_flags.append("gamma_storm")
    if snap.sentiment.regime == "squeeze_risk":
        risk_flags.append("squeeze_risk")
    if snap.liquidity.dark_pool_ratio and snap.liquidity.dark_pool_ratio > 0.5:
        risk_flags.append("high_dark_pool_activity")
    
    # Expected volatility proxy from hedge vanna
    expected_vol = float(max(0.01, abs(snap.hedge.vanna) * 100))
    
    return ComposerOutput(
        ts=snap.ts,
        symbol=snap.symbol,
        direction=direction,
        conviction=conviction,
        horizon_hours=horizon_hours,
        thesis=thesis,
        key_levels=key_levels,
        risk_flags=risk_flags,
        expected_vol=expected_vol
    )
