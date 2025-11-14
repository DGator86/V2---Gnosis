from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, Mapping, Protocol, Sequence, Tuple


class AgentOutput(Protocol):
    """Marker protocol for all agent outputs."""


@dataclass(frozen=True)
class LookbackLookforwardConfig:
    """Canonical look-back/look-forward configuration enforced for agents."""

    lookback_windows: Sequence[timedelta]
    lookforward_horizons: Sequence[timedelta]


@dataclass
class EngineTimeSeries:
    """Container of time-aligned look-back and look-forward payloads."""

    lookback: Mapping[timedelta, Sequence[Any]]
    lookforward: Mapping[timedelta, Sequence[Any]]

    def iter_lookback(self) -> Iterable[Tuple[timedelta, Sequence[Any]]]:
        for window in sorted(self.lookback.keys(), key=lambda d: d.total_seconds()):
            yield window, self.lookback[window]

    def iter_lookforward(self) -> Iterable[Tuple[timedelta, Sequence[Any]]]:
        for horizon in sorted(self.lookforward.keys(), key=lambda d: d.total_seconds()):
            yield horizon, self.lookforward[horizon]


@dataclass
class TimeContext:
    """Concrete data slices for a given ``as_of`` timestamp."""

    as_of: datetime
    engine_time_series: Dict[str, EngineTimeSeries]

    def require_engine(self, engine: str) -> EngineTimeSeries:
        try:
            return self.engine_time_series[engine]
        except KeyError as exc:  # pragma: no cover - defensive guard
            raise KeyError(f"Missing engine '{engine}' in TimeContext") from exc


DEFAULT_LOOKBACK_WINDOWS: Tuple[timedelta, ...] = (
    timedelta(minutes=5),
    timedelta(minutes=30),
    timedelta(hours=2),
    timedelta(days=1),
    timedelta(weeks=1),
    timedelta(days=30),
)
DEFAULT_LOOKFORWARD_HORIZONS: Tuple[timedelta, ...] = (
    timedelta(minutes=5),
    timedelta(minutes=30),
    timedelta(hours=2),
    timedelta(days=1),
)
DEFAULT_LOOKBACK_LOOKFORWARD_CONFIG = LookbackLookforwardConfig(
    lookback_windows=DEFAULT_LOOKBACK_WINDOWS,
    lookforward_horizons=DEFAULT_LOOKFORWARD_HORIZONS,
)


class BaseAgent(ABC):
    """Base class for agents consuming multi-scale temporal context."""

    def __init__(self, config: LookbackLookforwardConfig | None = None) -> None:
        self.config = config or DEFAULT_LOOKBACK_LOOKFORWARD_CONFIG

    @abstractmethod
    def name(self) -> str:
        ...

    def engine_dependencies(self) -> Tuple[str, ...]:
        """Engine keys this agent expects within ``TimeContext``."""

        return (self.name(),)

    @abstractmethod
    def analyze(self, ctx: TimeContext) -> AgentOutput:
        """Fuse multi-timescale signals into a single output."""

    def run(self, ctx: TimeContext) -> AgentOutput:
        """Public entry point enforcing look-back/look-forward usage."""

        self._validate_context(ctx)
        return self.analyze(ctx)

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------
    def _validate_context(self, ctx: TimeContext) -> None:
        for engine in self.engine_dependencies():
            series = ctx.require_engine(engine)
            missing_lb = [
                window for window in self.config.lookback_windows if window not in series.lookback
            ]
            missing_lf = [
                horizon
                for horizon in self.config.lookforward_horizons
                if horizon not in series.lookforward
            ]
            if missing_lb:
                raise ValueError(
                    f"TimeContext for agent '{self.name()}' is missing look-back windows: {missing_lb}"
                )
            if missing_lf:
                raise ValueError(
                    f"TimeContext for agent '{self.name()}' is missing look-forward horizons: {missing_lf}"
                )
            if not any(series.lookback[window] for window in self.config.lookback_windows):
                raise ValueError(
                    f"TimeContext for agent '{self.name()}' contains no look-back payloads"
                )
            if not any(series.lookforward[h] for h in self.config.lookforward_horizons):
                raise ValueError(
                    f"TimeContext for agent '{self.name()}' contains no look-forward payloads"
                )
