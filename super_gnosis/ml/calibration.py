"""Calibration hooks for adapting model outputs."""

from __future__ import annotations

from typing import Protocol, Any


class CalibrationStrategy(Protocol):
    """Protocol for calibration or post-processing strategies."""

    def calibrate(self, predictions: Any) -> Any:
        ...
