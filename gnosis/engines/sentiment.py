from __future__ import annotations
from datetime import datetime
from ..schemas.base import SentimentFeatures, SentimentPast, SentimentPresent, SentimentFuture

def compute(symbol: str, bar: datetime, price: float) -> SentimentFeatures:
    past = SentimentPast(events=[], iv_drift=-0.1)
    present = SentimentPresent(regime="risk_on", price_momo_z=0.6, vol_momo_z=-0.4, conf=0.65)
    future = SentimentFuture(flip_prob_10b=0.2, vov_tilt=0.3, conf=0.6)
    return SentimentFeatures(past=past, present=present, future=future)