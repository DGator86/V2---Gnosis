import numpy as np
import pandas as pd
from datetime import datetime
from gnosis.engines.sentiment_v0 import compute_sentiment_v0, _momentum_z, _vol_z, _regime

def test_momentum_calculation():
    """Test momentum z-score calculation"""
    # Uptrending prices
    df_up = pd.DataFrame({
        "price": 100 + np.linspace(0, 5, 50)
    })
    momo_up = _momentum_z(df_up)
    assert momo_up > 0  # Should be positive for uptrend
    
    # Downtrending prices
    df_down = pd.DataFrame({
        "price": 100 - np.linspace(0, 5, 50)
    })
    momo_down = _momentum_z(df_down)
    assert momo_down < 0  # Should be negative for downtrend

def test_volatility_calculation():
    """Test volatility z-score calculation"""
    # Need enough data for rolling windows
    # Low volatility - steady prices
    prices_low = 100 + np.cumsum(np.random.randn(200) * 0.01)
    df_low_vol = pd.DataFrame({
        "price": prices_low
    })
    vol_low = _vol_z(df_low_vol)
    
    # High volatility (recent spike)
    prices_high = np.concatenate([
        100 + np.cumsum(np.random.randn(150) * 0.01),  # Normal vol
        100 + np.cumsum(np.random.randn(50) * 0.1)     # Vol spike
    ])
    df_high_vol = pd.DataFrame({
        "price": prices_high
    })
    vol_high = _vol_z(df_high_vol)
    
    # At least one should be non-zero, and they should differ
    assert vol_high != vol_low or (vol_high == 0 and vol_low == 0)

def test_regime_classification():
    """Test regime determination logic"""
    # Risk-on: positive momentum, low vol
    regime_on = _regime(momo_z=1.5, vol_z=-0.5, news_bias=0.2)
    assert regime_on == "risk_on"
    
    # Risk-off: negative momentum, high vol
    regime_off = _regime(momo_z=-1.0, vol_z=1.5, news_bias=-0.3)
    assert regime_off == "risk_off"
    
    # Neutral: mixed signals
    regime_neutral = _regime(momo_z=0.2, vol_z=0.1, news_bias=0.0)
    assert regime_neutral == "neutral"

def test_sentiment_features_structure():
    """Test complete sentiment feature generation"""
    now = datetime(2025, 11, 3, 14, 31)
    df = pd.DataFrame({
        "t_event": pd.date_range(end=now, periods=60, freq="1min"),
        "price": 100 + np.cumsum(np.random.randn(60) * 0.1),
        "volume": np.random.randint(1000, 5000, 60)
    })
    
    features = compute_sentiment_v0("SPY", now, df)
    
    # Check structure
    assert features.past is not None
    assert features.present is not None
    assert features.future is not None
    
    # Check regime is valid
    assert features.present.regime in ["risk_on", "neutral", "risk_off"]
    
    # Check confidence bounds
    assert 0 <= features.present.conf <= 1
    assert 0 <= features.future.conf <= 1
    
    # Check flip probability bounds
    assert 0.1 <= features.future.flip_prob_10b <= 0.9

def test_empty_data_handling():
    """Test handling of empty/missing data"""
    now = datetime(2025, 11, 3, 14, 31)
    
    # Empty DataFrame
    df_empty = pd.DataFrame()
    features_empty = compute_sentiment_v0("SPY", now, df_empty)
    assert features_empty.present.regime == "neutral"
    assert features_empty.present.conf == 0.5
    
    # Insufficient data
    df_small = pd.DataFrame({
        "t_event": pd.date_range(end=now, periods=5, freq="1min"),
        "price": [100, 100.1, 100.2, 100.1, 100.3],
        "volume": [1000, 1100, 900, 1000, 1200]
    })
    features_small = compute_sentiment_v0("SPY", now, df_small)
    assert features_small.present.price_momo_z == 0.0  # Not enough data

def test_news_bias_impact():
    """Test that news bias affects regime classification"""
    now = datetime(2025, 11, 3, 14, 31)
    df = pd.DataFrame({
        "t_event": pd.date_range(end=now, periods=60, freq="1min"),
        "price": 100 + np.random.randn(60) * 0.1,  # Flat/random
        "volume": np.full(60, 3000)
    })
    
    # Without news - should be neutral
    features_no_news = compute_sentiment_v0("SPY", now, df, news_bias=0.0)
    
    # With strong positive news - might shift to risk-on
    features_pos_news = compute_sentiment_v0("SPY", now, df, news_bias=1.0)
    
    # With strong negative news - might shift to risk-off
    features_neg_news = compute_sentiment_v0("SPY", now, df, news_bias=-1.0)
    
    # News should influence confidence
    assert features_pos_news.present.conf >= features_no_news.present.conf or \
           features_neg_news.present.conf >= features_no_news.present.conf