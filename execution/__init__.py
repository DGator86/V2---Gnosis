# execution/__init__.py

"""
Super Gnosis Execution Layer (Trade Agent v3)

Institutional-grade execution infrastructure for options trading.
Provides broker connectivity, smart order routing, execution cost modeling,
and order lifecycle management.

Key Components:
- Broker Adapters: Unified interface for multiple brokers (Alpaca, IBKR, Tradier)
- Order Router: Smart routing with limit/market decision logic
- Cost Model: Bid-ask, slippage, commission, and market impact estimation
- Order Controller: Lifecycle management with partial fills and repricing
"""

__version__ = "3.0.0"
__all__ = [
    "BrokerAdapter",
    "OrderRouter",
    "ExecutionCostModel",
    "OrderLifecycleController",
]
