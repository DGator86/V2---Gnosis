from __future__ import annotations

from typing import Iterable, Sequence, Tuple
from datetime import timedelta

from core.schemas import SentimentEngineSignals, SentimentAgentPacket

from .base import (
    BaseAgent,
    LookbackLookforwardConfig,
    TimeContext,
    DEFAULT_LOOKBACK_LOOKFORWARD_CONFIG,
)


class SentimentAgent(BaseAgent):
    """Synthesises sentiment engine signals across multiple horizons."""

    def __init__(self, config: LookbackLookforwardConfig | None = None) -> None:
        super().__init__(config or DEFAULT_LOOKBACK_LOOKFORWARD_CONFIG)

    def name(self) -> str:
        return "sentiment"

    def analyze(self, ctx: TimeContext) -> SentimentAgentPacket:
        series = ctx.require_engine("sentiment")

        lookback_signals = self._collect_signals(series.iter_lookback(), self._lookback_weight)
        lookforward_signals = self._collect_signals(
            series.iter_lookforward(), self._lookforward_weight, amplification=1.25
        )

        trend_state = self._weighted_vote(
            [(sig.trend_state, weight) for sig, weight in lookback_signals + lookforward_signals],
            default="unknown",
        )
        sentiment_bias = self._weighted_vote(
            [(sig.sentiment_bias, weight) for sig, weight in lookback_signals + lookforward_signals],
            default="mixed",
        )

        compression_prob = self._weighted_mean(
            [(sig.compression_prob, weight) for sig, weight in lookback_signals + lookforward_signals],
            default=0.0,
        )
        capitulation_prob = self._weighted_mean(
            [(sig.capitulation_prob, weight) for sig, weight in lookback_signals + lookforward_signals],
            default=0.0,
        )
        persistence_prob = self._weighted_mean(
            [(sig.trend_persistence_prob, weight) for sig, weight in lookback_signals + lookforward_signals],
            default=0.0,
        )

        confidence = self._weighted_mean(
            [(sig.confidence, weight) for sig, weight in lookback_signals + lookforward_signals],
            default=0.0,
        )

        if lookback_signals and lookforward_signals:
            lb_trend = self._weighted_vote(
                [(sig.trend_state, weight) for sig, weight in lookback_signals], default="unknown"
            )
            lf_trend = self._weighted_vote(
                [(sig.trend_state, weight) for sig, weight in lookforward_signals], default="unknown"
            )
            if lb_trend == lf_trend and lb_trend != "unknown":
                confidence = min(1.0, confidence + 0.1)
            elif lf_trend != lb_trend and lf_trend != "unknown":
                trend_state = lf_trend
                confidence *= 0.75

        return SentimentAgentPacket(
            symbol=self._resolve_symbol(lookback_signals, lookforward_signals),
            timestamp=ctx.as_of,
            trend_state=trend_state,
            sentiment_bias=sentiment_bias,
            compression_prob=max(0.0, min(1.0, compression_prob)),
            capitulation_prob=max(0.0, min(1.0, capitulation_prob)),
            trend_persistence_prob=max(0.0, min(1.0, persistence_prob)),
            confidence=max(0.0, min(1.0, confidence)),
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _collect_signals(
        self,
        series: Iterable[Tuple[timedelta, Sequence[SentimentEngineSignals] | SentimentEngineSignals]],
        weight_fn,
        amplification: float = 1.0,
    ) -> list[Tuple[SentimentEngineSignals, float]]:
        collected: list[Tuple[SentimentEngineSignals, float]] = []
        for span, payloads in series:
            signal = self._select_latest(payloads)
            if signal is None:
                continue
            collected.append((signal, weight_fn(span) * amplification))
        return collected

    @staticmethod
    def _select_latest(
        payloads: Sequence[SentimentEngineSignals] | SentimentEngineSignals | None,
    ) -> SentimentEngineSignals | None:
        if payloads is None:
            return None
        if isinstance(payloads, Sequence) and not isinstance(payloads, (str, bytes)):
            return payloads[-1] if payloads else None
        if isinstance(payloads, SentimentEngineSignals):
            return payloads
        return None

    @staticmethod
    def _weighted_vote(
        votes: Sequence[Tuple[str, float]],
        default: str,
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
        lookback: Sequence[Tuple[SentimentEngineSignals, float]],
        lookforward: Sequence[Tuple[SentimentEngineSignals, float]],
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
