"""Parameter update strategies for adaptation layer."""

from __future__ import annotations

from typing import Protocol, Mapping


class ParameterUpdateStrategy(Protocol):
    """Protocol for applying parameter updates based on feedback."""

    def apply_updates(self, updates: Mapping[str, float]) -> None:
        ...
