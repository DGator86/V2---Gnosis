from __future__ import annotations
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from ..schemas.base import SentimentPast, SentimentPresent, SentimentFuture, SentimentFeatures

def _momentum_z(df: pd.DataFrame, lookback: int = 20) -> float:
    """
    Calculate momentum z-score: how strong is the trend relative to recent history
    Positive = bullish momentum, Negative = bearish momentum
    """
    if len(df) < lookback: 
        return 0.0
    
    # Use log returns for better statistical properties
    ret = np.log(df["price"]).diff()
    
    # Calculate rolling mean and std
    recent_ret = ret.tail(lookback)
    mean_ret = recent_ret.mean()
    std_ret = recent_ret.std()
    
    # Z-score: how many stdev from mean
    z = mean_ret / (std_ret + 1e-8)  # avoid division by zero
    
    return float(np.clip(z, -3, 3))  # clip to reasonable range

def _vol_z(df: pd.DataFrame, lookback: int = 20) -> float:
    """
    Calculate volatility z-score: is vol elevated or suppressed vs baseline
    Positive = high vol environment, Negative = low vol environment  
    """
    if len(df) < lookback * 2:  # Need more data for baseline
        return 0.0
    
    # Calculate rolling volatility
    returns = df["price"].pct_change()
    recent_vol = returns.rolling(lookback).std().iloc[-1]
    
    # Baseline vol (longer window)
    baseline_vol = returns.rolling(min(len(returns), lookback * 5)).std().mean()
    
    if pd.isna(recent_vol) or pd.isna(baseline_vol) or baseline_vol == 0:
        return 0.0
    
    # Z-score: how elevated is current vol vs baseline
    z = (recent_vol - baseline_vol) / (baseline_vol + 1e-8)
    
    return float(np.clip(z, -3, 3))

def _volume_sentiment(df: pd.DataFrame, lookback: int = 20) -> float:
    """
    Calculate volume-based sentiment: heavy volume on up moves = bullish
    Returns value between -1 (bearish) and 1 (bullish)
    """
    if len(df) < lookback or "volume" not in df.columns:
        return 0.0
    
    recent = df.tail(lookback)
    returns = recent["price"].pct_change()
    
    # Volume-weighted directional flow
    up_volume = recent.loc[returns > 0, "volume"].sum()
    down_volume = recent.loc[returns < 0, "volume"].sum()
    total_volume = up_volume + down_volume
    
    if total_volume == 0:
        return 0.0
    
    # Buy/sell pressure ratio
    sentiment = (up_volume - down_volume) / total_volume
    
    return float(np.clip(sentiment, -1, 1))

def _regime(momo_z: float, vol_z: float, news_bias: float = 0.0) -> str:
    """
    Classify market regime based on momentum, volatility, and news
    
    Risk-on: Strong momentum + low vol + positive news
    Risk-off: Weak momentum + high vol + negative news
    Neutral: Mixed signals
    """
    # Composite score with weights
    score = momo_z - 0.5 * vol_z + 0.3 * news_bias
    
    if score > 0.5:
        return "risk_on"
    elif score < -0.5:
        return "risk_off"
    else:
        return "neutral"

def compute_sentiment_v0(
    symbol: str, 
    now: datetime, 
    df: pd.DataFrame, 
    news_bias: float = 0.0
) -> SentimentFeatures:
    """
    Compute sentiment features from price/volume data and optional news
    
    Args:
        symbol: Trading symbol
        now: Current timestamp
        df: DataFrame with columns: t_event, price, volume
        news_bias: Optional news sentiment score [-1, 1]
    
    Returns:
        SentimentFeatures with past/present/future components
    """
    if df.empty:
        # Return neutral sentiment if no data
        return SentimentFeatures(
            past=SentimentPast(events=[], iv_drift=0.0),
            present=SentimentPresent(
                regime="neutral",
                price_momo_z=0.0,
                vol_momo_z=0.0,
                conf=0.5
            ),
            future=SentimentFuture(
                flip_prob_10b=0.5,
                vov_tilt=0.0,
                conf=0.5
            )
        )
    
    df = df.sort_values("t_event")
    
    # Calculate core metrics
    price_momo_z = _momentum_z(df)
    vol_momo_z = _vol_z(df)
    volume_sent = _volume_sentiment(df)
    
    # Incorporate volume sentiment into regime determination
    adjusted_momo = price_momo_z + 0.3 * volume_sent
    regime = _regime(adjusted_momo, vol_momo_z, news_bias)
    
    # --- Past: What preceded current regime ---
    # Look for recent volatility events
    events = []
    if vol_momo_z > 1.5:
        events.append("vol_spike")
    elif vol_momo_z < -1.5:
        events.append("vol_crush")
    
    # Detect IV drift (placeholder - would use options data in production)
    iv_drift = float(np.random.normal(0, 0.05))  # Simulate for now
    
    past = SentimentPast(
        events=events,
        iv_drift=iv_drift
    )
    
    # --- Present: Current market mood ---
    # Confidence based on signal strength and consistency
    signal_strength = abs(adjusted_momo - 0.5 * vol_momo_z)
    conf = float(min(1.0, 0.5 + signal_strength / 3))
    
    # Boost confidence if volume confirms price action
    if abs(volume_sent) > 0.5 and np.sign(volume_sent) == np.sign(price_momo_z):
        conf = min(1.0, conf * 1.2)
    
    present = SentimentPresent(
        regime=regime,
        price_momo_z=price_momo_z,
        vol_momo_z=vol_momo_z,
        conf=conf
    )
    
    # --- Future: Probability of regime change ---
    # Higher vol = more likely to flip
    # Extreme momentum = less likely to flip (trend persistence)
    vol_contribution = abs(vol_momo_z) / 5  # Vol increases flip probability
    momo_contribution = abs(price_momo_z) / 10  # Strong trend decreases flip probability
    
    flip_prob = float(np.clip(
        0.3 + vol_contribution - momo_contribution,
        0.1,  # Minimum 10% flip probability
        0.9   # Maximum 90% flip probability
    ))
    
    # Vol-of-vol tilt: are we entering calmer or choppier waters?
    vov_tilt = float(vol_momo_z)
    
    # Future confidence inversely related to flip probability
    future_conf = float(1.0 - flip_prob / 2)
    
    future = SentimentFuture(
        flip_prob_10b=flip_prob,
        vov_tilt=vov_tilt,
        conf=future_conf
    )
    
    return SentimentFeatures(past=past, present=present, future=future)