# execution/broker_adapters/__init__.py

"""
Broker adapter implementations for Trade Agent v3.

Provides unified interface for multiple brokers:
- Alpaca: Commission-free stock/crypto trading
- IBKR: Professional options/futures platform
- Tradier: Developer-friendly options API
- Simulated: Paper trading for testing
"""

from .base import BrokerAdapter
from .simulated_adapter import SimulatedBrokerAdapter

__all__ = [
    "BrokerAdapter",
    "SimulatedBrokerAdapter",
]
