# execution/broker/__init__.py

"""
Broker Adapters - Phase 8

This module contains all broker adapter implementations.
All adapters implement AbstractBrokerAdapter interface.

Available adapters:
- PaperBroker: Deterministic simulator for testing
- RobinhoodBroker: Robinhood API adapter (stub)
- TradierBroker: Tradier API adapter (stub)
"""

from .base import (
    AbstractBrokerAdapter,
    BrokerError,
    InsufficientFundsError,
    InvalidOrderError,
    NetworkError,
    OrderNotFoundError,
)
from .paper import PaperBroker, PaperMode

__all__ = [
    # Base
    "AbstractBrokerAdapter",
    "BrokerError",
    "NetworkError",
    "OrderNotFoundError",
    "InsufficientFundsError",
    "InvalidOrderError",
    # Paper
    "PaperBroker",
    "PaperMode",
]
