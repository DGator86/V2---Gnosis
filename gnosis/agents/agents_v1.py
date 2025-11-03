from __future__ import annotations
from pydantic import BaseModel
from typing import Dict, List, Optional
from datetime import datetime
import numpy as np

# ---- Common agent view (one per engine) ----
class AgentView(BaseModel):
    symbol: str
    bar: datetime
    agent: str                 # "hedge" | "liquidity" | "sentiment"
    dir_bias: float            # -1..+1
    confidence: float          # 0..1
    thesis: str                # e.g., "breakout_up", "pin", "risk_on_follow"
    levels: Optional[Dict[str, List[List[float]]]] = None
    notes: Optional[str] = None

# ---- Agent 1: Hedge (pressure) ----
def agent1_hedge(symbol: str, bar: datetime, hedge_present: Dict, hedge_future: Dict) -> AgentView:
    """
    Hedge agent: interprets dealer positioning pressure
    Strong gamma = directional breakout bias
    Pin regime = low confidence
    """
    hf   = float(hedge_present.get("hedge_force", 0.0))
    conf = float(hedge_present.get("conf", 0.5))
    regime = hedge_present.get("regime", "neutral")
    wall_dist = float(hedge_present.get("wall_dist", 0.0))
    
    # Determine thesis based on regime and force
    if regime == "pin":
        thesis = "pin"
    elif hf > 0.001:
        thesis = "breakout_up"
    elif hf < -0.001:
        thesis = "breakout_down"
    else:
        thesis = "neutral_gamma"
    
    # Penalize pins and adjust confidence
    conf_adj = conf * (0.6 if regime == "pin" else 1.0)
    
    # Boost confidence if near gamma wall (imminent action)
    if wall_dist > 0 and wall_dist < 2:
        conf_adj *= 1.2
    
    return AgentView(
        symbol=symbol, 
        bar=bar, 
        agent="hedge",
        dir_bias=1.0 if hf > 0.001 else -1.0 if hf < -0.001 else 0.0,
        confidence=max(0.0, min(1.0, conf_adj)),
        thesis=thesis,
        notes=f"regime={regime}, hedge_force={hf:.4f}, wall_dist={wall_dist:.2f}"
    )

# ---- Agent 2: Liquidity (terrain) ----
def agent2_liquidity(symbol: str, bar: datetime, liq_present: Dict, liq_future: Dict, spot: float) -> AgentView:
    """
    Liquidity agent: maps market terrain and zones
    Thick liquidity = higher confidence
    Zone proximity = directional bias
    """
    support = liq_present.get("support", [])
    resistance = liq_present.get("resistance", [])
    amihud = float(liq_present.get("amihud", 0.0))
    lam    = float(liq_present.get("lambda_impact", 0.0))
    next_mag = liq_future.get("next_magnet")
    
    # Bias toward next magnet relative to spot
    bias = 0.0
    if next_mag is not None:
        mag_dist = float(next_mag) - spot
        if abs(mag_dist) > 0.1:  # Meaningful distance
            bias = 1.0 if mag_dist > 0 else -1.0
    
    # Alternative: bias based on zone proximity
    if bias == 0 and (support or resistance):
        # Closer to support = bullish, closer to resistance = bearish
        def get_hi(z):
            return z["hi"] if isinstance(z, dict) else (z[1] if len(z) >= 2 else 0)
        def get_lo(z):
            return z["lo"] if isinstance(z, dict) else (z[0] if len(z) >= 2 else float('inf'))
        
        nearest_support = max([get_hi(z) for z in support], default=0)
        nearest_resist = min([get_lo(z) for z in resistance], default=float('inf'))
        
        if nearest_support > 0 and abs(spot - nearest_support) < abs(spot - nearest_resist):
            bias = 1.0  # Bounce off support expected
        elif nearest_resist < float('inf'):
            bias = -1.0  # Rejection at resistance expected
    
    # Liquidity confidence: thinner market → reduce conviction
    base_conf = float(liq_present.get("conf", 0.5))
    
    # Scale confidence by liquidity quality (lower Amihud = better liquidity)
    # Typical Amihud for liquid markets: 1e-11 to 1e-10
    # Illiquid markets: > 1e-9
    if amihud > 0:
        liq_quality = min(1.0, -np.log10(max(amihud, 1e-15)) / 15)  # Maps 1e-15 to 1.0, 1e-0 to 0.0
    else:
        liq_quality = 0.5
    
    conf = max(0.0, min(1.0, base_conf * liq_quality))
    
    # Package zone levels for reference
    # Handle both dict and list formats (parquet may store as lists)
    def zone_to_list(z):
        if isinstance(z, dict):
            return [z["lo"], z["hi"]]
        elif isinstance(z, list) and len(z) >= 2:
            return [z[0], z[1]]
        else:
            return [0.0, 0.0]
    
    levels = {
        "zones_support": [zone_to_list(z) for z in support],
        "zones_resist":  [zone_to_list(z) for z in resistance]
    }
    
    # Determine thesis
    if len(support) > len(resistance):
        thesis = "support_dominant"
    elif len(resistance) > len(support):
        thesis = "resistance_dominant"
    else:
        thesis = "zone_follow"
    
    return AgentView(
        symbol=symbol, 
        bar=bar, 
        agent="liquidity",
        dir_bias=bias, 
        confidence=conf, 
        thesis=thesis,
        levels=levels, 
        notes=f"amihud={amihud:.4g}, lambda={lam:.3g}, zones={len(support)}S/{len(resistance)}R"
    )

