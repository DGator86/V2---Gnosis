from __future__ import annotations

from typing import Iterable, Sequence, Tuple
from datetime import timedelta

from core.schemas import LiquidityEngineSignals, LiquidityAgentPacket

from .base import (
    BaseAgent,
    LookbackLookforwardConfig,
    TimeContext,
    DEFAULT_LOOKBACK_LOOKFORWARD_CONFIG,
)


class LiquidityAgent(BaseAgent):
    """Transforms liquidity engine signals into actionable structure."""

    def __init__(self, config: LookbackLookforwardConfig | None = None) -> None:
        super().__init__(config or DEFAULT_LOOKBACK_LOOKFORWARD_CONFIG)

    def name(self) -> str:
        return "liquidity"

    def analyze(self, ctx: TimeContext) -> LiquidityAgentPacket:
        series = ctx.require_engine("liquidity")

        lookback_signals = self._collect_signals(series.iter_lookback(), self._lookback_weight)
        lookforward_signals = self._collect_signals(
            series.iter_lookforward(), self._lookforward_weight, amplification=1.25
        )

        bounds_lb: list[Tuple[Tuple[float, float], float]] = []
        for sig, weight in lookback_signals:
            bounds = self._extract_bounds(sig)
            if bounds is None:
                continue
            bounds_lb.append((bounds, weight))

        bounds_lf: list[Tuple[Tuple[float, float], float]] = []
        for sig, weight in lookforward_signals:
            bounds = self._extract_bounds(sig)
            if bounds is None:
                continue
            bounds_lf.append((bounds, weight))

        range_low = self._weighted_mean(
            [(low, weight) for (low, _), weight in bounds_lb + bounds_lf],
            default=0.0,
        )
        range_high = self._weighted_mean(
            [(high, weight) for (_, high), weight in bounds_lb + bounds_lf],
            default=0.0,
        )

        forward_low = self._weighted_mean(
            [(low, weight) for (low, _), weight in bounds_lf], default=range_low
        )
        forward_high = self._weighted_mean(
            [(high, weight) for (_, high), weight in bounds_lf], default=range_high
        )

        breakout_bias = self._resolve_breakout_bias(range_low, range_high, forward_low, forward_high)

        vacuum_candidates = self._collect_vacuum_zones(lookback_signals, lookforward_signals)

        elasticity_pairs = [
            (sig.elasticity, weight) for sig, weight in lookback_signals + lookforward_signals
        ]
        energy_to_cross_range = self._weighted_mean(elasticity_pairs, default=0.0)

        confidence = self._weighted_mean(
            [(sig.confidence, weight) for sig, weight in lookback_signals + lookforward_signals],
            default=0.0,
        )

        if lookforward_signals:
            forward_breakout_prob = self._weighted_mean(
                [(sig.breakout_probability, weight) for sig, weight in lookforward_signals],
                default=0.0,
            )
            confidence = min(1.0, confidence + 0.1 * max(0.0, forward_breakout_prob - 0.5))

        return LiquidityAgentPacket(
            symbol=self._resolve_symbol(lookback_signals, lookforward_signals),
            timestamp=ctx.as_of,
            range_low=range_low,
            range_high=range_high,
            vacuum_zones=vacuum_candidates,
            breakout_bias=breakout_bias,
            energy_to_cross_range=max(0.0, energy_to_cross_range),
            confidence=max(0.0, min(1.0, confidence)),
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _collect_signals(
        self,
        series: Iterable[Tuple[timedelta, Sequence[LiquidityEngineSignals] | LiquidityEngineSignals]],
        weight_fn,
        amplification: float = 1.0,
    ) -> list[Tuple[LiquidityEngineSignals, float]]:
        collected: list[Tuple[LiquidityEngineSignals, float]] = []
        for span, payloads in series:
            signal = self._select_latest(payloads)
            if signal is None:
                continue
            collected.append((signal, weight_fn(span) * amplification))
        return collected

    @staticmethod
    def _select_latest(
        payloads: Sequence[LiquidityEngineSignals] | LiquidityEngineSignals | None,
    ) -> LiquidityEngineSignals | None:
        if payloads is None:
            return None
        if isinstance(payloads, Sequence) and not isinstance(payloads, (str, bytes)):
            return payloads[-1] if payloads else None
        if isinstance(payloads, LiquidityEngineSignals):
            return payloads
        return None

    @staticmethod
    def _extract_bounds(signal: LiquidityEngineSignals) -> Tuple[float, float] | None:
        if not signal.liquidity_zones:
            return None
        zones = list(signal.liquidity_zones.values())
        return (min(zones), max(zones))

    @staticmethod
    def _weighted_mean(values: Sequence[Tuple[float, float]], default: float = 0.0) -> float:
        total_weight = sum(weight for _, weight in values)
        if total_weight == 0:
            return default
        return sum(value * weight for value, weight in values) / total_weight

    @staticmethod
    def _resolve_symbol(
        lookback: Sequence[Tuple[LiquidityEngineSignals, float]],
        lookforward: Sequence[Tuple[LiquidityEngineSignals, float]],
    ) -> str:
        for seq in (lookback, lookforward):
            if seq:
                return seq[0][0].symbol
        return ""

    @staticmethod
    def _collect_vacuum_zones(
        lookback: Sequence[Tuple[LiquidityEngineSignals, float]],
        lookforward: Sequence[Tuple[LiquidityEngineSignals, float]],
    ) -> list[float]:
        zones: set[float] = set()
        for seq in (lookback, lookforward):
            for signal, _ in seq:
                if signal.vacuum_score < 0.4:
                    continue
                zones.update(signal.liquidity_zones.values())
        return sorted(zones)

    @staticmethod
    def _resolve_breakout_bias(
        range_low: float,
        range_high: float,
        forward_low: float,
        forward_high: float,
    ) -> str:
        if forward_high > range_high * 1.01:
            return "up"
        if forward_low < range_low * 0.99:
            return "down"
        return "none"

    @staticmethod
    def _lookback_weight(window: timedelta) -> float:
        minutes = max(window.total_seconds() / 60.0, 1.0)
        return 1.0 / minutes

    @staticmethod
    def _lookforward_weight(horizon: timedelta) -> float:
        minutes = max(horizon.total_seconds() / 60.0, 1.0)
        return 1.0 / minutes
