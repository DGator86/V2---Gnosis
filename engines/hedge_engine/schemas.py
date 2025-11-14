from __future__ import annotations

from typing import Dict, List, Optional

import pandas as pd
from pydantic import BaseModel, Field, validator


class HedgeEngineConfig(BaseModel):
    """Configuration for pure hedge field calculations."""

    price_grid_pct_width: float = Field(
        0.08,
        description="Symmetric width around spot for price grid (e.g., 0.08 = ±8%).",
    )
    price_grid_points: int = Field(
        201,
        description="Number of price grid points across [spot*(1-w), spot*(1+w)].",
    )
    realized_vol_lookback: int = Field(
        20,
        description="Lookback (bars) for realized volatility computation.",
    )
    gamma_smoothing_lambda: float = Field(
        5.0,
        description="Smoothing parameter for gamma profile (higher = smoother).",
    )
    vanna_weight: float = Field(
        0.6,
        description="Relative contribution of vanna to total hedge field.",
    )
    charm_weight: float = Field(
        0.4,
        description="Relative contribution of charm to total hedge field.",
    )
    energy_scale: float = Field(
        1.0,
        description="Scale factor for 'energy to move price' metrics.",
    )


class UnderlyingSnapshot(BaseModel):
    """Snapshot of underlying state required for hedge field computation."""

    symbol: str
    timestamp: pd.Timestamp
    spot_price: float
    intraday_return: float = 0.0
    realized_vol_20d: float = 0.0
    atr: float = 0.0
    vix_level: Optional[float] = None

    @validator("spot_price")
    def _spot_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("spot_price must be positive.")
        return v


class OptionStrikeExposure(BaseModel):
    """Aggregated dealer exposure per strike for a given tenor."""

    strike: float
    gamma: float
    vanna: float
    charm: float
    open_interest: int
    notional: float


class OptionTenorExposure(BaseModel):
    """Aggregated dealer exposure for a single expiry (tenor)."""

    expiry: pd.Timestamp
    dte: float
    exposures: List[OptionStrikeExposure]
    total_gamma: float
    total_vanna: float
    total_charm: float
    total_notional: float
    liquidity_score: float


class OptionsSurfaceSnapshot(BaseModel):
    """Simplified options surface view consumed by the Hedge Engine."""

    symbol: str
    timestamp: pd.Timestamp
    tenors: List[OptionTenorExposure]


class DealerPositionSnapshot(BaseModel):
    """Dealer net positioning / skew information (if available)."""

    symbol: str
    timestamp: pd.Timestamp
    net_gamma_sign: Optional[int] = None
    net_vega_sign: Optional[int] = None
    net_delta_sign: Optional[int] = None


class StructuralLevels(BaseModel):
    """Structural levels extracted from a single scalar field."""

    maxima_levels: List[float] = Field(
        default_factory=list,
        description="Price levels where the field has local maxima.",
    )
    minima_levels: List[float] = Field(
        default_factory=list,
        description="Price levels where the field has local minima.",
    )
    low_curvature_levels: List[float] = Field(
        default_factory=list,
        description="Price levels where curvature is low (voids/plateaus).",
    )


class GreekFieldArrays(BaseModel):
    """Raw arrays for all hedge fields and their derivatives on the price grid."""

    price_grid: List[float]

    gamma_field: List[float]
    vanna_field: List[float]
    charm_field: List[float]
    total_field: List[float]

    d_field_dS: List[float]
    d2_field_dS2: List[float]

    potential: List[float]

    elasticity: List[float]
    energy_1pct: List[float]


class GreekStructuralSummary(BaseModel):
    """Structural levels per Greek and for the total field."""

    gamma_struct: StructuralLevels
    vanna_struct: StructuralLevels
    charm_struct: StructuralLevels
    total_struct: StructuralLevels


class TenorFieldContribution(BaseModel):
    """How much a single tenor contributes to the total field."""

    expiry: pd.Timestamp
    dte: float
    weight: float
    gamma_field: List[float]
    vanna_field: List[float]
    charm_field: List[float]


class ElasticitySummary(BaseModel):
    """Aggregated metrics over elasticity and energy fields."""

    spot_elasticity: float
    spot_energy_to_move_1pct: float
    spot_energy_to_move_atr: float
    mean_elasticity: float
    max_elasticity: float
    min_elasticity: float


class HedgeEngineInputs(BaseModel):
    """Single-bar input bundle to the Hedge Engine."""

    underlying: UnderlyingSnapshot
    options_surface: OptionsSurfaceSnapshot
    dealer_position: Optional[DealerPositionSnapshot] = None
    config: Optional[HedgeEngineConfig] = None


class HedgeEngineOutput(BaseModel):
    """Pure, data-dense output from the Hedge Engine."""

    underlying: UnderlyingSnapshot
    config_used: HedgeEngineConfig

    fields: GreekFieldArrays
    structural: GreekStructuralSummary
    elasticity_summary: ElasticitySummary

    tenor_contributions: List[TenorFieldContribution]
    options_surface_meta: Dict[str, float]
    diagnostics: Dict[str, float]
