# agents/trade_agent/vol_surface.py

"""
Volatility Surface Intelligence Module

Provides institutional-grade volatility surface analysis for options strategy selection.
Computes IV rank, IV percentile, skew metrics, and volatility signals to enhance
Trade Agent v2 with surface-based decision logic.

Key Capabilities:
- Load and parse volatility surface data (ORATS/CBOE format)
- Compute IV rank and IV percentile (lookback periods)
- Detect put/call skew and wing compression
- Generate vol expansion/crush probability signals
- Extract term structure slopes (calendar spread intel)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

import numpy as np
from pydantic import BaseModel, Field


@dataclass
class IVDataPoint:
    """Single IV observation for a specific strike/expiry."""
    strike: float
    expiry: date
    iv: float  # Implied volatility (annualized, e.g., 0.25 = 25%)
    delta: Optional[float] = None  # Option delta (for skew analysis)
    option_type: str = "call"  # "call" or "put"


class SurfaceSlice(BaseModel):
    """
    A single expiry's IV curve across strikes.
    Used for skew analysis and wing detection.
    """
    expiry: date
    dte: int  # Days to expiration
    strikes: List[float] = Field(default_factory=list)
    ivs: List[float] = Field(default_factory=list)
    call_ivs: List[float] = Field(default_factory=list)
    put_ivs: List[float] = Field(default_factory=list)
    atm_iv: float = 0.0
    
    def get_skew(self, strike_offset_pct: float = 0.05) -> float:
        """
        Compute put/call IV skew.
        
        Args:
            strike_offset_pct: Offset from ATM (e.g., 0.05 = 5% OTM)
        
        Returns:
            Skew metric: positive = put premium, negative = call premium
        """
        if not self.call_ivs or not self.put_ivs:
            return 0.0
        
        # Simple skew: average put IV - average call IV
        avg_put_iv = np.mean(self.put_ivs) if self.put_ivs else 0.0
        avg_call_iv = np.mean(self.call_ivs) if self.call_ivs else 0.0
        
        return float(avg_put_iv - avg_call_iv)
    
    def get_wing_spread(self) -> float:
        """
        Measure IV spread between wings (far OTM options).
        
        Returns:
            Wing spread: high spread = rich wings (favorable for selling)
        """
        if len(self.ivs) < 5:
            return 0.0
        
        # Compare far OTM vs ATM
        sorted_ivs = sorted(self.ivs)
        wing_ivs = [sorted_ivs[0], sorted_ivs[-1]]  # Extremes
        atm_iv = self.atm_iv if self.atm_iv > 0 else np.median(self.ivs)
        
        wing_avg = np.mean(wing_ivs)
        return float(wing_avg - atm_iv)


class VolSurface(BaseModel):
    """
    Complete volatility surface for a symbol.
    Contains historical IV data and current surface slices.
    """
    symbol: str
    as_of_date: date
    slices: List[SurfaceSlice] = Field(default_factory=list)
    historical_ivs: List[float] = Field(
        default_factory=list,
        description="Historical ATM IV values (for IV rank calculation)"
    )
    current_atm_iv: float = 0.0
    
    def get_slice_by_dte(self, target_dte: int, tolerance: int = 5) -> Optional[SurfaceSlice]:
        """
        Get surface slice closest to target DTE.
        
        Args:
            target_dte: Desired days to expiration
            tolerance: Max days difference to accept
        
        Returns:
            SurfaceSlice if found within tolerance, else None
        """
        if not self.slices:
            return None
        
        # Find closest match
        closest_slice = min(self.slices, key=lambda s: abs(s.dte - target_dte))
        
        if abs(closest_slice.dte - target_dte) <= tolerance:
            return closest_slice
        
        return None
    
    def get_term_structure_slope(self) -> float:
        """
        Compute IV term structure slope (front month vs back month).
        
        Returns:
            Positive = backwardation (near-term vol higher)
            Negative = contango (longer-term vol higher)
        """
        if len(self.slices) < 2:
            return 0.0
        
        # Sort by DTE
        sorted_slices = sorted(self.slices, key=lambda s: s.dte)
        
        front_iv = sorted_slices[0].atm_iv
        back_iv = sorted_slices[-1].atm_iv
        
        # Slope: (front - back) / front
        if front_iv == 0:
            return 0.0
        
        return float((front_iv - back_iv) / front_iv)


class SkewMetrics(BaseModel):
    """Comprehensive skew analysis for strategy selection."""
    put_call_skew: float = Field(
        description="Put IV - Call IV (positive = put premium)"
    )
    skew_direction: str = Field(
        default="neutral",
        description="'put_rich', 'call_rich', or 'neutral'"
    )
    wing_spread: float = Field(
        description="Wing IV - ATM IV (positive = rich wings)"
    )
    term_structure_slope: float = Field(
        description="Front IV - Back IV slope"
    )


class IVRankPercentile(BaseModel):
    """IV rank and percentile metrics."""
    iv_rank: float = Field(
        ge=0.0,
        le=1.0,
        description="Current IV rank (0-1) based on lookback period"
    )
    iv_percentile: float = Field(
        ge=0.0,
        le=100.0,
        description="Current IV percentile (0-100)"
    )
    lookback_days: int = Field(
        default=252,
        description="Lookback period for rank calculation"
    )
    current_iv: float
    iv_high: float
    iv_low: float


class VolatilitySignals(BaseModel):
    """
    Actionable volatility signals for strategy routing.
    
    These signals enhance Trade Agent v2 strategy selection by adding
    surface-based intelligence beyond simple volatility regime classification.
    """
    expansion_probability: float = Field(
        ge=0.0,
        le=1.0,
        description="Probability of IV expansion (0-1)"
    )
    crush_risk: float = Field(
        ge=0.0,
        le=1.0,
        description="Risk of IV crush post-event (0-1)"
    )
    skew_favorable_for_calendars: bool = Field(
        description="True if skew profile favors calendar spreads"
    )
    rich_wings: bool = Field(
        description="True if wings are expensive (favorable for butterflies/condors)"
    )
    term_structure_backwardation: bool = Field(
        description="True if near-term IV > longer-term (event risk)"
    )
    iv_regime: str = Field(
        description="'low', 'mid', 'high', 'expansion', or 'crush'"
    )


def load_vol_surface(
    symbol: str,
    as_of_date: datetime,
    iv_data: List[IVDataPoint],
    historical_ivs: Optional[List[float]] = None,
) -> VolSurface:
    """
    Load and parse volatility surface from raw IV data.
    
    Args:
        symbol: Ticker symbol
        as_of_date: Date of the surface snapshot
        iv_data: List of IV observations across strikes/expiries
        historical_ivs: Historical ATM IV values for IV rank calculation
    
    Returns:
        VolSurface object with organized slices
    """
    if historical_ivs is None:
        historical_ivs = []
    
    # Group data by expiry
    expiry_map: Dict[date, List[IVDataPoint]] = {}
    
    for point in iv_data:
        if point.expiry not in expiry_map:
            expiry_map[point.expiry] = []
        expiry_map[point.expiry].append(point)
    
    # Build slices
    slices: List[SurfaceSlice] = []
    
    for expiry, points in expiry_map.items():
        dte = (expiry - as_of_date.date()).days
        
        strikes = [p.strike for p in points]
        ivs = [p.iv for p in points]
        call_ivs = [p.iv for p in points if p.option_type == "call"]
        put_ivs = [p.iv for p in points if p.option_type == "put"]
        
        # Estimate ATM IV (median of all IVs for this expiry)
        atm_iv = float(np.median(ivs)) if ivs else 0.0
        
        slice_obj = SurfaceSlice(
            expiry=expiry,
            dte=dte,
            strikes=strikes,
            ivs=ivs,
            call_ivs=call_ivs,
            put_ivs=put_ivs,
            atm_iv=atm_iv,
        )
        
        slices.append(slice_obj)
    
    # Compute current ATM IV (use front month if available)
    current_atm_iv = 0.0
    if slices:
        front_slice = min(slices, key=lambda s: s.dte)
        current_atm_iv = front_slice.atm_iv
    
    return VolSurface(
        symbol=symbol,
        as_of_date=as_of_date.date(),
        slices=slices,
        historical_ivs=historical_ivs,
        current_atm_iv=current_atm_iv,
    )


def get_iv_slice(surface: VolSurface, expiry: date) -> Optional[SurfaceSlice]:
    """
    Extract a specific expiry slice from the surface.
    
    Args:
        surface: VolSurface object
        expiry: Target expiry date
    
    Returns:
        SurfaceSlice if found, else None
    """
    for slice_obj in surface.slices:
        if slice_obj.expiry == expiry:
            return slice_obj
    
    return None


def compute_iv_rank(
    surface: VolSurface,
    lookback_days: int = 252,
) -> IVRankPercentile:
    """
    Compute IV rank and IV percentile for current ATM IV.
    
    IV Rank = (Current IV - Min IV) / (Max IV - Min IV)
    IV Percentile = Percentage of days with lower IV
    
    Args:
        surface: VolSurface with historical_ivs populated
        lookback_days: Lookback period (default 252 = 1 year)
    
    Returns:
        IVRankPercentile object with rank and percentile metrics
    """
    historical = surface.historical_ivs[-lookback_days:] if len(surface.historical_ivs) > lookback_days else surface.historical_ivs
    
    if not historical:
        # No historical data - return neutral metrics
        return IVRankPercentile(
            iv_rank=0.5,
            iv_percentile=50.0,
            lookback_days=lookback_days,
            current_iv=surface.current_atm_iv,
            iv_high=surface.current_atm_iv,
            iv_low=surface.current_atm_iv,
        )
    
    current_iv = surface.current_atm_iv
    iv_high = float(np.max(historical))
    iv_low = float(np.min(historical))
    
    # IV Rank
    if iv_high == iv_low:
        iv_rank = 0.5
    else:
        iv_rank = (current_iv - iv_low) / (iv_high - iv_low)
    
    # IV Percentile
    below_current = sum(1 for iv in historical if iv < current_iv)
    iv_percentile = (below_current / len(historical)) * 100.0
    
    return IVRankPercentile(
        iv_rank=float(np.clip(iv_rank, 0.0, 1.0)),
        iv_percentile=float(np.clip(iv_percentile, 0.0, 100.0)),
        lookback_days=lookback_days,
        current_iv=current_iv,
        iv_high=iv_high,
        iv_low=iv_low,
    )


def compute_skew_metrics(
    surface: VolSurface,
    target_dte: int = 30,
) -> SkewMetrics:
    """
    Compute comprehensive skew metrics for strategy selection.
    
    Args:
        surface: VolSurface object
        target_dte: Target DTE for analysis (default 30 days)
    
    Returns:
        SkewMetrics object
    """
    slice_obj = surface.get_slice_by_dte(target_dte, tolerance=10)
    
    if not slice_obj:
        # No data - return neutral metrics
        return SkewMetrics(
            put_call_skew=0.0,
            skew_direction="neutral",
            wing_spread=0.0,
            term_structure_slope=0.0,
        )
    
    put_call_skew = slice_obj.get_skew()
    wing_spread = slice_obj.get_wing_spread()
    term_structure_slope = surface.get_term_structure_slope()
    
    # Classify skew direction
    if put_call_skew > 0.02:  # 2% threshold
        skew_direction = "put_rich"
    elif put_call_skew < -0.02:
        skew_direction = "call_rich"
    else:
        skew_direction = "neutral"
    
    return SkewMetrics(
        put_call_skew=put_call_skew,
        skew_direction=skew_direction,
        wing_spread=wing_spread,
        term_structure_slope=term_structure_slope,
    )


def generate_volatility_signals(
    surface: VolSurface,
    iv_rank: IVRankPercentile,
    skew_metrics: SkewMetrics,
) -> VolatilitySignals:
    """
    Generate actionable volatility signals for strategy routing.
    
    This is the key function that transforms surface analytics into
    strategy selection intelligence for Trade Agent v2.
    
    Args:
        surface: VolSurface object
        iv_rank: IV rank/percentile metrics
        skew_metrics: Skew analysis
    
    Returns:
        VolatilitySignals with routing recommendations
    """
    # Expansion probability: high when IV rank is low
    expansion_prob = 1.0 - iv_rank.iv_rank
    
    # Crush risk: high when IV rank is high + backwardation
    crush_risk_base = iv_rank.iv_rank
    if skew_metrics.term_structure_slope > 0.1:  # Strong backwardation
        crush_risk = min(1.0, crush_risk_base * 1.5)
    else:
        crush_risk = crush_risk_base
    
    # Calendar spread favorability: low IV rank + slight backwardation
    calendars_favorable = (
        iv_rank.iv_rank < 0.5 and 
        0.0 < skew_metrics.term_structure_slope < 0.15
    )
    
    # Rich wings: favorable for butterflies and iron condors
    rich_wings = skew_metrics.wing_spread > 0.03  # 3% threshold
    
    # Backwardation detection (event risk)
    backwardation = skew_metrics.term_structure_slope > 0.1
    
    # IV regime classification
    if iv_rank.iv_rank < 0.3:
        iv_regime = "low"
    elif iv_rank.iv_rank < 0.7:
        iv_regime = "mid"
    else:
        iv_regime = "high"
    
    # Override with expansion/crush signals
    if expansion_prob > 0.7:
        iv_regime = "expansion"
    elif crush_risk > 0.7:
        iv_regime = "crush"
    
    return VolatilitySignals(
        expansion_probability=float(np.clip(expansion_prob, 0.0, 1.0)),
        crush_risk=float(np.clip(crush_risk, 0.0, 1.0)),
        skew_favorable_for_calendars=calendars_favorable,
        rich_wings=rich_wings,
        term_structure_backwardation=backwardation,
        iv_regime=iv_regime,
    )
