from __future__ import annotations

"""
Advanced regime detection with jump-diffusion handling.

Regimes include:
- High gamma compression
- Low gamma expansion  
- High vanna (vol-driven)
- High charm decay
- Jump risk
- Cross-asset correlation amplification
"""

from engines.hedge.models import (
    CharmFieldOutput,
    ElasticityOutput,
    GammaFieldOutput,
    GreekInputs,
    MovementEnergyOutput,
    RegimeOutput,
    VannaFieldOutput,
)


def detect_regime(
    inputs: GreekInputs,
    gamma_field: GammaFieldOutput,
    vanna_field: VannaFieldOutput,
    charm_field: CharmFieldOutput,
    elasticity: ElasticityOutput,
    energy: MovementEnergyOutput,
    config: dict,
) -> RegimeOutput:
    """
    Detect multi-dimensional market regime.
    
    This classifies the current dealer-positioning state across multiple
    dimensions to determine the "shape" of the potential function.
    
    REGIME DIMENSIONS:
    ------------------
    1. Gamma regime: compression vs expansion
    2. Vanna regime: vol-driven vs stable
    3. Charm regime: decay-dominant vs neutral
    4. Jump risk: continuous vs jump-diffusion
    5. Volatility regime: high vs low vol environment
    6. Cross-asset: correlated vs independent
    
    POTENTIAL SHAPES:
    -----------------
    - quadratic: Low gamma, standard parabolic
    - cubic: Moderate gamma, asymmetric
    - double_well: High vanna + negative gamma, bistable
    - quartic: Extreme regimes
    
    Args:
        inputs: Raw Greek inputs with vol data
        gamma_field: Gamma pressure field
        vanna_field: Vanna pressure field
        charm_field: Charm decay field
        elasticity: Elasticity calculation
        energy: Movement energy calculation
        config: Configuration parameters
        
    Returns:
        RegimeOutput with multi-dimensional classification
    """
    vix = inputs.vix or 20.0
    vol_of_vol = inputs.vol_of_vol
    
    # ============================================================
    # GAMMA REGIME
    # ============================================================
    gamma_regime = gamma_field.gamma_regime
    
    # ============================================================
    # VANNA REGIME
    # ============================================================
    vanna_regime = vanna_field.vanna_regime
    
    # ============================================================
    # CHARM REGIME
    # ============================================================
    charm_regime = charm_field.charm_regime
    
    # ============================================================
    # JUMP RISK REGIME (SWOT FIX: Jump-diffusion term)
    # ============================================================
    # Replace heuristic jump detection with jump-diffusion state
    # Based on:
    # - Vol-of-vol (measure of jump intensity)
    # - VIX level (fear gauge)
    # - Energy acceleration likelihood
    
    jump_risk_score = 0.0
    
    # Vol-of-vol contribution (higher = more jumpy)
    vol_of_vol_threshold = config.get("vol_of_vol_jump_threshold", 0.4)
    if vol_of_vol > vol_of_vol_threshold:
        jump_risk_score += (vol_of_vol - vol_of_vol_threshold) * 2.0
    
    # VIX contribution (fear)
    vix_jump_threshold = config.get("vix_jump_threshold", 30.0)
    if vix > vix_jump_threshold:
        jump_risk_score += (vix - vix_jump_threshold) / 20.0
    
    # Acceleration likelihood (low elasticity + high pressure)
    if energy.acceleration_likelihood > 0.7:
        jump_risk_score += energy.acceleration_likelihood
    
    # Short gamma amplifies jump risk
    if gamma_regime == "short_gamma_squeeze":
        jump_risk_score *= 1.5
    
    # Classify jump risk regime
    if jump_risk_score > 2.0:
        jump_risk_regime = "high_jump_risk"
    elif jump_risk_score > 1.0:
        jump_risk_regime = "moderate_jump_risk"
    else:
        jump_risk_regime = "continuous_diffusion"
    
    # ============================================================
    # VOLATILITY REGIME
    # ============================================================
    if vix > 30:
        volatility_regime = "high_vol"
    elif vix > 20:
        volatility_regime = "moderate_vol"
    else:
        volatility_regime = "low_vol"
    
    # ============================================================
    # CROSS-ASSET CORRELATION
    # ============================================================
    # Placeholder: would integrate SPX/SPY/VIX correlation here
    # For now, infer from vanna and VIX relationship
    if vanna_regime in ["high_vanna_high_vol", "high_vanna_low_vol"]:
        cross_asset_correlation = 0.7  # High vanna implies strong spot-vol correlation
    else:
        cross_asset_correlation = 0.3
    
    # ============================================================
    # PRIMARY REGIME (HIERARCHICAL)
    # ============================================================
    # Prioritize most impactful regime
    if jump_risk_regime == "high_jump_risk":
        primary_regime = "jump_risk_dominant"
    elif gamma_regime in ["short_gamma_squeeze", "long_gamma_compression"]:
        primary_regime = gamma_regime
    elif vanna_regime in ["high_vanna_high_vol", "high_vanna_low_vol"]:
        primary_regime = vanna_regime
    elif charm_regime == "high_charm_decay_acceleration":
        primary_regime = charm_regime
    else:
        primary_regime = "neutral"
    
    # ============================================================
    # POTENTIAL SHAPE (CUBIC → QUARTIC → DOUBLE-WELL MIXING)
    # ============================================================
    # Determine the shape of the potential function based on regime
    
    gamma_magnitude = abs(gamma_field.gamma_exposure)
    vanna_magnitude = abs(vanna_field.vanna_exposure)
    
    gamma_ratio = elasticity.metadata.get("gamma_component", 1.0)
    vanna_ratio = elasticity.metadata.get("vanna_modifier", 1.0)
    
    # Low gamma = quadratic (standard parabolic potential)
    if gamma_magnitude < config.get("gamma_quadratic_threshold", 1e6):
        potential_shape = "quadratic"
    
    # Moderate gamma + asymmetry = cubic
    elif gamma_magnitude < config.get("gamma_cubic_threshold", 5e6):
        potential_shape = "cubic"
    
    # High vanna + negative gamma = double-well (bistable)
    elif (
        vanna_magnitude > config.get("vanna_double_well_threshold", 5e6)
        and gamma_field.dealer_gamma_sign < 0
        and vanna_ratio > 1.5
    ):
        potential_shape = "double_well"
    
    # Extreme conditions = quartic
    elif jump_risk_regime == "high_jump_risk" or gamma_magnitude > config.get("gamma_quartic_threshold", 1e7):
        potential_shape = "quartic"
    
    else:
        potential_shape = "cubic"  # Default
    
    # ============================================================
    # REGIME CONFIDENCE & STABILITY
    # ============================================================
    # How confident are we in this regime classification?
    
    # Confidence based on data quality and consistency
    regime_alignment_score = 0.0
    
    # Check if sub-regimes are consistent
    if gamma_regime != "neutral":
        regime_alignment_score += 0.25
    if vanna_regime != "neutral":
        regime_alignment_score += 0.25
    if charm_regime != "neutral":
        regime_alignment_score += 0.25
    if jump_risk_regime != "continuous_diffusion":
        regime_alignment_score += 0.25
    
    regime_confidence = min(1.0, regime_alignment_score)
    
    # Stability: how likely is regime to persist?
    # High elasticity + low energy = stable regime
    # Low elasticity + high energy = unstable regime
    stability_factor = elasticity.elasticity / (energy.barrier_strength + 1.0)
    regime_stability = min(1.0, stability_factor)
    
    # ============================================================
    # METADATA
    # ============================================================
    metadata = {
        "jump_risk_score": float(jump_risk_score),
        "regime_alignment_score": float(regime_alignment_score),
        "stability_factor": float(stability_factor),
        "gamma_magnitude": float(gamma_magnitude),
        "vanna_magnitude": float(vanna_magnitude),
    }
    
    return RegimeOutput(
        primary_regime=primary_regime,
        gamma_regime=gamma_regime,
        vanna_regime=vanna_regime,
        charm_regime=charm_regime,
        jump_risk_regime=jump_risk_regime,
        volatility_regime=volatility_regime,
        potential_shape=potential_shape,
        regime_confidence=regime_confidence,
        regime_stability=regime_stability,
        cross_asset_correlation=cross_asset_correlation,
        metadata=metadata,
    )
