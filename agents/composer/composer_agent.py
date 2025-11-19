# agents/composer/composer_agent.py

from typing import Any, Dict

from .schemas import (
    EngineDirective,
    CompositeMarketDirective,
    Direction,
)
from .resolution.regime_weights import compute_regime_weights
from .fusion.confidence_fusion import fuse_confidence
from .fusion.direction_fusion import fuse_direction
from .energy.energy_calculator import compute_total_energy
from .scenarios.cone_builder import build_expected_move_cone
from .classification.trade_style import classify_trade_style
from .resolution.conflict_resolver import summarize_conflicts


class ComposerAgent:
    """
    Composer Agent v1.0

    Consumes:
        - HedgeAgent (with .output())
        - LiquidityAgent (with .output())
        - SentimentAgent (with .output())

    Produces:
        - CompositeMarketDirective for the Trade Agent
    """

    def __init__(
        self,
        hedge_agent: Any,
        liquidity_agent: Any,
        sentiment_agent: Any,
        reference_price_getter,
        learning_orchestrator: Any = None,
    ) -> None:
        """
        Parameters
        ----------
        hedge_agent : Any
            Object exposing .output() -> EngineDirective or dict.
        liquidity_agent : Any
            Object exposing .output() -> EngineDirective or dict.
        sentiment_agent : Any
            Object exposing .output() -> EngineDirective or dict.
        reference_price_getter : Callable[[], float]
            Function returning the current reference price for expected move cones.
        learning_orchestrator : Any, optional
            LearningOrchestrator instance for adaptive learning (Transformer lookahead).
        """
        self._hedge_agent = hedge_agent
        self._liquidity_agent = liquidity_agent
        self._sentiment_agent = sentiment_agent
        self._reference_price_getter = reference_price_getter
        self._learning_orchestrator = learning_orchestrator

    @staticmethod
    def _normalize_output(raw: Any, name: str) -> EngineDirective:
        """
        Normalize arbitrary agent output into EngineDirective.

        v1.0 expects either:
        - EngineDirective instance, or
        - dict with matching fields.
        """
        if isinstance(raw, EngineDirective):
            return raw

        if isinstance(raw, dict):
            return EngineDirective(name=name, **raw)

        raise TypeError(f"Unsupported output type for {name}: {type(raw)}")

    def compose(self) -> CompositeMarketDirective:
        """
        Run all three agents, fuse their directives, and produce a composite directive.
        """
        raw_hedge = self._hedge_agent.output()
        raw_liq = self._liquidity_agent.output()
        raw_sent = self._sentiment_agent.output()

        hedge = self._normalize_output(raw_hedge, "hedge")
        liquidity = self._normalize_output(raw_liq, "liquidity")
        sentiment = self._normalize_output(raw_sent, "sentiment")

        # 🧠 ADAPTIVE LEARNING: Get Transformer lookahead prediction
        lookahead_directive = None
        if self._learning_orchestrator and self._learning_orchestrator.enabled:
            lookahead_prediction = self._learning_orchestrator.get_lookahead_prediction()
            if lookahead_prediction is not None:
                # Convert prediction to EngineDirective format
                # Prediction is % price change, convert to direction/confidence
                pred_direction = 1.0 if lookahead_prediction > 0 else -1.0 if lookahead_prediction < 0 else 0.0
                pred_confidence = min(1.0, abs(lookahead_prediction) / 2.0)  # Scale: 2% = 100% confidence
                
                lookahead_directive = EngineDirective(
                    name="lookahead",
                    direction=pred_direction,
                    confidence=pred_confidence,
                    energy=0.1  # Low energy since it's a prediction
                )
                print(f"🧠 Transformer Lookahead: direction={pred_direction:.2f}, confidence={pred_confidence:.2f} (raw prediction={lookahead_prediction:.4f}%)")

        weights = compute_regime_weights(hedge, liquidity, sentiment)
        confidence = fuse_confidence(hedge, liquidity, sentiment, weights, lookahead_directive)
        direction: Direction = fuse_direction(hedge, liquidity, sentiment, weights, lookahead_directive)
        energy = compute_total_energy(hedge, liquidity, sentiment)

        # Simple volatility metric for now: use volatility proxy fusion in cone_builder
        reference_price = self._reference_price_getter()
        cone = build_expected_move_cone(
            reference_price=reference_price,
            direction_sign=direction,
            hedge=hedge,
            liquidity=liquidity,
            sentiment=sentiment,
        )

        trade_style = classify_trade_style(
            direction=direction,
            confidence=confidence,
            energy=energy,
            hedge=hedge,
            liquidity=liquidity,
            sentiment=sentiment,
        )

        # Strength: scale confidence to 0–100, discounted by energy
        strength = max(0.0, min(100.0, 100.0 * confidence / (1.0 + energy)))

        # Volatility: for now use 0–100 proxy as average band % of 1d horizon
        one_day_band = cone.bands["1d"]
        volatility = abs(one_day_band.upper - one_day_band.lower) / reference_price * 100.0

        rationale = self._build_rationale(
            direction=direction,
            confidence=confidence,
            energy=energy,
            hedge=hedge,
            liquidity=liquidity,
            sentiment=sentiment,
        )

        raw_engines: Dict[str, Dict[str, Any]] = {
            "hedge": hedge.model_dump(),
            "liquidity": liquidity.model_dump(),
            "sentiment": sentiment.model_dump(),
        }

        return CompositeMarketDirective(
            direction=direction,
            strength=strength,
            confidence=confidence,
            volatility=volatility,
            energy_cost=energy,
            trade_style=trade_style,
            expected_move_cone=cone,
            rationale=rationale,
            raw_engines=raw_engines,
        )

    @staticmethod
    def _build_rationale(
        direction: Direction,
        confidence: float,
        energy: float,
        hedge: EngineDirective,
        liquidity: EngineDirective,
        sentiment: EngineDirective,
    ) -> str:
        """
        Construct a succinct explanation of the composite signal.

        This is what the Trade Agent (and you) will read.
        """
        dir_text = {
            -1: "short bias",
             0: "neutral / no strong bias",
             1: "long bias",
        }[direction]

        conflicts = summarize_conflicts(hedge, liquidity, sentiment)

        return (
            f"Composer v1.0: {dir_text} with confidence={confidence:.2f}, "
            f"energy_cost={energy:.2f}. "
            f"Hedge: dir={hedge.direction:.2f}, conf={hedge.confidence:.2f}, "
            f"energy={hedge.energy:.2f}. "
            f"Liquidity: dir={liquidity.direction:.2f}, conf={liquidity.confidence:.2f}, "
            f"energy={liquidity.energy:.2f}. "
            f"Sentiment: dir={sentiment.direction:.2f}, conf={sentiment.confidence:.2f}, "
            f"energy={sentiment.energy:.2f}. "
            f"Conflicts: {conflicts}"
        )
