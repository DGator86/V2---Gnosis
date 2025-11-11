"""
Trade package initialization.
Provides trade construction and risk management functions.
"""

from .trade_constructor import construct_trade_ideas
from .risk import (
    compute_position_size,
    apply_kelly_fraction,
    check_portfolio_limits,
    calculate_var,
)

__all__ = [
    'construct_trade_ideas',
    'compute_position_size',
    'apply_kelly_fraction',
    'check_portfolio_limits',
    'calculate_var',
]
