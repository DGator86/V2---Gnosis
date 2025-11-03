from __future__ import annotations
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Optional, Literal
from ..schemas.base import BaseModel

# Add to schemas/base.py:
# class WyckoffPhase(BaseModel):
#     phase: Literal["accumulation", "markup", "distribution", "markdown", "unknown"]
#     confidence: float
#     volume_strength: float  # 0-1
#     price_action: str
#     events: list[str]

WyckoffPhase = Literal["accumulation", "markup", "distribution", "markdown", "unknown"]

def _detect_volume_divergence(df: pd.DataFrame, lookback: int = 20) -> float:
    """
    Detect volume vs price divergence (key Wyckoff signal)
    
    Positive divergence: Volume increasing while price falling (accumulation)
    Negative divergence: Volume increasing while price rising (distribution)
    
    Returns: -1 to +1 score
    """
    if len(df) < lookback:
        return 0.0
    
    recent = df.tail(lookback)
    
    # Price momentum
    price_ret = np.log(recent["price"]).diff()
    price_trend = price_ret.mean()
    
    # Volume trend
    vol_norm = (recent["volume"] - recent["volume"].mean()) / (recent["volume"].std() + 1e-8)
    vol_trend = vol_norm.tail(5).mean()  # Recent volume vs baseline
    
    # Divergence score
    # If vol increasing + price falling → positive (accumulation)
    # If vol increasing + price rising → negative (distribution)
    if vol_trend > 0.5:  # High volume
        if price_trend < -0.001:  # Price falling
            return min(1.0, vol_trend)  # Accumulation signal
        elif price_trend > 0.001:  # Price rising
            return max(-1.0, -vol_trend)  # Distribution signal
    
    return 0.0

def _detect_spring(df: pd.DataFrame, lookback: int = 50) -> bool:
    """
    Detect Wyckoff 'Spring' - a bear trap at support
    
    Pattern: Price breaks below support, then quickly recovers
    Signal: Accumulation phase ending, markup beginning
    """
    if len(df) < lookback:
        return False
    
    recent = df.tail(lookback)
    
    # Find recent low
    low_idx = recent["price"].idxmin()
    low_price = recent.loc[low_idx, "price"]
    
    # Check if we bounced significantly (>1%) from low in last 10 bars
    last_10 = recent.tail(10)
    current_price = last_10["price"].iloc[-1]
    
    if (current_price - low_price) / low_price > 0.01:
        # Check volume on bounce
        bounce_vol = last_10["volume"].mean()
        baseline_vol = recent["volume"].mean()
        
        if bounce_vol > baseline_vol * 1.2:  # 20% higher volume on bounce
            return True
    
    return False

def _detect_upthrust(df: pd.DataFrame, lookback: int = 50) -> bool:
    """
    Detect Wyckoff 'Upthrust' - a bull trap at resistance
    
    Pattern: Price breaks above resistance, then quickly fails
    Signal: Distribution phase, markdown beginning
    """
    if len(df) < lookback:
        return False
    
    recent = df.tail(lookback)
    
    # Find recent high
    high_idx = recent["price"].idxmax()
    high_price = recent.loc[high_idx, "price"]
    
    # Check if we dropped significantly (>1%) from high in last 10 bars
    last_10 = recent.tail(10)
    current_price = last_10["price"].iloc[-1]
    
    if (high_price - current_price) / high_price > 0.01:
        # Check volume on rejection
        reject_vol = last_10["volume"].mean()
        baseline_vol = recent["volume"].mean()
        
        if reject_vol > baseline_vol * 1.2:  # 20% higher volume on rejection
            return True
    
    return False

def _classify_wyckoff_phase(
    df: pd.DataFrame,
    vol_divergence: float,
    spring: bool,
    upthrust: bool
) -> tuple[WyckoffPhase, float]:
    """
    Classify current Wyckoff phase based on indicators
    
    Returns: (phase, confidence)
    """
    if len(df) < 50:
        return "unknown", 0.0
    
    recent = df.tail(50)
    
    # Price trend (50-bar)
    ret = np.log(recent["price"]).diff()
    trend = ret.mean()
    
    # Volume behavior
    vol_ma_20 = recent["volume"].rolling(20).mean()
    vol_recent = recent["volume"].tail(10).mean()
    vol_ratio = vol_recent / (vol_ma_20.iloc[-1] + 1e-8)
    
    # Decision logic
    conf = 0.5
    
    # Strong signals
    if spring:
        return "accumulation", 0.85  # Spring is high-confidence accumulation end
    
    if upthrust:
        return "distribution", 0.85  # Upthrust is high-confidence distribution
    
    # Accumulation: High volume + sideways/down price + positive divergence
    if vol_divergence > 0.5 and abs(trend) < 0.001:
        conf = min(0.9, 0.6 + vol_divergence * 0.3)
        return "accumulation", conf
    
    # Markup: Strong uptrend + declining volume (healthy)
    if trend > 0.002 and vol_ratio < 1.0:
        conf = min(0.9, 0.6 + abs(trend) * 100)
        return "markup", conf
    
    # Distribution: High volume + sideways/up price + negative divergence
    if vol_divergence < -0.5 and abs(trend) < 0.001:
        conf = min(0.9, 0.6 + abs(vol_divergence) * 0.3)
        return "distribution", conf
    
    # Markdown: Strong downtrend + declining volume
    if trend < -0.002 and vol_ratio < 1.0:
        conf = min(0.9, 0.6 + abs(trend) * 100)
        return "markdown", conf
    
    return "unknown", 0.3

def compute_wyckoff_v0(symbol: str, now: datetime, df: pd.DataFrame) -> dict:
    """
    Compute Wyckoff analysis features
    
    Args:
        symbol: Trading symbol
        now: Current timestamp
        df: DataFrame with columns: t_event, price, volume
    
    Returns:
        Dictionary with Wyckoff features
    """
    if df.empty or len(df) < 50:
        return {
            "phase": "unknown",
            "confidence": 0.0,
            "volume_divergence": 0.0,
            "spring_detected": False,
            "upthrust_detected": False,
            "volume_strength": 0.5,
            "price_action": "unknown",
            "events": []
        }
    
    df = df.sort_values("t_event")
    
    # Compute indicators
    vol_divergence = _detect_volume_divergence(df, lookback=20)
    spring = _detect_spring(df, lookback=50)
    upthrust = _detect_upthrust(df, lookback=50)
    
    # Classify phase
    phase, confidence = _classify_wyckoff_phase(df, vol_divergence, spring, upthrust)
    
    # Volume strength (recent vs baseline)
    vol_recent = df["volume"].tail(10).mean()
    vol_baseline = df["volume"].mean()
    vol_strength = min(1.0, vol_recent / (vol_baseline + 1e-8))
    
    # Price action description
    ret = np.log(df["price"]).diff().tail(20).mean()
    if ret > 0.002:
        price_action = "strong_uptrend"
    elif ret > 0.001:
        price_action = "mild_uptrend"
    elif ret < -0.002:
        price_action = "strong_downtrend"
    elif ret < -0.001:
        price_action = "mild_downtrend"
    else:
        price_action = "ranging"
    
    # Events
    events = []
    if spring:
        events.append("spring")
    if upthrust:
        events.append("upthrust")
    if abs(vol_divergence) > 0.7:
        events.append("strong_divergence")
    
    return {
        "phase": phase,
        "confidence": float(confidence),
        "volume_divergence": float(vol_divergence),
        "spring_detected": spring,
        "upthrust_detected": upthrust,
        "volume_strength": float(vol_strength),
        "price_action": price_action,
        "events": events
    }
