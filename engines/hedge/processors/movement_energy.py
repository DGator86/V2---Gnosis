from __future__ import annotations

"""
Movement energy calculation - ENERGY REQUIRED TO MOVE PRICE.

Energy = Pressure / Elasticity

This quantifies the "cost" to push price through dealer hedge pressure.
Low energy = easy to move
High energy = hard to move (strong barriers)
"""

from engines.hedge.models import (
    CharmFieldOutput,
    ElasticityOutput,
    GammaFieldOutput,
    MovementEnergyOutput,
    VannaFieldOutput,
)


def calculate_movement_energy(
    gamma_field: GammaFieldOutput,
    vanna_field: VannaFieldOutput,
    charm_field: CharmFieldOutput,
    elasticity: ElasticityOutput,
    config: dict,
) -> MovementEnergyOutput:
    """
    Calculate movement energy required to push price through elasticity.
    
    THEORY:
    -------
    Movement energy = Force / Resistance = Pressure / Elasticity
    
    Where:
    - Pressure = dealer hedge pressure (from gamma, vanna, charm)
    - Elasticity = market stiffness (resistance to movement)
    
    High energy = barriers are strong, hard to move price
    Low energy = barriers are weak, easy to move price
    
    This gives a quantifiable measure of "how much firepower is needed
    to move price by ΔP."
    
    DIRECTIONAL INTERPRETATION:
    ---------------------------
    - movement_energy_up: energy needed to push price UP
    - movement_energy_down: energy needed to push price DOWN
    - net_energy: net directional bias
    - energy_asymmetry: up/down ratio (>1 = easier to move up)
    
    ACCELERATION LIKELIHOOD:
    ------------------------
    Low energy + high pressure = high acceleration likelihood
    High energy + low pressure = low acceleration likelihood
    
    Args:
        gamma_field: Gamma pressure field
        vanna_field: Vanna pressure field
        charm_field: Charm decay field
        elasticity: Elasticity calculation
        config: Configuration parameters
        
    Returns:
        MovementEnergyOutput with directional energy metrics
    """
    # ============================================================
    # TOTAL PRESSURE CALCULATION
    # ============================================================
    # Combine gamma, vanna, charm pressures
    
    # Upside pressure (resistance to moving up)
    gamma_up = gamma_field.gamma_pressure_up
    vanna_up = vanna_field.vanna_pressure_up
    charm_up = charm_field.charm_drift_rate if charm_field.charm_drift_rate > 0 else 0.0
    
    total_pressure_up = abs(gamma_up) + abs(vanna_up) + abs(charm_up)
    
    # Downside pressure (resistance to moving down)
    gamma_down = gamma_field.gamma_pressure_down
    vanna_down = vanna_field.vanna_pressure_down
    charm_down = abs(charm_field.charm_drift_rate) if charm_field.charm_drift_rate < 0 else 0.0
    
    total_pressure_down = abs(gamma_down) + abs(vanna_down) + abs(charm_down)
    
    # ============================================================
    # MOVEMENT ENERGY = PRESSURE / ELASTICITY
    # ============================================================
    
    # Energy to move UP
    elasticity_up = elasticity.elasticity_up
    if elasticity_up > 0:
        movement_energy_up = total_pressure_up / elasticity_up
    else:
        movement_energy_up = 0.0
    
    # Energy to move DOWN
    elasticity_down = elasticity.elasticity_down
    if elasticity_down > 0:
        movement_energy_down = total_pressure_down / elasticity_down
    else:
        movement_energy_down = 0.0
    
    # ============================================================
    # NET ENERGY & ASYMMETRY
    # ============================================================
    
    # Net energy: directional bias
    # Positive = easier to move up, Negative = easier to move down
    net_energy = movement_energy_up - movement_energy_down
    
    # Energy asymmetry ratio
    energy_asymmetry = movement_energy_up / (movement_energy_down + 1e-9)
    
    # ============================================================
    # BARRIER STRENGTH
    # ============================================================
    # Average energy barrier (how hard is it to move price in general?)
    barrier_strength = (movement_energy_up + movement_energy_down) / 2.0
    
    # ============================================================
    # ACCELERATION LIKELIHOOD
    # ============================================================
    # Low energy + directional pressure = high acceleration
    # This is a normalized [0,1] metric
    
    # Directional pressure imbalance
    pressure_imbalance = abs(total_pressure_up - total_pressure_down)
    avg_pressure = (total_pressure_up + total_pressure_down) / 2.0
    
    if avg_pressure > 0:
        pressure_asymmetry = pressure_imbalance / avg_pressure
    else:
        pressure_asymmetry = 0.0
    
    # Low average elasticity = easier to accelerate
    avg_elasticity = (elasticity_up + elasticity_down) / 2.0
    elasticity_factor = 1.0 / (1.0 + avg_elasticity)
    
    # Combine: high pressure asymmetry + low elasticity = high acceleration
    acceleration_likelihood = min(1.0, pressure_asymmetry * elasticity_factor * 2.0)
    
    # Boost if in short gamma regime (destabilizing)
    if gamma_field.gamma_regime in ["short_gamma_squeeze", "low_gamma_expansion"]:
        acceleration_likelihood = min(1.0, acceleration_likelihood * 1.5)
    
    # ============================================================
    # METADATA
    # ============================================================
    metadata = {
        "total_pressure_up": float(total_pressure_up),
        "total_pressure_down": float(total_pressure_down),
        "avg_elasticity": float(avg_elasticity),
        "pressure_asymmetry": float(pressure_asymmetry),
        "elasticity_factor": float(elasticity_factor),
        "barrier_strength_normalized": float(barrier_strength / (avg_pressure + 1e-9)),
    }
    
    return MovementEnergyOutput(
        movement_energy_up=movement_energy_up,
        movement_energy_down=movement_energy_down,
        net_energy=net_energy,
        energy_asymmetry=energy_asymmetry,
        barrier_strength=barrier_strength,
        acceleration_likelihood=acceleration_likelihood,
        metadata=metadata,
    )