# ---- Agent 3: Sentiment (mood) ----
def agent3_sentiment(symbol: str, bar: datetime, sent_present: Dict, sent_future: Dict) -> AgentView:
    """
    Sentiment agent: reads market emotional temperature
    Risk-on = bullish, Risk-off = bearish
    High flip probability = low confidence
    """
    regime = sent_present.get("regime", "neutral")
    conf   = float(sent_present.get("conf", 0.5))
    momo_z = float(sent_present.get("price_momo_z", 0.0))
    vol_z  = float(sent_present.get("vol_momo_z", 0.0))
    flip_p = float(sent_future.get("flip_prob_10b", 0.3))
    vov    = float(sent_future.get("vov_tilt", 0.0))
    
    # Map regime to bias
    if regime == "risk_on":
        bias = 1.0
        thesis = "risk_on_follow"
    elif regime == "risk_off":
        bias = -1.0
        thesis = "risk_off_defensive"
    else:
        # In neutral, use momentum as tiebreaker
        bias = 1.0 if momo_z > 0.3 else -1.0 if momo_z < -0.3 else 0.0
        thesis = "regime_neutral"
    
    # Adjust confidence based on regime strength and flip risk
    # Strong momentum = higher confidence
    momo_conf_boost = min(0.2, abs(momo_z) / 5)
    
    # High volatility = lower confidence (except in risk-off where it's expected)
    vol_penalty = 0.1 * abs(vol_z) if regime != "risk_off" else 0
    
    # High flip probability = much lower confidence
    flip_penalty = 0.7 * flip_p
    
    conf_adj = conf + momo_conf_boost - vol_penalty - flip_penalty
    conf_adj = max(0.0, min(1.0, conf_adj))
    
    return AgentView(
        symbol=symbol, 
        bar=bar, 
        agent="sentiment",
        dir_bias=bias, 
        confidence=conf_adj,
        thesis=thesis, 
        notes=f"regime={regime}, momo_z={momo_z:.2f}, flip_prob={flip_p:.2f}, vov={vov:.2f}"
    )

