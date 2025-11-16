"""
Liquidity Agent Schemas - Canonical v1.0

Input/Output schemas for the Liquidity Agent pure interpretation layer.
The Liquidity Agent does NOT compute liquidity metrics.
It ONLY interprets pre-computed Liquidity Engine outputs.
"""

from typing import Dict, List

from pydantic import BaseModel, Field


class LiquidityAgentInput(BaseModel):
    """
    Canonical input surface for the Liquidity Agent.
    
    All fields are outputs of the Liquidity Engine. The agent does NOT compute
    any of these; it only interprets them.
    
    Attributes:
        net_liquidity_pressure: Signed summary of liquidity
                               Positive = absorption/support
                               Negative = distribution/selling pressure
        liquidity_mtf: Multi-timeframe liquidity pressure breakdown
        amihud_lambda: Amihud illiquidity - higher = more price impact per volume
        kyle_lambda: Kyle's lambda estimate - price impact per signed volume
        orderflow_imbalance: Signed OFI - positive = aggressive buy dominance
        book_depth_score: Normalized [0,1+] depth measure
        volume_profile_slope: Slope of volume by price - captures cliffs vs shelves
        liquidity_gaps_score: 0 = smooth, >0 = gaps/thin zones
        dark_pool_bias: Signed dark pool bias (accumulation vs distribution)
        vol_of_liquidity: Volatility of liquidity itself - unstable microstructure
        regime: Liquidity regime from engine
        confidence: Engine-level confidence in metrics
        realized_slippage_score: Expected vs realized slippage comparison
    """
    net_liquidity_pressure: float = Field(
        ...,
        description=(
            "Signed summary of liquidity. Positive implies absorption/support; "
            "negative implies distribution/selling pressure."
        ),
    )
    
    liquidity_mtf: Dict[str, float] = Field(
        default_factory=dict,
        description="Optional multi-timeframe liquidity pressure readings.",
    )
    
    # Microstructure metrics
    amihud_lambda: float = Field(
        ...,
        description="Amihud illiquidity: higher means more price impact per unit volume.",
    )
    
    kyle_lambda: float = Field(
        ...,
        description="Kyle's lambda estimate: price impact per unit signed volume.",
    )
    
    orderflow_imbalance: float = Field(
        ...,
        description="Signed OFI: positive = aggressive buy dominance, negative = aggressive sell dominance.",
    )
    
    book_depth_score: float = Field(
        ...,
        description="Normalized [0,1+] depth measure; higher means deeper visible book.",
    )
    
    volume_profile_slope: float = Field(
        ...,
        description="Slope of volume by price; captures cliffs vs shelves.",
    )
    
    liquidity_gaps_score: float = Field(
        ...,
        description="0 = smooth, >0 = gaps/thin zones (e.g., low resting liquidity).",
    )
    
    dark_pool_bias: float = Field(
        ...,
        description="Signed dark pool bias: positive = net accumulation, negative = net distribution.",
    )
    
    vol_of_liquidity: float = Field(
        ...,
        description="Volatility of liquidity itself; higher means unstable microstructure.",
    )
    
    regime: str = Field(
        ...,
        description=(
            "Liquidity regime assigned by Liquidity Engine: "
            "e.g. 'balanced', 'absorption', 'distribution', 'vacuum', 'transition'."
        ),
    )
    
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Engine-level confidence in the liquidity metrics.",
    )
    
    realized_slippage_score: float = Field(
        ...,
        description=(
            "Signed score comparing expected vs realized slippage. "
            "Negative = worse-than-expected liquidity conditions."
        ),
    )


class LiquidityAgentOutput(BaseModel):
    """
    Canonical output object of the Liquidity Agent, consumed by the Composer.
    
    Attributes:
        direction: Qualitative classification of liquidity environment
        strength: Liquidity fragility / cost to move size [0-1]
        confidence: Trust in this liquidity read [0-1]
        regime: Echoed liquidity regime for Composer context
        notes: Human-readable annotations and warnings
    """
    direction: str = Field(
        ...,
        description=(
            "Qualitative classification: 'supportive', 'weak supportive', "
            "'fragile', 'liquidity vacuum up', 'liquidity vacuum down', "
            "'balanced', 'chaotic'."
        ),
    )
    
    strength: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="0–1 measure of liquidity fragility / cost to move size.",
    )
    
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="0–1 measure of how much we trust this liquidity read.",
    )
    
    regime: str = Field(
        ...,
        description="Echoed liquidity regime, for Composer context.",
    )
    
    notes: List[str] = Field(
        default_factory=list,
        description="Human-readable annotations and warnings.",
    )
