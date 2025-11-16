# execution/broker_adapters/base.py

"""
Base broker adapter protocol for Trade Agent v3.

Defines the unified interface that all broker adapters must implement.
Uses Protocol for structural subtyping (duck typing with type checking).
"""

from __future__ import annotations

from typing import Protocol, List

from ..schemas import (
    OrderRequest,
    OrderResult,
    AccountInfo,
    Position,
    Quote,
)


class BrokerAdapter(Protocol):
    """
    Unified broker adapter interface.
    
    All broker implementations (Alpaca, IBKR, Tradier, Simulated) must
    implement this protocol to ensure compatibility with the execution layer.
    """
    
    def get_account(self) -> AccountInfo:
        """
        Retrieve current account information.
        
        Returns:
            AccountInfo with cash, buying power, positions, etc.
        """
        ...
    
    def get_positions(self) -> List[Position]:
        """
        Get all current positions.
        
        Returns:
            List of Position objects
        """
        ...
    
    def place_order(self, order: OrderRequest) -> OrderResult:
        """
        Submit an order to the broker.
        
        Args:
            order: OrderRequest with order details
        
        Returns:
            OrderResult with order ID and status
        
        Raises:
            BrokerError: If order submission fails
        """
        ...
    
    def get_order_status(self, order_id: str) -> OrderResult:
        """
        Check status of an existing order.
        
        Args:
            order_id: Broker's order identifier
        
        Returns:
            OrderResult with current status and fills
        """
        ...
    
    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel a pending order.
        
        Args:
            order_id: Broker's order identifier
        
        Returns:
            True if cancellation successful, False otherwise
        """
        ...
    
    def get_quote(self, symbol: str) -> Quote:
        """
        Get real-time quote for a symbol.
        
        Args:
            symbol: Ticker symbol or option symbol (OCC format)
        
        Returns:
            Quote with bid, ask, last, sizes
        """
        ...
    
    def get_quotes_batch(self, symbols: List[str]) -> List[Quote]:
        """
        Get quotes for multiple symbols (batch request).
        
        Args:
            symbols: List of ticker/option symbols
        
        Returns:
            List of Quote objects
        """
        ...


class BrokerError(Exception):
    """Base exception for broker-related errors."""
    pass


class InsufficientFundsError(BrokerError):
    """Raised when account has insufficient funds for order."""
    pass


class InvalidOrderError(BrokerError):
    """Raised when order parameters are invalid."""
    pass


class BrokerConnectionError(BrokerError):
    """Raised when broker API connection fails."""
    pass
