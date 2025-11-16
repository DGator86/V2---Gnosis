# engines/sentiment_agent/agent.py

from .schemas import SentimentAgentInput, SentimentAgentOutput


class SentimentAgent:
    """
    Pure interpreter for Sentiment Engine outputs.

    Responsibilities:
    - Classify high-level sentiment direction (bullish / bearish / topping / bottoming / chop)
    - Quantify sentiment strength in [0,1]
    - Adjust confidence based on regime, divergences, and volatility behavior
    - Emit notes for Composer and human review

    No data fetching, no modeling, no trade construction.
    """

    def interpret(self, x: SentimentAgentInput) -> SentimentAgentOutput:
        notes: list[str] = []

        # ----------------------------------------------------------
        # 1) Base direction from Wyckoff phase + oscillator & breadth
        # ----------------------------------------------------------
        direction = self._infer_direction(x, notes)

        # ----------------------------------------------------------
        # 2) Strength from oscillator, breadth, flow_bias, sentiment_energy
        # ----------------------------------------------------------
        strength = self._compute_strength(x)

        # ----------------------------------------------------------
        # 3) Confidence adjustments based on regime, divergence and vol regime
        # ----------------------------------------------------------
        confidence = self._adjust_confidence(x, notes)

        # Chaotic label if confidence very low
        if confidence < 0.2:
            direction = "chaotic"

        return SentimentAgentOutput(
            direction=direction,
            strength=strength,
            confidence=confidence,
            regime=x.regime,
            notes=notes,
        )

    # ---------------------- Internals -----------------------------

    def _infer_direction(
        self,
        x: SentimentAgentInput,
        notes: list[str],
    ) -> str:
        """
        Map Wyckoff phase + oscillator + breadth into a qualitative
        sentiment direction.
        """
        osc = x.oscillator_score
        breadth = x.breadth_score
        flow = x.flow_bias

        # Start from Wyckoff macro regime
        phase = x.wyckoff_phase.upper()

        if phase in ("A", "B"):
            base_regime = "range-bound"
        elif phase == "C":
            base_regime = "accumulation bottom"
        elif phase == "D":
            base_regime = "bullish"
        elif phase == "E":
            base_regime = "distribution top"
        else:
            base_regime = "range-bound"

        direction = base_regime

        # Refine with oscillator and breadth/flow
        if osc > 0.6 and breadth > 0.3 and flow > 0.2:
            direction = "bullish"
            notes.append("strong bullish sentiment (overbought with confirmation)")
        elif osc < -0.6 and breadth < -0.3 and flow < -0.2:
            direction = "bearish"
            notes.append("strong bearish sentiment (oversold with confirmation)")
        elif osc > 0.6 and breadth < 0:
            notes.append("overbought with weak breadth (topping risk)")
            if direction == "bullish":
                direction = "distribution top"
        elif osc < -0.6 and breadth > 0:
            notes.append("oversold with resilient breadth (bottoming risk)")
            if direction != "bullish":
                direction = "accumulation bottom"

        # If volatility compression with no clear bias → range-bound sentiment
        if x.volatility_regime == "compression" and abs(osc) < 0.4 and abs(breadth) < 0.2:
            direction = "range-bound"
            notes.append("compression regime with muted oscillators (range sentiment)")

        return direction

    def _compute_strength(self, x: SentimentAgentInput) -> float:
        """
        Compute sentiment strength as a fusion of oscillator magnitude,
        breadth, flow bias, and sentiment energy.
        """
        osc_mag = abs(x.oscillator_score)
        breadth_mag = abs(x.breadth_score)
        flow_mag = abs(x.flow_bias)
        energy = max(0.0, x.sentiment_energy)

        # Weighted sum of magnitudes
        raw_strength = (
            0.35 * osc_mag
            + 0.25 * breadth_mag
            + 0.2 * flow_mag
            + 0.2 * energy
        )

        # Slight boost if volatility regime is expansion
        if x.volatility_regime == "expansion":
            raw_strength *= 1.1

        strength = max(0.0, min(raw_strength, 1.0))
        return strength

    def _adjust_confidence(
        self,
        x: SentimentAgentInput,
        notes: list[str],
    ) -> float:
        """
        Modify engine-level confidence using:
        - sentiment regime
        - realized sentiment divergence
        - volatility regime
        """
        confidence = x.confidence

        # Regime haircuts
        if x.regime == "transition":
            confidence *= 0.7
            notes.append("transition sentiment regime (noisy)")
        elif x.regime == "sideways":
            confidence *= 0.85
            notes.append("sideways regime (sentiment less directional)")

        # Divergence: sentiment was wrong vs realized price action
        if x.realized_sentiment_divergence < -0.5:
            confidence *= 0.6
            notes.append("negative realized sentiment divergence (sentiment misaligned)")

        # Volatility regime
        if x.volatility_regime == "expansion" and abs(x.oscillator_score) < 0.3:
            confidence *= 0.75
            notes.append("vol expansion without strong oscillator signal (noisy)")

        # Clamp
        confidence = max(0.0, min(confidence, 1.0))
        return confidence
