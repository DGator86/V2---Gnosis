# execution/__init__.py

"""
Execution Orchestration Layer v1.0 - Phase 8

Broker-safe, idempotent, auditable, replayable, fault-tolerant execution.

This is NOT a wrapper around broker APIs.
This is a GUARANTEES layer.

Key Guarantees:
1. Idempotency: Same order twice → deduplicated
2. Durability: Orders persisted before broker submission
3. Recoverability: System can crash and restart safely
4. Traceability: Full audit trail of all orders
5. Broker abstraction: Plug-and-play broker switching
6. Deterministic testing: Paper broker for CI/CD

Architecture:
    OrderInstruction (Portfolio Manager)
        ↓
    ExecutionOrchestrator
        ↓
    OrderEnvelope (+ persistence)
        ↓
    BrokerAdapter (Abstract)
        ├── PaperBroker (testing)
        ├── RobinhoodBroker (prod)
        └── TradierBroker (prod)
        ↓
    Broker API

Components:
- ExecutionOrchestrator: Main coordinator
- ExecutionRegistry: DuckDB-backed persistence
- OrderEnvelope: Durable order wrapper
- AbstractBrokerAdapter: Broker interface
- PaperBroker: Deterministic simulator
"""

from .broker import (
    AbstractBrokerAdapter,
    BrokerError,
    InsufficientFundsError,
    InvalidOrderError,
    NetworkError,
    OrderNotFoundError,
    PaperBroker,
    PaperMode,
)
from .orchestrator import ExecutionOrchestrator
from .registry import ExecutionRegistry, generate_idempotency_key
from .schemas import (
    BrokerResponse,
    BrokerStatus,
    ExecutionRecord,
    OrderEnvelope,
    OrderStatus,
    OrderType,
)

__all__ = [
    # Orchestrator
    "ExecutionOrchestrator",
    # Registry
    "ExecutionRegistry",
    "generate_idempotency_key",
    # Schemas
    "OrderEnvelope",
    "ExecutionRecord",
    "BrokerResponse",
    "BrokerStatus",
    "OrderStatus",
    "OrderType",
    # Broker
    "AbstractBrokerAdapter",
    "BrokerError",
    "NetworkError",
    "OrderNotFoundError",
    "InsufficientFundsError",
    "InvalidOrderError",
    "PaperBroker",
    "PaperMode",
]
