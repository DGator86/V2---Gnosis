from __future__ import annotations

"""Sentiment Agent v1.0 implementation skeleton."""

from typing import Any, Dict
from uuid import uuid4

from agents.base import PrimaryAgent
from schemas.core_schemas import StandardSnapshot, Suggestion
from agents.composer.schemas import EngineDirective
from engines.sentiment.models import SentimentEnvelope


class SentimentAgentV1(PrimaryAgent):
    """Interpret sentiment features."""

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config
        self._last_sentiment_envelope: SentimentEnvelope | None = None

    def step(self, snapshot: StandardSnapshot) -> Suggestion:
        sentiment = snapshot.sentiment
        score = sentiment.get("sentiment_score", 0.0)
        confidence = sentiment.get("sentiment_confidence", 0.0)

        if score > self.config.get("bullish_threshold", 0.2):
            action = "long"
            tags = ["bullish_sentiment"]
            reasoning = "Positive sentiment"
        elif score < -self.config.get("bearish_threshold", 0.2):
            action = "short"
            tags = ["bearish_sentiment"]
            reasoning = "Negative sentiment"
        else:
            action = "flat"
            tags = ["mixed_sentiment"]
            reasoning = "Mixed sentiment"

        return Suggestion(
            id=f"sent-{uuid4()}",
            layer="primary_sentiment",
            symbol=snapshot.symbol,
            action=action,
            confidence=float(min(1.0, confidence)),
            forecast={},
            reasoning=reasoning,
            tags=tags,
        )
    
    def set_sentiment_envelope(self, envelope: SentimentEnvelope) -> None:
        """
        Cache the latest sentiment envelope for .output() method.
        
        Args:
            envelope: SentimentEnvelope from SentimentEngineV1
        """
        self._last_sentiment_envelope = envelope
    
    def output(self) -> EngineDirective:
        """
        Convert sentiment envelope to normalized EngineDirective for Composer.
        
        This is the integration point for ComposerAgent.
        
        Returns:
            EngineDirective with sentiment-specific features
        
        Raises:
            RuntimeError: If no sentiment envelope has been cached
        """
        if self._last_sentiment_envelope is None:
            raise RuntimeError(
                "SentimentAgentV1 has no sentiment envelope. Call set_sentiment_envelope() first."
            )
        
        envelope = self._last_sentiment_envelope
        
        # ============================================================
        # DIRECTION
        # ============================================================
        # Map bias to directional value in [-1, 1]
        if envelope.bias == "bullish":
            direction = envelope.strength  # Positive [0, 1]
        elif envelope.bias == "bearish":
            direction = -envelope.strength  # Negative [-1, 0]
        else:  # neutral
            direction = 0.0
        
        # ============================================================
        # STRENGTH
        # ============================================================
        strength = envelope.strength
        
        # ============================================================
        # CONFIDENCE
        # ============================================================
        confidence = envelope.confidence
        
        # ============================================================
        # REGIME
        # ============================================================
        # Prefer liquidity_regime if available, fallback to volatility_regime
        regime = (
            envelope.liquidity_regime 
            or envelope.volatility_regime 
            or envelope.flow_regime 
            or "normal"
        )
        
        # ============================================================
        # ENERGY
        # ============================================================
        # Use sentiment energy (metabolic load)
        energy = envelope.energy
        
        # ============================================================
        # VOLATILITY PROXY
        # ============================================================
        # Use energy as volatility proxy for sentiment
        # Higher sentiment energy = higher volatility
        volatility_proxy = energy * 10.0
        
        # ============================================================
        # FEATURE NAMESPACING
        # ============================================================
        # Extract driver signals and namespace them
        namespaced_features: Dict[str, float] = {}
        for driver, value in envelope.drivers.items():
            if isinstance(value, (int, float)):
                namespaced_features[f"sentiment.{driver}"] = float(value)
        
        # Add core metrics
        namespaced_features["sentiment.strength"] = strength
        namespaced_features["sentiment.energy"] = energy
        namespaced_features["sentiment.confidence"] = confidence
        
        # ============================================================
        # NOTES
        # ============================================================
        wyckoff_phase = envelope.wyckoff_phase or "unknown"
        liquidity_regime = envelope.liquidity_regime or "unknown"
        volatility_regime = envelope.volatility_regime or "unknown"
        flow_regime = envelope.flow_regime or "unknown"
        
        # Get top drivers
        top_drivers = sorted(
            envelope.drivers.items(), 
            key=lambda x: abs(float(x[1])) if isinstance(x[1], (int, float)) else 0, 
            reverse=True
        )[:3]
        top_driver_str = ", ".join([f"{k}={v:.2f}" for k, v in top_drivers if isinstance(v, (int, float))])
        
        notes = (
            f"SentimentAgentV1 | bias={envelope.bias} | "
            f"wyckoff={wyckoff_phase} | "
            f"liq_regime={liquidity_regime} | "
            f"vol_regime={volatility_regime} | "
            f"flow_regime={flow_regime} | "
            f"top_drivers=({top_driver_str})"
        )
        
        return EngineDirective(
            name="sentiment",
            direction=direction,
            strength=strength,
            confidence=confidence,
            regime=regime,
            energy=energy,
            volatility_proxy=volatility_proxy,
            features=namespaced_features,
            notes=notes,
        )
