from __future__ import annotations

"""
Elasticity calculation - THE CORE THEORY.

Elasticity = resistance of price to movement = market stiffness.

This is derived from:
- Gamma (curvature of supply/demand)
- Vanna (vol-dependent elasticity reshaping)
- Charm (time-decay elasticity drift)
- OI distribution (density wells)
- Liquidity (friction coefficient)

Elasticity determines the energy required to move price.
"""

import polars as pl

from engines.hedge.models import (
    CharmFieldOutput,
    ElasticityOutput,
    GammaFieldOutput,
    GreekInputs,
    VannaFieldOutput,
)


def calculate_elasticity(
    inputs: GreekInputs,
    gamma_field: GammaFieldOutput,
    vanna_field: VannaFieldOutput,
    charm_field: CharmFieldOutput,
    config: dict,
) -> ElasticityOutput:
    """
    Calculate market elasticity from Greek fields.
    
    THEORY:
    -------
    Elasticity of the supply/demand curves changes dynamically due to Greeks.
    
    - GAMMA: Determines curvature of the supply-demand curve
      Higher |gamma| = higher curvature = higher elasticity (more resistance)
    
    - VANNA: Volatility-dependent elasticity reshaping
      High vanna = elasticity changes with vol shocks
    
    - CHARM: Time-decay-driven elasticity drift
      High charm = elasticity decays over time
    
    - OI DISTRIBUTION: Local "density wells" that raise elasticity
      Concentrated OI = higher local elasticity (pin zones)
    
    - LIQUIDITY: Determines friction coefficient
      Low liquidity = higher friction = higher effective elasticity
    
    FORMULA:
    --------
    elasticity = base_elasticity * gamma_component * vanna_modifier * charm_modifier 
                 * oi_density_modifier * liquidity_friction
    
    This elasticity is then used to calculate movement energy.
    
    Args:
        inputs: Raw Greek inputs with liquidity data
        gamma_field: Gamma pressure field
        vanna_field: Vanna pressure field
        charm_field: Charm decay field
        config: Configuration parameters
        
    Returns:
        ElasticityOutput with directional elasticity values
    """
    chain = inputs.chain
    spot = inputs.spot
    liquidity_lambda = inputs.liquidity_lambda
    
    # Base elasticity (dimensionless resistance factor)
    base_elasticity = config.get("base_elasticity", 1.0)
    
    # ============================================================
    # GAMMA COMPONENT
    # ============================================================
    # Gamma creates curvature in the supply-demand response
    # Higher |gamma| = more resistance to movement
    gamma_exposure = gamma_field.gamma_exposure
    gamma_magnitude = abs(gamma_exposure)
    
    # Normalize gamma to elasticity contribution
    gamma_scale = config.get("gamma_elasticity_scale", 1e-7)
    gamma_component = 1.0 + gamma_magnitude * gamma_scale
    
    # Sign matters: negative gamma (short) REDUCES elasticity (accelerates moves)
    if gamma_field.dealer_gamma_sign < 0:
        gamma_component = 1.0 / gamma_component  # Invert for destabilizing effect
    
    # ============================================================
    # VANNA COMPONENT
    # ============================================================
    # Vanna modifies elasticity based on vol sensitivity
    vanna_magnitude = abs(vanna_field.vanna_exposure)
    vanna_scale = config.get("vanna_elasticity_scale", 1e-7)
    # Use absolute value of vol_sensitivity to ensure positive contribution
    vanna_modifier = 1.0 + vanna_magnitude * vanna_scale * abs(vanna_field.vol_sensitivity)
    
    # ============================================================
    # CHARM COMPONENT
    # ============================================================
    # Charm creates time-decay drift in elasticity
    charm_magnitude = abs(charm_field.charm_exposure)
    charm_scale = config.get("charm_elasticity_scale", 1e-7)
    charm_modifier = 1.0 + charm_magnitude * charm_scale * charm_field.decay_acceleration
    
    # ============================================================
    # OI DENSITY MODIFIER
    # ============================================================
    # Concentrated OI creates "wells" that increase local elasticity
    if not chain.is_empty() and "open_interest" in chain.columns:
        total_oi = float(chain["open_interest"].sum())
        # Calculate OI concentration (Herfindahl-like index)
        if total_oi > 0:
            oi_shares = chain["open_interest"] / total_oi
            oi_concentration = float((oi_shares**2).sum())
        else:
            oi_concentration = 0.0
        
        # Higher concentration = more resistance at key strikes
        oi_density_modifier = 1.0 + oi_concentration * config.get("oi_concentration_scale", 2.0)
    else:
        oi_density_modifier = 1.0
    
    # ============================================================
    # LIQUIDITY FRICTION
    # ============================================================
    # Liquidity determines friction coefficient
    # High liquidity_lambda (Amihud) = low liquidity = high friction
    liquidity_friction = 1.0 + liquidity_lambda * config.get("liquidity_friction_scale", 1.0)
    
    # ============================================================
    # COMBINED ELASTICITY
    # ============================================================
    elasticity = (
        base_elasticity
        * gamma_component
        * vanna_modifier
        * charm_modifier
        * oi_density_modifier
        * liquidity_friction
    )
    
    # Ensure positive elasticity (by definition)
    elasticity = max(elasticity, 0.01)
    
    # ============================================================
    # DIRECTIONAL ELASTICITY (UP vs DOWN)
    # ============================================================
    # Asymmetry comes from strike distribution and Greek skew
    
    # Upside elasticity: resistance to moving UP
    gamma_up_pressure = gamma_field.gamma_pressure_up
    vanna_up_pressure = vanna_field.vanna_pressure_up
    
    # Normalize upside pressures to elasticity modifier
    up_pressure_total = abs(gamma_up_pressure) + abs(vanna_up_pressure)
    up_modifier = 1.0 + up_pressure_total * config.get("directional_pressure_scale", 1e-8)
    
    elasticity_up = elasticity * up_modifier
    
    # Downside elasticity: resistance to moving DOWN
    gamma_down_pressure = gamma_field.gamma_pressure_down
    vanna_down_pressure = vanna_field.vanna_pressure_down
    
    down_pressure_total = abs(gamma_down_pressure) + abs(vanna_down_pressure)
    down_modifier = 1.0 + down_pressure_total * config.get("directional_pressure_scale", 1e-8)
    
    elasticity_down = elasticity * down_modifier
    
    # Asymmetry ratio
    asymmetry_ratio = elasticity_up / (elasticity_down + 1e-9)
    
    # ============================================================
    # METADATA
    # ============================================================
    metadata = {
        "gamma_component": float(gamma_component),
        "vanna_modifier": float(vanna_modifier),
        "charm_modifier": float(charm_modifier),
        "oi_density_modifier": float(oi_density_modifier),
        "liquidity_friction": float(liquidity_friction),
        "up_pressure_total": float(up_pressure_total),
        "down_pressure_total": float(down_pressure_total),
    }
    
    return ElasticityOutput(
        elasticity=elasticity,
        elasticity_up=elasticity_up,
        elasticity_down=elasticity_down,
        asymmetry_ratio=asymmetry_ratio,
        gamma_component=gamma_component,
        vanna_component=vanna_modifier,
        charm_component=charm_modifier,
        liquidity_friction=liquidity_friction,
        oi_density_modifier=oi_density_modifier,
        metadata=metadata,
    )
