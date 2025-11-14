from __future__ import annotations

from core.schemas import (
    HedgeEngineSignals,
    LiquidityEngineSignals,
    SentimentEngineSignals,
    StandardizedSignals,
)


class StandardizerEngine:
    """Scales and fuses raw engine outputs into a unified signal packet."""

    def run(
        self,
        hedge: HedgeEngineSignals,
        liquidity: LiquidityEngineSignals,
        sentiment: SentimentEngineSignals,
    ) -> StandardizedSignals:
        """
        Convert heterogeneous scales → consistent 0..1 or -1..1 fields,
        and determine a coarse regime label.
        """
        # TODO: real scaling/calibration
        return StandardizedSignals(
            symbol=hedge.symbol,
            timestamp=hedge.timestamp,
            directional_score=0.0,
            volatility_score=0.5,
            liquidity_score=liquidity.confidence,
            sentiment_score=sentiment.confidence,
            energy_score=0.5,
            jump_risk_score=hedge.jump_risk_score,
            regime_label="uncertain",
        )
