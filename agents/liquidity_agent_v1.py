from __future__ import annotations

"""Liquidity Agent v1.0 implementation skeleton."""

from typing import Any, Dict
from uuid import uuid4

from agents.base import PrimaryAgent
from schemas.core_schemas import StandardSnapshot, Suggestion, EngineOutput
from agents.composer.schemas import EngineDirective


class LiquidityAgentV1(PrimaryAgent):
    """Interpret liquidity features to determine market stance."""

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config
        self._last_engine_output: EngineOutput | None = None

    def step(self, snapshot: StandardSnapshot) -> Suggestion:
        liquidity = snapshot.liquidity
        action = "flat"
        confidence = 0.4
        reasoning = "Normal liquidity"
        tags = []

        amihud = liquidity.get("amihud_illiquidity", 0.0)
        ofi = liquidity.get("ofi", 0.0)

        if amihud > self.config.get("thin_threshold", 0.001):
            action = "spread"
            confidence = 0.6
            tags.append("thin_liquidity")
            reasoning = "Thin liquidity suggests spreads"
        if ofi > self.config.get("one_sided_threshold", 0.6):
            action = "long"
            confidence = 0.7
            tags.append("one_sided_flow")
            reasoning = "Strong buy-side flow"
        elif ofi < -self.config.get("one_sided_threshold", 0.6):
            action = "short"
            confidence = 0.7
            tags.append("one_sided_flow")
            reasoning = "Strong sell-side flow"

        return Suggestion(
            id=f"liq-{uuid4()}",
            layer="primary_liquidity",
            symbol=snapshot.symbol,
            action=action,
            confidence=confidence,
            forecast={},
            reasoning=reasoning,
            tags=tags,
        )
    
    def set_engine_output(self, engine_output: EngineOutput) -> None:
        """
        Cache the latest engine output for .output() method.
        
        Args:
            engine_output: Raw EngineOutput from LiquidityEngineV1
        """
        self._last_engine_output = engine_output
    
    def output(self) -> EngineDirective:
        """
        Convert liquidity engine output to normalized EngineDirective for Composer.
        
        This is the integration point for ComposerAgent.
        
        Returns:
            EngineDirective with liquidity-specific features
        
        Raises:
            RuntimeError: If no engine output has been cached
        """
        if self._last_engine_output is None:
            raise RuntimeError(
                "LiquidityAgentV1 has no engine output. Call set_engine_output() first."
            )
        
        features = self._last_engine_output.features
        metadata = self._last_engine_output.metadata
        
        # ============================================================
        # DIRECTION
        # ============================================================
        # Use POLR (Path of Least Resistance) direction as primary bias
        polr_direction = features.get("polr_direction", 0.0)
        
        # Fallback to orderbook imbalance if POLR not available
        if abs(polr_direction) < 0.1:
            ofi = features.get("orderbook_imbalance", 0.0)
            direction = max(-1.0, min(1.0, ofi))
        else:
            direction = max(-1.0, min(1.0, polr_direction))
        
        # ============================================================
        # STRENGTH
        # ============================================================
        # Combine POLR strength with liquidity score
        polr_strength = features.get("polr_strength", 0.5)
        liquidity_score = features.get("liquidity_score", 0.5)
        
        strength = polr_strength * liquidity_score
        
        # ============================================================
        # CONFIDENCE
        # ============================================================
        confidence = self._last_engine_output.confidence
        
        # ============================================================
        # REGIME
        # ============================================================
        regime = metadata.get("liquidity_regime", self._last_engine_output.regime or "Normal")
        
        # ============================================================
        # ENERGY
        # ============================================================
        # Use friction cost as primary energy metric
        friction_cost = features.get("friction_cost", 0.0)
        
        # Add compression/expansion energy components
        compression_energy = features.get("compression_energy", 0.0)
        expansion_energy = features.get("expansion_energy", 0.0)
        
        # Total energy = friction + volatility-liquidity interaction
        energy = friction_cost + (compression_energy + expansion_energy) * 0.5
        
        # ============================================================
        # VOLATILITY PROXY
        # ============================================================
        # Use Amihud illiquidity as volatility proxy (higher illiquidity = higher vol)
        amihud = features.get("amihud_illiquidity", 0.0)
        volatility_proxy = amihud * 1e6  # Scale to interpretable range
        
        # ============================================================
        # FEATURE NAMESPACING
        # ============================================================
        # Prefix all liquidity features with 'liquidity.'
        namespaced_features: Dict[str, float] = {}
        for key, value in features.items():
            if isinstance(value, (int, float)):
                namespaced_features[f"liquidity.{key}"] = float(value)
        
        # ============================================================
        # NOTES
        # ============================================================
        wyckoff_phase = metadata.get("wyckoff_phase", "unknown")
        sweep_detected = bool(features.get("sweep_detected", 0.0))
        iceberg_detected = bool(features.get("iceberg_detected", 0.0))
        
        notes_parts = [
            f"LiquidityAgentV1 | regime={regime}",
            f"wyckoff_phase={wyckoff_phase}",
            f"polr_dir={polr_direction:.2f}",
            f"friction_cost={friction_cost:.4f}",
        ]
        
        if sweep_detected:
            notes_parts.append("sweep_alert")
        if iceberg_detected:
            notes_parts.append("iceberg_alert")
        
        notes = " | ".join(notes_parts)
        
        return EngineDirective(
            name="liquidity",
            direction=direction,
            strength=strength,
            confidence=confidence,
            regime=regime,
            energy=energy,
            volatility_proxy=volatility_proxy,
            features=namespaced_features,
            notes=notes,
        )
