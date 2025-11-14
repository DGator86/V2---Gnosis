from __future__ import annotations

from typing import Iterable, Sequence, Tuple
from datetime import timedelta

from core.schemas import HedgeEngineSignals, HedgeAgentPacket

from .base import (
    BaseAgent,
    LookbackLookforwardConfig,
    TimeContext,
    DEFAULT_LOOKBACK_LOOKFORWARD_CONFIG,
)


class HedgeAgent(BaseAgent):
    """Reduces hedge engine signals into a decision-ready summary."""

    def __init__(self, config: LookbackLookforwardConfig | None = None) -> None:
        super().__init__(config or DEFAULT_LOOKBACK_LOOKFORWARD_CONFIG)

    def name(self) -> str:
        return "hedge"

    def analyze(self, ctx: TimeContext) -> HedgeAgentPacket:
        series = ctx.require_engine("hedge")

        lookback_signals = self._collect_signals(series.iter_lookback(), self._lookback_weight)
        lookforward_signals = self._collect_signals(
            series.iter_lookforward(), self._lookforward_weight, amplification=1.25
        )

        bias_votes = [
            (sig.directional_bias, weight)
            for sig, weight in lookback_signals + lookforward_signals
        ]
        bias = self._weighted_vote(bias_votes, default="neutral")

        thrust = self._weighted_mean(
            [(sig.field_thrust, weight) for sig, weight in lookback_signals + lookforward_signals],
            default=0.0,
        )

        stability = self._weighted_mean(
            [(sig.field_stability, weight) for sig, weight in lookback_signals + lookforward_signals],
            default=0.5,
        )

        jump_risk = self._weighted_mean(
            [(sig.jump_risk_score, weight) for sig, weight in lookback_signals + lookforward_signals],
            default=0.0,
        )

        confidence = self._weighted_mean(
            [(sig.confidence, weight) for sig, weight in lookback_signals + lookforward_signals],
            default=0.0,
        )

        if lookback_signals and lookforward_signals:
            lb_bias = self._weighted_vote(
                [(sig.directional_bias, weight) for sig, weight in lookback_signals],
                default="neutral",
            )
            lf_bias = self._weighted_vote(
                [(sig.directional_bias, weight) for sig, weight in lookforward_signals],
                default="neutral",
            )
            if lb_bias == lf_bias and lb_bias != "neutral":
                confidence = min(1.0, confidence + 0.1)
            elif lf_bias != lb_bias and lf_bias != "neutral":
                bias = lf_bias
                confidence *= 0.75

            thrust_delta = (
                self._weighted_mean(
                    [(sig.field_thrust, weight) for sig, weight in lookforward_signals], default=0.0
                )
                - self._weighted_mean(
                    [(sig.field_thrust, weight) for sig, weight in lookback_signals], default=0.0
                )
            )
            if thrust_delta > 0:
                stability = max(0.0, min(1.0, stability - min(thrust_delta * 0.05, 0.2)))

        return HedgeAgentPacket(
            symbol=self._resolve_symbol(lookback_signals, lookforward_signals),
            timestamp=ctx.as_of,
            bias=bias,
            thrust_energy=thrust,
            field_stability=max(0.0, min(1.0, stability)),
            jump_risk_score=max(0.0, min(1.0, jump_risk)),
            confidence=max(0.0, min(1.0, confidence)),
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _collect_signals(
        self,
        series: Iterable[Tuple[timedelta, Sequence[HedgeEngineSignals] | HedgeEngineSignals]],
        weight_fn,
        amplification: float = 1.0,
    ) -> list[Tuple[HedgeEngineSignals, float]]:
        collected: list[Tuple[HedgeEngineSignals, float]] = []
        for span, payloads in series:
            signal = self._select_latest(payloads)
            if signal is None:
                continue
            collected.append((signal, weight_fn(span) * amplification))
        return collected

    @staticmethod
    def _select_latest(
        payloads: Sequence[HedgeEngineSignals] | HedgeEngineSignals | None,
    ) -> HedgeEngineSignals | None:
        if payloads is None:
            return None
        if isinstance(payloads, Sequence) and not isinstance(payloads, (str, bytes)):
            return payloads[-1] if payloads else None
        if isinstance(payloads, HedgeEngineSignals):
            return payloads
        return None

    @staticmethod
    def _weighted_vote(
        votes: Sequence[Tuple[str, float]],
        default: str = "neutral",
    ) -> str:
        totals: dict[str, float] = {}
        for label, weight in votes:
            totals[label] = totals.get(label, 0.0) + weight
        if not totals:
            return default
        return max(totals.items(), key=lambda item: item[1])[0]

    @staticmethod
    def _weighted_mean(values: Sequence[Tuple[float, float]], default: float = 0.0) -> float:
        total_weight = sum(weight for _, weight in values)
        if total_weight == 0:
            return default
        return sum(value * weight for value, weight in values) / total_weight

    @staticmethod
    def _resolve_symbol(
        lookback: Sequence[Tuple[HedgeEngineSignals, float]],
        lookforward: Sequence[Tuple[HedgeEngineSignals, float]],
    ) -> str:
        for seq in (lookback, lookforward):
            if seq:
                return seq[0][0].symbol
        return ""

    @staticmethod
    def _lookback_weight(window: timedelta) -> float:
        minutes = max(window.total_seconds() / 60.0, 1.0)
        return 1.0 / minutes

    @staticmethod
    def _lookforward_weight(horizon: timedelta) -> float:
        minutes = max(horizon.total_seconds() / 60.0, 1.0)
        return 1.0 / minutes
