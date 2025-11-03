from __future__ import annotations
from datetime import datetime
from ..schemas.base import LiquidityFeatures, LiquidityPast, LiquidityPresent, LiquidityFuture, Zone

def compute(symbol: str, bar: datetime, price: float) -> LiquidityFeatures:
    past = LiquidityPast(zones_held=2, zones_broken=1, slippage_err_bps=5.0)
    present = LiquidityPresent(
        support=[Zone(lo=price-1.0, hi=price-0.6)],
        resistance=[Zone(lo=price+0.6, hi=price+1.0)],
        amihud=0.004, lambda_impact=1.2, conf=0.7
    )
    future = LiquidityFuture(zone_survival=0.72, slippage_cone_bps=[5,10,20],
                             next_magnet=price+0.8, eta_bars=6, conf=0.66)
    return LiquidityFeatures(past=past, present=present, future=future)