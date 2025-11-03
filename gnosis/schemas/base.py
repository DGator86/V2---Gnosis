from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime

# minimal L1-Thin (units normalized pre-engine: USD, decimal IV, years)
class L1Thin(BaseModel):
    symbol: str
    t_event: datetime
    source: str
    units_normalized: bool = True
    price: Optional[float] = None
    volume: Optional[float] = None
    dollar_volume: Optional[float] = None
    iv_dec: Optional[float] = None
    oi: Optional[int] = None
    raw_ref: str

# Hedge
class HedgePast(BaseModel):
    exhaustion_score: float = 0.0
    window_bars: int = 20
    method: str = "linear"

class HedgePresent(BaseModel):
    hedge_force: float
    regime: str              # "pin" | "neutral" | "breakout"
    wall_dist: Optional[float] = None
    conf: float = 0.5
    half_life_bars: int = 6

class HedgeFuture(BaseModel):
    q10: float; q50: float; q90: float
    hit_prob_tp1: float
    eta_bars: int
    conf: float = 0.5

class HedgeFeatures(BaseModel):
    past: HedgePast
    present: HedgePresent
    future: HedgeFuture

# Liquidity
class Zone(BaseModel):
    lo: float; hi: float

class LiquidityPast(BaseModel):
    zones_held: int = 0
    zones_broken: int = 0
    slippage_err_bps: float = 0.0

class LiquidityPresent(BaseModel):
    support: List[Zone] = Field(default_factory=list)
    resistance: List[Zone] = Field(default_factory=list)
    amihud: float
    lambda_impact: float
    conf: float = 0.5

class LiquidityFuture(BaseModel):
    zone_survival: float
    slippage_cone_bps: List[int] = Field(default_factory=lambda: [5,10,20])
    next_magnet: Optional[float] = None
    eta_bars: int = 6
    conf: float = 0.5

class LiquidityFeatures(BaseModel):
    past: LiquidityPast
    present: LiquidityPresent
    future: LiquidityFuture

# Sentiment
class SentimentPast(BaseModel):
    events: List[str] = Field(default_factory=list)
    iv_drift: float = 0.0

class SentimentPresent(BaseModel):
    regime: str              # "risk_on" | "neutral" | "risk_off"
    price_momo_z: float
    vol_momo_z: float
    conf: float = 0.5

class SentimentFuture(BaseModel):
    flip_prob_10b: float
    vov_tilt: float
    conf: float = 0.5

class SentimentFeatures(BaseModel):
    past: SentimentPast
    present: SentimentPresent
    future: SentimentFuture

# Canonical feature row (what Agents/Composer read)
class L3Canonical(BaseModel):
    symbol: str
    bar: datetime
    feature_set_id: str = "v0.1.0"
    hedge: Optional[HedgeFeatures] = None
    liquidity: Optional[LiquidityFeatures] = None
    sentiment: Optional[SentimentFeatures] = None
    quality: Dict[str, float] = Field(default_factory=lambda: {"fill_rate": 1.0})