from __future__ import annotations
from datetime import datetime
from ..schemas.base import HedgeFeatures, HedgePast, HedgePresent, HedgeFuture

def compute(symbol: str, bar: datetime, price: float) -> HedgeFeatures:
    past = HedgePast(exhaustion_score=0.3, window_bars=20, method="linear")
    present = HedgePresent(hedge_force=0.6, regime="pin", wall_dist=0.5, conf=0.7, half_life_bars=6)
    future = HedgeFuture(q10=-0.3, q50=0.2, q90=0.8, hit_prob_tp1=0.58, eta_bars=8, conf=0.65)
    return HedgeFeatures(past=past, present=present, future=future)