# ---- Composer: 2-of-3 alignment + reliability + liquidity sizing ----
def compose(
    symbol: str, 
    bar: datetime, 
    views: List[AgentView], 
    amihud: float, 
    reliability: Dict[str, float] | None = None
) -> Dict:
    """
    Composer: synthesizes agent views into final trade decision
    
    Rules:
    1. Need 2-of-3 agents aligned with confidence >= 0.6
    2. Weighted voting by confidence × reliability
    3. Position sizing based on liquidity (Amihud)
    4. Time stops based on sentiment flip risk
    """
    import numpy as np
    
    reliability = reliability or {"hedge": 1.0, "liquidity": 1.0, "sentiment": 1.0}

    # Normalize confidences and apply reliability weights
    for v in views:
        v.confidence = float(max(0.0, min(1.0, v.confidence)))
    
    w = {v.agent: v.confidence * float(reliability.get(v.agent, 1.0)) for v in views}

    # Calculate directional scores
    up_score   = sum(w[v.agent] for v in views if v.dir_bias > 0)
    down_score = sum(w[v.agent] for v in views if v.dir_bias < 0)
    
    # Check alignment: need 2+ agents with conf >= 0.6 pointing same way
    high_conf_threshold = 0.6
    align_up   = sum(1 for v in views if v.dir_bias > 0 and v.confidence >= high_conf_threshold) >= 2
    align_down = sum(1 for v in views if v.dir_bias < 0 and v.confidence >= high_conf_threshold) >= 2

    # Make trade decision
    take = False
    direction = None
    conf = 0.0
    
    if align_up and up_score > down_score * 1.2:  # Need 20% edge
        take = True
        direction = "long"
        conf = min(1.0, up_score / (up_score + down_score + 1e-9))
    elif align_down and down_score > up_score * 1.2:  # Need 20% edge
        take = True
        direction = "short"
        conf = min(1.0, down_score / (up_score + down_score + 1e-9))

    # Build response based on decision
    if not take:
        reason = "no_alignment"
        if not align_up and not align_down:
            reason = "insufficient_alignment"
        elif up_score > 0 and down_score > 0 and abs(up_score - down_score) < 0.2:
            reason = "mixed_signals"
        
        return {
            "take_trade": False, 
            "symbol": symbol,
            "bar": bar.isoformat(),
            "reason": reason,
            "scores": {"up": round(up_score, 3), "down": round(down_score, 3)},
            "views": [v.model_dump() for v in views]
        }

    # --- Trade approved: calculate sizing and stops ---
    
    # Position sizing from liquidity (Amihud): thinner → smaller
    # Typical Amihud ranges:
    # Very liquid (SPY): 1e-11 to 1e-10
    # Liquid: 1e-10 to 1e-9  
    # Illiquid: > 1e-9
    if amihud > 0:
        # Map Amihud to size multiplier
        # 1e-12 or less → 1.0 (max size)
        # 1e-10 → 0.8
        # 1e-9 → 0.5
        # 1e-8 or more → 0.25 (min size)
        log_amihud = np.log10(max(amihud, 1e-15))
        if log_amihud <= -12:
            size_mult = 1.0
        elif log_amihud >= -8:
            size_mult = 0.25
        else:
            # Linear interpolation between -12 and -8
            size_mult = 1.0 - 0.75 * (log_amihud + 12) / 4
    else:
        size_mult = 0.5  # Default conservative
    
    # Adjust size based on confidence
    size_mult *= min(1.0, 0.5 + conf)
    
    # Time stop based on sentiment flip risk
    flip_prob = 0.3  # Default
    vov = 0.0
    for v in views:
        if v.agent == "sentiment" and v.notes:
            # Extract flip probability from notes
            if "flip_prob=" in v.notes:
                try:
                    flip_prob = float(v.notes.split("flip_prob=")[1].split(",")[0])
                except:
                    pass
            if "vov=" in v.notes:
                try:
                    vov = float(v.notes.split("vov=")[1].split(",")[0])
                except:
                    pass
    
    # High flip risk or high VoV = shorter time stop
    eta_bars = int(max(4, min(12, 10 * (1 - flip_prob))))
    
    # Get stop levels from liquidity zones
    stop_levels = {}
    for v in views:
        if v.agent == "liquidity" and v.levels:
            if direction == "long" and v.levels.get("zones_support"):
                # Stop below nearest support
                supports = v.levels["zones_support"]
                if supports:
                    stop_levels["stop_loss"] = min([zone[0] for zone in supports])
            elif direction == "short" and v.levels.get("zones_resist"):
                # Stop above nearest resistance
                resists = v.levels["zones_resist"]
                if resists:
                    stop_levels["stop_loss"] = max([zone[1] for zone in resists])

    return {
        "take_trade": True,
        "symbol": symbol,
        "bar": bar.isoformat(),
        "direction": direction,
        "confidence": round(conf, 3),
        "position_sizing_hint": round(size_mult, 3),
        "time_stop_bars": eta_bars,
        "stop_levels": stop_levels,
        "scores": {"up": round(up_score, 3), "down": round(down_score, 3)},
        "rationale": {
            "alignment": f"{sum(1 for v in views if v.dir_bias * (1 if direction == 'long' else -1) > 0)}/3 agents agree",
            "primary_driver": max(views, key=lambda v: v.confidence * v.dir_bias * (1 if direction == "long" else -1)).agent,
            "liquidity_quality": "good" if amihud < 1e-10 else ("fair" if amihud < 1e-9 else "poor"),
            "flip_risk": "high" if flip_prob > 0.5 else ("medium" if flip_prob > 0.3 else "low")
        },
        "views": [v.model_dump() for v in views]
    }