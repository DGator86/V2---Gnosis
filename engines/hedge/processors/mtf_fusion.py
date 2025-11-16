from __future__ import annotations

"""
Multi-timeframe fusion with adaptive weighting.

Superior to fixed "50/30/20" ratios because it adapts based on:
- Realized directional consistency
- Volatility regime
- Jump risk
- Liquidity shocks
- Energy-aware confidence weighting
"""

from typing import Dict, List

from engines.hedge.models import (
    ElasticityOutput,
    HedgeEngineOutput,
    MTFFusionOutput,
    MovementEnergyOutput,
    RegimeOutput,
)


def fuse_multi_timeframe(
    outputs: List[HedgeEngineOutput],
    timeframes: List[str],
    regime: RegimeOutput,
    config: dict,
) -> MTFFusionOutput:
    """
    Fuse multiple timeframe outputs with adaptive weighting.
    
    ADAPTIVE WEIGHTING FACTORS:
    ---------------------------
    1. Realized move consistency: Higher weight to timeframes showing
       directional agreement with recent realized moves
    
    2. Energy-aware confidence: Weight by movement_energy reliability
       (low energy = easier to predict, higher weight)
    
    3. Volatility regime penalty: Reduce longer timeframe weights
       during high vol-of-vol (less predictable)
    
    4. Jump risk adjustment: Emphasize shorter timeframes during
       jump risk regimes
    
    5. Regime stability: Higher weight when regime is stable
    
    Args:
        outputs: List of HedgeEngineOutput from different timeframes
        timeframes: List of timeframe labels (e.g., ["1m", "5m", "15m"])
        regime: Current regime classification
        config: Configuration parameters
        
    Returns:
        MTFFusionOutput with adaptively weighted fusion
    """
    if not outputs:
        return MTFFusionOutput(
            fused_pressure_up=0.0,
            fused_pressure_down=0.0,
            fused_net_pressure=0.0,
            fused_elasticity=1.0,
            fused_energy=0.0,
            timeframe_weights={},
            realized_move_score=0.0,
            adaptive_confidence=0.0,
            volatility_penalty=1.0,
        )
    
    # ============================================================
    # CALCULATE BASE WEIGHTS
    # ============================================================
    # Start with equal weighting
    num_timeframes = len(outputs)
    base_weights = [1.0 / num_timeframes] * num_timeframes
    
    # ============================================================
    # ENERGY-AWARE CONFIDENCE ADJUSTMENT
    # ============================================================
    # Lower energy = more predictable = higher weight
    energy_factors = []
    for output in outputs:
        # Inverse energy weighting
        avg_energy = (output.movement_energy_up + output.movement_energy_down) / 2.0
        energy_factor = 1.0 / (1.0 + avg_energy * config.get("energy_weight_scale", 0.1))
        energy_factors.append(energy_factor)
    
    # Normalize energy factors
    total_energy = sum(energy_factors)
    if total_energy > 0:
        energy_weights = [ef / total_energy for ef in energy_factors]
    else:
        energy_weights = base_weights
    
    # ============================================================
    # REGIME STABILITY ADJUSTMENT
    # ============================================================
    # Higher regime stability = trust all timeframes more equally
    # Lower regime stability = trust shorter timeframes more
    stability = regime.regime_stability
    
    if stability < 0.5:
        # Low stability: exponentially decay longer timeframes
        stability_weights = []
        for i in range(num_timeframes):
            # Earlier timeframes (shorter) get higher weight
            decay_factor = config.get("instability_decay_rate", 0.3)
            weight = 1.0 * ((1.0 - decay_factor) ** i)
            stability_weights.append(weight)
        
        # Normalize
        total_stability = sum(stability_weights)
        stability_weights = [sw / total_stability for sw in stability_weights]
    else:
        stability_weights = base_weights
    
    # ============================================================
    # JUMP RISK ADJUSTMENT
    # ============================================================
    # High jump risk: emphasize shorter timeframes
    if regime.jump_risk_regime == "high_jump_risk":
        jump_weights = []
        for i in range(num_timeframes):
            # Exponential decay for longer timeframes
            weight = 1.0 * (0.5 ** i)
            jump_weights.append(weight)
        
        total_jump = sum(jump_weights)
        jump_weights = [jw / total_jump for jw in jump_weights]
    else:
        jump_weights = base_weights
    
    # ============================================================
    # VOLATILITY PENALTY
    # ============================================================
    # High vol-of-vol: reduce ALL longer timeframe weights
    vol_of_vol_threshold = config.get("vol_of_vol_fusion_threshold", 0.3)
    vol_of_vol = regime.metadata.get("vol_of_vol", 0.0)
    
    if vol_of_vol > vol_of_vol_threshold:
        volatility_penalty = 1.0 - (vol_of_vol - vol_of_vol_threshold) * 1.5
        volatility_penalty = max(0.3, min(1.0, volatility_penalty))
    else:
        volatility_penalty = 1.0
    
    # Apply penalty to longer timeframes only
    vol_weights = []
    for i in range(num_timeframes):
        if i > 0:  # Not the shortest timeframe
            vol_weights.append(base_weights[i] * volatility_penalty)
        else:
            vol_weights.append(base_weights[i])
    
    # Normalize
    total_vol = sum(vol_weights)
    vol_weights = [vw / total_vol for vw in vol_weights]
    
    # ============================================================
    # COMBINE ALL WEIGHT ADJUSTMENTS
    # ============================================================
    # Weighted average of all adjustment methods
    weight_blend_config = config.get("weight_blend", {
        "energy": 0.4,
        "stability": 0.3,
        "jump": 0.2,
        "volatility": 0.1,
    })
    
    final_weights = []
    for i in range(num_timeframes):
        combined = (
            energy_weights[i] * weight_blend_config.get("energy", 0.4)
            + stability_weights[i] * weight_blend_config.get("stability", 0.3)
            + jump_weights[i] * weight_blend_config.get("jump", 0.2)
            + vol_weights[i] * weight_blend_config.get("volatility", 0.1)
        )
        final_weights.append(combined)
    
    # Normalize final weights
    total_weight = sum(final_weights)
    if total_weight > 0:
        final_weights = [fw / total_weight for fw in final_weights]
    else:
        final_weights = base_weights
    
    # ============================================================
    # FUSE OUTPUTS
    # ============================================================
    fused_pressure_up = sum(o.pressure_up * w for o, w in zip(outputs, final_weights))
    fused_pressure_down = sum(o.pressure_down * w for o, w in zip(outputs, final_weights))
    fused_net_pressure = fused_pressure_up - fused_pressure_down
    
    fused_elasticity = sum(o.elasticity * w for o, w in zip(outputs, final_weights))
    fused_energy = sum(o.movement_energy * w for o, w in zip(outputs, final_weights))
    
    # ============================================================
    # REALIZED MOVE SCORE
    # ============================================================
    # Measure of directional consistency across timeframes
    # High score = all timeframes agree on direction
    
    net_pressures = [o.net_pressure for o in outputs]
    
    if net_pressures:
        # Check if all same sign
        all_positive = all(p > 0 for p in net_pressures)
        all_negative = all(p < 0 for p in net_pressures)
        
        if all_positive or all_negative:
            # Perfect agreement
            realized_move_score = 1.0
        else:
            # Partial agreement: measure variance
            avg_pressure = sum(net_pressures) / len(net_pressures)
            variance = sum((p - avg_pressure) ** 2 for p in net_pressures) / len(net_pressures)
            std_dev = variance ** 0.5
            
            # Normalize to [0, 1]
            if abs(avg_pressure) > 0:
                consistency = 1.0 - (std_dev / abs(avg_pressure))
                realized_move_score = max(0.0, min(1.0, consistency))
            else:
                realized_move_score = 0.0
    else:
        realized_move_score = 0.0
    
    # ============================================================
    # ADAPTIVE CONFIDENCE
    # ============================================================
    # Combine:
    # - Regime confidence
    # - Realized move consistency
    # - Weight distribution (more even = more confident)
    
    regime_conf = regime.regime_confidence
    
    # Weight distribution entropy (more even = higher confidence)
    if final_weights:
        entropy = -sum(w * (w + 1e-9).log() if w > 0 else 0 for w in final_weights)
        max_entropy = -(1.0 / num_timeframes) * num_timeframes * (1.0 / num_timeframes).log()
        if max_entropy > 0:
            weight_confidence = entropy / max_entropy
        else:
            weight_confidence = 0.5
    else:
        weight_confidence = 0.5
    
    adaptive_confidence = (
        regime_conf * 0.4
        + realized_move_score * 0.4
        + weight_confidence * 0.2
    )
    
    # ============================================================
    # BUILD WEIGHT DICT
    # ============================================================
    timeframe_weights = {tf: float(w) for tf, w in zip(timeframes, final_weights)}
    
    # ============================================================
    # METADATA
    # ============================================================
    metadata = {
        "num_timeframes": float(num_timeframes),
        "weight_entropy": float(entropy) if final_weights else 0.0,
        "regime_stability": float(stability),
        "avg_energy": float(fused_energy),
    }
    
    return MTFFusionOutput(
        fused_pressure_up=fused_pressure_up,
        fused_pressure_down=fused_pressure_down,
        fused_net_pressure=fused_net_pressure,
        fused_elasticity=fused_elasticity,
        fused_energy=fused_energy,
        timeframe_weights=timeframe_weights,
        realized_move_score=realized_move_score,
        adaptive_confidence=adaptive_confidence,
        volatility_penalty=volatility_penalty,
        metadata=metadata,
    )
