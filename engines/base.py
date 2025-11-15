from __future__ import annotations

"""Common engine interfaces for the Super Gnosis pipeline."""

from datetime import datetime
from typing import Protocol

from schemas.core_schemas import EngineOutput


class Engine(Protocol):
    """Protocol describing the behaviour of all engines."""

    def run(self, symbol: str, now: datetime) -> EngineOutput:
        """Return an :class:`EngineOutput` for ``symbol`` at ``now``."""

        raise NotImplementedError
