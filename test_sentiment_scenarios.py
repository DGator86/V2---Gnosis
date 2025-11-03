#!/usr/bin/env python3
import pandas as pd
import numpy as np
from datetime import datetime
from gnosis.engines.sentiment_v0 import compute_sentiment_v0

now = datetime(2025, 11, 3, 14, 31)

print("=" * 60)
print("SCENARIO 1: Strong Uptrend (Risk-On)")
print("-" * 60)
# Steadily rising prices with low volatility
prices_up = 450 + np.linspace(0, 3, 60) + np.random.randn(60) * 0.05
volumes_up = np.random.randint(3000, 5000, 60).astype(float)
# Higher volume on up moves
volumes_up[np.diff(prices_up, prepend=prices_up[0]) > 0] *= 1.5

df_up = pd.DataFrame({
    "t_event": pd.date_range(end=now, periods=60, freq="1min"),
    "price": prices_up,
    "volume": volumes_up
})

features_up = compute_sentiment_v0("SPY", now, df_up, news_bias=0.3)
print(f"Regime: {features_up.present.regime}")
print(f"Price momentum Z: {features_up.present.price_momo_z:.2f}")
print(f"Vol momentum Z: {features_up.present.vol_momo_z:.2f}")
print(f"Confidence: {features_up.present.conf:.2f}")
print(f"Flip probability: {features_up.future.flip_prob_10b:.2%}")

print("\n" + "=" * 60)
print("SCENARIO 2: Panic Selloff (Risk-Off)")
print("-" * 60)
# Sharp decline with spiking volatility
prices_down = 452 - np.linspace(0, 4, 60) + np.random.randn(60) * 0.3
volumes_down = np.random.randint(5000, 10000, 60).astype(float)
# Higher volume on down moves (panic selling)
volumes_down[np.diff(prices_down, prepend=prices_down[0]) < 0] *= 1.5

df_down = pd.DataFrame({
    "t_event": pd.date_range(end=now, periods=60, freq="1min"),
    "price": prices_down,
    "volume": volumes_down
})

features_down = compute_sentiment_v0("SPY", now, df_down, news_bias=-0.5)
print(f"Regime: {features_down.present.regime}")
print(f"Price momentum Z: {features_down.present.price_momo_z:.2f}")
print(f"Vol momentum Z: {features_down.present.vol_momo_z:.2f}")
print(f"Confidence: {features_down.present.conf:.2f}")
print(f"Events: {features_down.past.events}")

print("\n" + "=" * 60)
print("SCENARIO 3: Choppy/Neutral (High Vol, No Direction)")
print("-" * 60)
# Whipsaw price action with high volume both ways
prices_chop = 451 + np.cumsum(np.random.randn(60) * 0.4)
volumes_chop = np.random.randint(2000, 8000, 60)

df_chop = pd.DataFrame({
    "t_event": pd.date_range(end=now, periods=60, freq="1min"),
    "price": prices_chop,
    "volume": volumes_chop
})

features_chop = compute_sentiment_v0("SPY", now, df_chop)
print(f"Regime: {features_chop.present.regime}")
print(f"Price momentum Z: {features_chop.present.price_momo_z:.2f}")
print(f"Vol momentum Z: {features_chop.present.vol_momo_z:.2f}")
print(f"Confidence: {features_chop.present.conf:.2f}")
print(f"VoV tilt: {features_chop.future.vov_tilt:.2f}")

print("\n" + "=" * 60)
print("SCENARIO 4: Vol Crush After Event (Post-FOMC)")
print("-" * 60)
# First half: high vol, Second half: collapsing vol
prices_crush = np.concatenate([
    451 + np.cumsum(np.random.randn(30) * 0.5),  # High vol period
    451.5 + np.cumsum(np.random.randn(30) * 0.05)  # Low vol period
])
volumes_crush = np.concatenate([
    np.random.randint(8000, 12000, 30),  # High volume
    np.random.randint(1000, 2000, 30)    # Low volume
])

df_crush = pd.DataFrame({
    "t_event": pd.date_range(end=now, periods=60, freq="1min"),
    "price": prices_crush,
    "volume": volumes_crush
})

features_crush = compute_sentiment_v0("SPY", now, df_crush)
print(f"Regime: {features_crush.present.regime}")
print(f"Vol momentum Z: {features_crush.present.vol_momo_z:.2f}")
print(f"Events: {features_crush.past.events}")
print(f"Future confidence: {features_crush.future.conf:.2f}")

print("\n" + "=" * 60)
print("SCENARIO 5: News-Driven Rally")
print("-" * 60)
# Moderate trend but strong positive news
prices_news = 451 + np.linspace(0, 1, 60) + np.random.randn(60) * 0.1
volumes_news = np.random.randint(3000, 4000, 60)

df_news = pd.DataFrame({
    "t_event": pd.date_range(end=now, periods=60, freq="1min"),
    "price": prices_news,
    "volume": volumes_news
})

# Strong positive news bias
features_news = compute_sentiment_v0("SPY", now, df_news, news_bias=0.8)
print(f"Regime: {features_news.present.regime}")
print(f"Price momentum Z: {features_news.present.price_momo_z:.2f}")
print(f"News bias effect: Risk-on despite modest momentum")
print(f"Confidence: {features_news.present.conf:.2f}")