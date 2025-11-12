"""
Validation modules for statistical testing and feature quality control.

This package provides rigorous statistical validation:
- MCPT: Monte Carlo Permutation Tests for strategy significance
- Independence: Feature correlation and redundancy checks
- Reversibility: Causality and look-ahead bias detection
"""

from .mcpt import mcpt_validate, MCPTResult, mcpt_multiple_strategies
from .independence import check_feature_independence, IndependenceReport
from .reversibility import test_reversibility, ReversibilityResult

__all__ = [
    # MCPT
    "mcpt_validate",
    "MCPTResult",
    "mcpt_multiple_strategies",
    # Independence
    "check_feature_independence",
    "IndependenceReport",
    # Reversibility
    "test_reversibility",
    "ReversibilityResult",
]
