"""
Composer Agent - Resolution Module

Handles conflict resolution and regime-based weighting.
"""

from .regime_weights import compute_regime_weights, infer_global_regime
from .conflict_resolver import summarize_conflicts

__all__ = ["compute_regime_weights", "infer_global_regime", "summarize_conflicts"]
