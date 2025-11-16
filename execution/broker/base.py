# execution/broker/base.py

"""
Abstract Broker Adapter - Phase 8

Defines the interface all broker implementations must follow.
This allows plug-and-play broker switching without modifying
the execution orchestrator.

Implementations:
- PaperBroker: Deterministic simulator for testing
- RobinhoodBroker: Robinhood API adapter
- TradierBroker: Tradier API adapter
- AlpacaBroker: Alpaca API adapter
- IBBroker: Interactive Brokers TWS adapter
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from execution.schemas import BrokerResponse, BrokerStatus, OrderEnvelope


class AbstractBrokerAdapter(ABC):
    """
    Abstract base class for all broker adapters.

    All broker implementations must implement these methods
    to ensure compatibility with ExecutionOrchestrator.
    """

    @abstractmethod
    def submit_order(self, envelope: OrderEnvelope) -> BrokerResponse:
        """
        Submit order to broker.

        Args:
            envelope: Order envelope with instruction and metadata

        Returns:
            BrokerResponse with submission result

        Raises:
            BrokerError: If submission fails due to broker issues
            NetworkError: If submission fails due to network issues
        """
        pass

    @abstractmethod
    def fetch_status(self, broker_order_id: str) -> BrokerStatus:
        """
        Query current status of an order.

        Args:
            broker_order_id: Broker-assigned order ID

        Returns:
            BrokerStatus with current order state

        Raises:
            BrokerError: If query fails
            OrderNotFoundError: If order doesn't exist
        """
        pass

    @abstractmethod
    def cancel_order(self, broker_order_id: str) -> BrokerResponse:
        """
        Cancel a pending order.

        Args:
            broker_order_id: Broker-assigned order ID

        Returns:
            BrokerResponse with cancellation result

        Raises:
            BrokerError: If cancellation fails
            OrderNotFoundError: If order doesn't exist
        """
        pass

    @abstractmethod
    def get_account_info(self) -> dict:
        """
        Get current account information.

        Returns:
            Dict with account details (equity, cash, positions, etc.)

        Raises:
            BrokerError: If query fails
        """
        pass


class BrokerError(Exception):
    """Base exception for broker-related errors."""

    pass


class NetworkError(BrokerError):
    """Network-related errors (timeout, connection, etc.)."""

    pass


class OrderNotFoundError(BrokerError):
    """Order doesn't exist in broker system."""

    pass


class InsufficientFundsError(BrokerError):
    """Not enough capital to place order."""

    pass


class InvalidOrderError(BrokerError):
    """Order parameters are invalid."""

    pass
