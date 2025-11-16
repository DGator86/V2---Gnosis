from __future__ import annotations

"""
Hedge Agent v3.0 - Energy-Aware Interpretation.

The hedge agent interprets hedge engine output (pressure fields, elasticity,
movement energy) into actionable policy suggestions.

It does NOT predict direction.
It INTERPRETS dealer positioning and energy barriers.

Key Interpretation Logic:
- Low elasticity + directional pressure = easier to move (higher confidence)
- High elasticity + low energy = barriers strong (lower confidence for moves)
- Asymmetric energy = directional bias
- Regime modifiers adjust interpretation
"""

from typing import Any, Dict
from uuid import uuid4

from agents.base import PrimaryAgent
from schemas.core_schemas import StandardSnapshot, Suggestion, EngineOutput
from agents.composer.schemas import EngineDirective


class HedgeAgentV3(PrimaryAgent):
    """
    Interpret hedge features into high-level suggestions.
    
    Uses elasticity and movement energy to assess:
    - How easy/hard it is to move price
    - Which direction has lower barriers
    - What regime dynamics suggest
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config
        self._last_engine_output: EngineOutput | None = None

    def step(self, snapshot: StandardSnapshot) -> Suggestion:
        """
        Interpret hedge snapshot into a policy suggestion.
        
        Args:
            snapshot: StandardSnapshot with hedge features
            
        Returns:
            Suggestion with action, confidence, reasoning
        """
        hedge = snapshot.hedge
        
        # Extract key features
        net_pressure = hedge.get("net_pressure", 0.0)
        elasticity = hedge.get("elasticity", 1.0)
        movement_energy = hedge.get("movement_energy", 0.0)
        movement_energy_up = hedge.get("movement_energy_up", 0.0)
        movement_energy_down = hedge.get("movement_energy_down", 0.0)
        energy_asymmetry = hedge.get("energy_asymmetry", 1.0)
        
        gamma_pressure = hedge.get("gamma_pressure", 0.0)
        dealer_gamma_sign = hedge.get("dealer_gamma_sign", 0.0)
        
        # Extract regime from metadata
        regime = snapshot.regime or "neutral"
        
        # ============================================================
        # ENERGY-BASED INTERPRETATION
        # ============================================================
        # Core theory: Energy = cost to move price
        # Low energy = easy to move (low barriers)
        # High energy = hard to move (strong barriers)
        
        # Normalize energy to interpretable scale
        energy_threshold_low = self.config.get("energy_threshold_low", 100.0)
        energy_threshold_high = self.config.get("energy_threshold_high", 1000.0)
        
        if movement_energy < energy_threshold_low:
            energy_regime = "low_barriers"
        elif movement_energy > energy_threshold_high:
            energy_regime = "high_barriers"
        else:
            energy_regime = "moderate_barriers"
        
        # ============================================================
        # DIRECTIONAL BIAS FROM ENERGY ASYMMETRY
        # ============================================================
        # energy_asymmetry = movement_energy_up / movement_energy_down
        # > 1.0 = easier to move down (lower energy down)
        # < 1.0 = easier to move up (lower energy up)
        
        asymmetry_threshold = self.config.get("asymmetry_threshold", 1.2)
        
        if energy_asymmetry > asymmetry_threshold:
            # Easier to move down
            directional_bias = "short"
            bias_strength = min((energy_asymmetry - 1.0) * 2.0, 1.0)
        elif energy_asymmetry < (1.0 / asymmetry_threshold):
            # Easier to move up
            directional_bias = "long"
            bias_strength = min((1.0 - energy_asymmetry) * 2.0, 1.0)
        else:
            directional_bias = "flat"
            bias_strength = 0.0
        
        # ============================================================
        # GAMMA REGIME INTERPRETATION
        # ============================================================
        # Short gamma (dealer_gamma_sign < 0) = destabilizing
        # Long gamma (dealer_gamma_sign > 0) = stabilizing
        
        gamma_threshold = self.config.get("gamma_sign_threshold", 0.5)
        
        if dealer_gamma_sign < -gamma_threshold:
            gamma_interpretation = "short_gamma_acceleration"
            gamma_multiplier = 1.5  # Amplify signals in short gamma
        elif dealer_gamma_sign > gamma_threshold:
            gamma_interpretation = "long_gamma_dampening"
            gamma_multiplier = 0.7  # Dampen signals in long gamma (mean reversion)
        else:
            gamma_interpretation = "neutral_gamma"
            gamma_multiplier = 1.0
        
        # ============================================================
        # REGIME-ADJUSTED INTERPRETATION
        # ============================================================
        # Certain regimes modify confidence and action
        
        regime_modifiers = {
            "short_gamma_squeeze": {"confidence_mult": 1.3, "favor": "long"},
            "long_gamma_compression": {"confidence_mult": 0.7, "favor": "flat"},
            "high_vanna_high_vol": {"confidence_mult": 0.8, "favor": None},
            "high_charm_decay_acceleration": {"confidence_mult": 0.9, "favor": None},
            "jump_risk_dominant": {"confidence_mult": 0.6, "favor": "flat"},
        }
        
        modifier = regime_modifiers.get(regime, {"confidence_mult": 1.0, "favor": None})
        confidence_mult = modifier["confidence_mult"]
        regime_favor = modifier["favor"]
        
        # ============================================================
        # SYNTHESIZE ACTION & CONFIDENCE
        # ============================================================
        
        # Start with directional bias from energy asymmetry
        if regime_favor:
            action = regime_favor
        else:
            action = directional_bias
        
        # Base confidence from bias strength
        confidence = bias_strength * 0.5 + 0.3  # [0.3, 0.8] range
        
        # Adjust by energy regime
        if energy_regime == "low_barriers":
            # Low barriers = higher confidence in moves
            confidence *= 1.2
        elif energy_regime == "high_barriers":
            # High barriers = lower confidence in moves
            confidence *= 0.7
        
        # Apply gamma multiplier
        confidence *= gamma_multiplier
        
        # Apply regime modifier
        confidence *= confidence_mult
        
        # Clamp confidence
        confidence = max(0.1, min(0.95, confidence))
        
        # ============================================================
        # SPECIAL CASES
        # ============================================================
        
        # Override: if net pressure is strong but elasticity is very high
        # → Barriers are strong, prefer flat
        if elasticity > self.config.get("high_elasticity_threshold", 5.0):
            if abs(net_pressure) < self.config.get("pressure_threshold", 1e6):
                action = "flat"
                confidence *= 0.6
        
        # Override: jump risk regime → reduce conviction
        if "jump" in regime.lower():
            confidence *= 0.7
        
        # ============================================================
        # BUILD REASONING
        # ============================================================
        reasoning_parts = [
            f"Energy regime: {energy_regime} (energy={movement_energy:.1f})",
            f"Directional bias: {directional_bias} (asymmetry={energy_asymmetry:.2f})",
            f"Gamma: {gamma_interpretation} (sign={dealer_gamma_sign:.2f})",
            f"Regime: {regime}",
        ]
        
        if elasticity > 3.0:
            reasoning_parts.append(f"High elasticity ({elasticity:.2f}) indicates strong barriers")
        
        if movement_energy < energy_threshold_low:
            reasoning_parts.append("Low movement energy suggests easy price movement")
        
        reasoning = " | ".join(reasoning_parts)
        
        # ============================================================
        # BUILD TAGS
        # ============================================================
        tags = [energy_regime, gamma_interpretation]
        
        if abs(energy_asymmetry - 1.0) > 0.2:
            tags.append("asymmetric_energy")
        
        if "jump" in regime.lower():
            tags.append("jump_risk")
        
        # ============================================================
        # FORECAST (OPTIONAL)
        # ============================================================
        # Provide expected energy/elasticity for downstream agents
        forecast = {
            "elasticity": elasticity,
            "movement_energy": movement_energy,
            "energy_asymmetry": energy_asymmetry,
            "dealer_gamma_sign": dealer_gamma_sign,
        }
        
        return Suggestion(
            id=f"hedge-{uuid4()}",
            layer="primary_hedge",
            symbol=snapshot.symbol,
            action=action,
            confidence=confidence,
            forecast=forecast,
            reasoning=reasoning,
            tags=tags,
        )
    
    def set_engine_output(self, engine_output: EngineOutput) -> None:
        """
        Cache the latest engine output for .output() method.
        
        Args:
            engine_output: Raw EngineOutput from HedgeEngineV3
        """
        self._last_engine_output = engine_output
    
    def output(self) -> EngineDirective:
        """
        Convert hedge engine output to normalized EngineDirective for Composer.
        
        This is the integration point for ComposerAgent.
        
        Returns:
            EngineDirective with hedge-specific features
        
        Raises:
            RuntimeError: If no engine output has been cached
        """
        if self._last_engine_output is None:
            raise RuntimeError(
                "HedgeAgentV3 has no engine output. Call set_engine_output() first."
            )
        
        features = self._last_engine_output.features
        metadata = self._last_engine_output.metadata
        
        # ============================================================
        # DIRECTION
        # ============================================================
        # Map net_pressure to directional bias in [-1, 1]
        net_pressure = features.get("net_pressure", 0.0)
        
        # Normalize pressure to [-1, 1] range (assuming pressure can range ±1e6)
        pressure_scale = self.config.get("pressure_normalization_scale", 1e6)
        direction = max(-1.0, min(1.0, net_pressure / pressure_scale))
        
        # ============================================================
        # STRENGTH
        # ============================================================
        # Use absolute pressure as strength indicator
        # Also factor in energy asymmetry
        energy_asymmetry = features.get("energy_asymmetry", 1.0)
        raw_strength = abs(direction) * abs(1.0 - energy_asymmetry)
        strength = max(0.0, min(1.0, raw_strength * 10.0))  # Scale to [0, 1]
        
        # ============================================================
        # CONFIDENCE
        # ============================================================
        confidence = self._last_engine_output.confidence
        
        # ============================================================
        # REGIME
        # ============================================================
        regime = self._last_engine_output.regime or "normal"
        
        # ============================================================
        # ENERGY
        # ============================================================
        movement_energy = features.get("movement_energy", 0.0)
        
        # Normalize to more interpretable scale
        energy_scale = self.config.get("energy_normalization_scale", 1000.0)
        energy = movement_energy / energy_scale
        
        # ============================================================
        # VOLATILITY PROXY
        # ============================================================
        # Use implied volatility or elasticity as proxy
        elasticity = features.get("elasticity", 1.0)
        volatility_proxy = elasticity * 10.0  # Rough proxy
        
        # ============================================================
        # FEATURE NAMESPACING
        # ============================================================
        # Prefix all hedge features with 'hedge.'
        namespaced_features: Dict[str, float] = {}
        for key, value in features.items():
            if isinstance(value, (int, float)):
                namespaced_features[f"hedge.{key}"] = float(value)
        
        # ============================================================
        # NOTES
        # ============================================================
        dealer_sign = features.get("dealer_gamma_sign", 0.0)
        gamma_regime = metadata.get("gamma_regime", "unknown")
        potential_shape = metadata.get("potential_shape", "unknown")
        
        notes = (
            f"HedgeAgentV3 | regime={regime} | "
            f"gamma_regime={gamma_regime} | "
            f"potential_shape={potential_shape} | "
            f"dealer_sign={dealer_sign:.2f} | "
            f"elasticity={elasticity:.2f}"
        )
        
        return EngineDirective(
            name="hedge",
            direction=direction,
            strength=strength,
            confidence=confidence,
            regime=regime,
            energy=energy,
            volatility_proxy=volatility_proxy,
            features=namespaced_features,
            notes=notes,
        )
