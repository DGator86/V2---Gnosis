"""
Sentiment & Regime Engine
Fuses news sentiment, technical regime signals, and Wyckoff phase classification.
"""

import numpy as np
from typing import List, Optional
from ..schemas.bars import Bar
from ..schemas.features import SentimentFields


def compute_sentiment_fields(
    symbol: str,
    bars: List[Bar],
    news_scores: Optional[List[float]] = None
) -> SentimentFields:
    """
    Fuse textual sentiment with technical regime signals and output regime + Wyckoff phase.
    
    Parameters
    ----------
    symbol : str
        Ticker symbol
    bars : list[Bar]
        Recent price bars
    news_scores : list[float], optional
        News sentiment scores in range -1..1
        
    Returns
    -------
    SentimentFields
        Sentiment and regime analysis
    """
    if not bars or len(bars) < 2:
        return SentimentFields(
            ts=bars[0].ts if bars else None,
            symbol=symbol,
            news_sentiment=0.0,
            social_sentiment=None,
            regime="unknown",
            wyckoff_phase="unknown"
        )
    
    # Extract price data
    close = np.array([b.close for b in bars])
    volume = np.array([b.volume for b in bars])
    
    # Compute returns and realized volatility
    ret = np.diff(close) / close[:-1]
    
    # Realized volatility (annualized, assuming hourly data)
    if len(ret) > 100:
        rv = float(np.std(ret[-100:]) * np.sqrt(252 * 24))  # annualized
    else:
        rv = float(np.std(ret) * np.sqrt(252 * 24))
    
    # News sentiment: average of provided scores
    news_sentiment = 0.0
    if news_scores and len(news_scores) > 0:
        news_sentiment = float(np.mean(news_scores))
        # Clamp to -1..1
        news_sentiment = max(-1.0, min(1.0, news_sentiment))
    
    # Regime classification based on realized vol and price action
    # Thresholds (these would be calibrated in production)
    if rv < 0.15:
        regime = "calm"
    elif rv < 0.30:
        regime = "normal"
    elif rv < 0.50:
        # Check for squeeze conditions
        # Squeeze: low recent range but increasing volume
        if len(bars) > 20:
            recent_high = max(b.high for b in bars[-20:])
            recent_low = min(b.low for b in bars[-20:])
            recent_range = (recent_high - recent_low) / close[-1]
            recent_vol = np.mean(volume[-20:])
            older_vol = np.mean(volume[-40:-20]) if len(volume) > 40 else recent_vol
            
            if recent_range < 0.05 and recent_vol > older_vol * 1.2:
                regime = "squeeze_risk"
            else:
                regime = "elevated"
        else:
            regime = "elevated"
    else:
        regime = "gamma_storm"
    
    # Wyckoff phase classification
    wyckoff_phase = classify_wyckoff_phase(bars)
    
    return SentimentFields(
        ts=bars[-1].ts,
        symbol=symbol,
        news_sentiment=news_sentiment,
        social_sentiment=None,
        regime=regime,
        wyckoff_phase=wyckoff_phase
    )


def classify_wyckoff_phase(bars: List[Bar]) -> str:
    """
    Classify Wyckoff market phase using volume profile and price action.
    
    Simplified heuristic implementation:
    - Accumulation: narrow range, increasing volume, at lows
    - Markup: expanding range, price rising, volume confirming
    - Distribution: narrow range, increasing volume, at highs
    - Markdown: expanding range, price falling, volume confirming
    
    Parameters
    ----------
    bars : list[Bar]
        Recent price bars
        
    Returns
    -------
    str
        Wyckoff phase label
    """
    if len(bars) < 40:
        return "unknown"
    
    # Get recent and older periods
    recent = bars[-20:]
    older = bars[-40:-20]
    
    # Price metrics
    recent_close = np.array([b.close for b in recent])
    older_close = np.array([b.close for b in older])
    
    recent_high = max(b.high for b in recent)
    recent_low = min(b.low for b in recent)
    older_high = max(b.high for b in older)
    older_low = min(b.low for b in older)
    
    # Range metrics
    recent_range = (recent_high - recent_low) / recent_close[-1]
    older_range = (older_high - older_low) / older_close[-1]
    
    # Volume metrics
    recent_vol = np.mean([b.volume for b in recent])
    older_vol = np.mean([b.volume for b in older])
    
    # Trend metrics
    recent_trend = (recent_close[-1] - recent_close[0]) / recent_close[0]
    
    # Position relative to recent range
    current_price = recent_close[-1]
    range_position = (current_price - recent_low) / (recent_high - recent_low) if recent_high > recent_low else 0.5
    
    # Classification logic
    if recent_range < older_range * 0.7:
        # Narrow range (consolidation)
        if recent_vol > older_vol * 1.1:
            # Increasing volume in narrow range
            if range_position < 0.3:
                # At lows
                return "accumulation"
            elif range_position > 0.7:
                # At highs
                return "distribution"
            else:
                return "accumulation"  # default to accumulation in middle
        else:
            # Low volume consolidation
            return "accumulation"
    else:
        # Expanding range (trending)
        if recent_trend > 0.02:
            # Rising
            return "markup"
        elif recent_trend < -0.02:
            # Falling
            return "markdown"
        else:
            # Unclear
            return "accumulation"
    
    return "unknown"
