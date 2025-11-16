# execution/broker/paper.py

"""
Paper Broker Simulator - Phase 8

Deterministic fill simulator for testing execution layer.

Modes:
- immediate_fill: Order fills instantly at limit price
- delayed_fill: Order fills after delay
- partial_fill: Order fills partially
- rejected: Order is rejected
- slippage: Order fills with price slippage

This broker NEVER hits a real API. It simulates fills
deterministically for reliable CI/CD testing.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import uuid4

from execution.broker.base import (
    AbstractBrokerAdapter,
    BrokerError,
    InvalidOrderError,
    OrderNotFoundError,
)
from execution.schemas import (
    BrokerResponse,
    BrokerStatus,
    OrderEnvelope,
    OrderStatus,
    OrderType,
)


class PaperMode(str, Enum):
    """Simulation modes for paper broker."""

    IMMEDIATE_FILL = "immediate_fill"  # Instant fill at limit price
    DELAYED_FILL = "delayed_fill"  # Fill after delay
    PARTIAL_FILL = "partial_fill"  # Fill partial quantity
    REJECTED = "rejected"  # Reject order
    SLIPPAGE = "slippage"  # Fill with slippage


class PaperBroker(AbstractBrokerAdapter):
    """
    Paper broker simulator for testing.

    This broker simulates fills deterministically without
    hitting any real API. Perfect for CI/CD and unit tests.
    """

    def __init__(
        self,
        mode: PaperMode = PaperMode.IMMEDIATE_FILL,
        delay_seconds: float = 1.0,
        slippage_pct: float = 0.01,  # 1% slippage
        partial_fill_ratio: float = 0.5,  # Fill 50% of order
    ):
        """
        Initialize paper broker.

        Args:
            mode: Simulation mode
            delay_seconds: Delay for delayed_fill mode
            slippage_pct: Slippage percentage for slippage mode
            partial_fill_ratio: Fill ratio for partial_fill mode
        """
        self.mode = mode
        self.delay_seconds = delay_seconds
        self.slippage_pct = slippage_pct
        self.partial_fill_ratio = partial_fill_ratio

        # In-memory order book
        self._orders: dict[str, dict] = {}

    def submit_order(self, envelope: OrderEnvelope) -> BrokerResponse:
        """
        Simulate order submission.

        Args:
            envelope: Order envelope

        Returns:
            BrokerResponse with simulated result
        """
        # Validate order
        if envelope.instruction.size_delta <= 0:
            return BrokerResponse(
                success=False,
                status=OrderStatus.REJECTED,
                error_code="INVALID_SIZE",
                error_message="Size delta must be positive",
            )

        # Generate broker order ID
        broker_order_id = f"PAPER-{uuid4().hex[:8].upper()}"

        # Determine fill behavior based on mode
        if self.mode == PaperMode.REJECTED:
            return self._simulate_rejection(broker_order_id)

        elif self.mode == PaperMode.IMMEDIATE_FILL:
            return self._simulate_immediate_fill(envelope, broker_order_id)

        elif self.mode == PaperMode.DELAYED_FILL:
            return self._simulate_delayed_fill(envelope, broker_order_id)

        elif self.mode == PaperMode.PARTIAL_FILL:
            return self._simulate_partial_fill(envelope, broker_order_id)

        elif self.mode == PaperMode.SLIPPAGE:
            return self._simulate_slippage_fill(envelope, broker_order_id)

        else:
            raise BrokerError(f"Unknown mode: {self.mode}")

    def fetch_status(self, broker_order_id: str) -> BrokerStatus:
        """
        Query order status.

        Args:
            broker_order_id: Broker order ID

        Returns:
            BrokerStatus with current state
        """
        if broker_order_id not in self._orders:
            raise OrderNotFoundError(f"Order not found: {broker_order_id}")

        order = self._orders[broker_order_id]

        return BrokerStatus(
            broker_order_id=broker_order_id,
            status=order["status"],
            fill_price=order.get("fill_price"),
            filled_quantity=order.get("filled_quantity", 0),
            remaining_quantity=order.get("remaining_quantity", 0),
            submitted_at=order.get("submitted_at"),
            updated_at=datetime.now(timezone.utc),
        )

    def cancel_order(self, broker_order_id: str) -> BrokerResponse:
        """
        Cancel order.

        Args:
            broker_order_id: Broker order ID

        Returns:
            BrokerResponse with cancellation result
        """
        if broker_order_id not in self._orders:
            raise OrderNotFoundError(f"Order not found: {broker_order_id}")

        order = self._orders[broker_order_id]

        # Can only cancel pending/submitted orders
        if order["status"] in [OrderStatus.FILLED, OrderStatus.CANCELLED]:
            return BrokerResponse(
                success=False,
                broker_order_id=broker_order_id,
                status=order["status"],
                error_code="CANNOT_CANCEL",
                error_message=f"Order is already {order['status']}",
            )

        # Update status
        order["status"] = OrderStatus.CANCELLED
        order["updated_at"] = datetime.now(timezone.utc)

        return BrokerResponse(
            success=True,
            broker_order_id=broker_order_id,
            status=OrderStatus.CANCELLED,
        )

    def get_account_info(self) -> dict:
        """
        Get simulated account info.

        Returns:
            Dict with account details
        """
        return {
            "equity": 100_000.0,
            "cash": 50_000.0,
            "buying_power": 200_000.0,  # 2x margin
            "positions": [],
            "account_type": "paper",
        }

    # Helper methods for simulation

    def _simulate_rejection(self, broker_order_id: str) -> BrokerResponse:
        """Simulate order rejection."""
        self._orders[broker_order_id] = {
            "status": OrderStatus.REJECTED,
            "submitted_at": datetime.now(timezone.utc),
        }

        return BrokerResponse(
            success=False,
            broker_order_id=broker_order_id,
            status=OrderStatus.REJECTED,
            error_code="REJECTED",
            error_message="Order rejected by broker (simulated)",
        )

    def _simulate_immediate_fill(
        self, envelope: OrderEnvelope, broker_order_id: str
    ) -> BrokerResponse:
        """Simulate immediate fill at limit price."""
        fill_price = envelope.limit_price or 100.0  # Default if no limit
        filled_quantity = envelope.instruction.size_delta

        self._orders[broker_order_id] = {
            "status": OrderStatus.FILLED,
            "fill_price": fill_price,
            "filled_quantity": filled_quantity,
            "remaining_quantity": 0,
            "submitted_at": datetime.now(timezone.utc),
        }

        return BrokerResponse(
            success=True,
            broker_order_id=broker_order_id,
            status=OrderStatus.FILLED,
            fill_price=fill_price,
            filled_quantity=filled_quantity,
        )

    def _simulate_delayed_fill(
        self, envelope: OrderEnvelope, broker_order_id: str
    ) -> BrokerResponse:
        """Simulate delayed fill (submitted, will fill later)."""
        self._orders[broker_order_id] = {
            "status": OrderStatus.SUBMITTED,
            "submitted_at": datetime.now(timezone.utc),
            "will_fill_at": time.time() + self.delay_seconds,
            "fill_price": envelope.limit_price or 100.0,
            "filled_quantity": envelope.instruction.size_delta,
        }

        return BrokerResponse(
            success=True,
            broker_order_id=broker_order_id,
            status=OrderStatus.SUBMITTED,
        )

    def _simulate_partial_fill(
        self, envelope: OrderEnvelope, broker_order_id: str
    ) -> BrokerResponse:
        """Simulate partial fill."""
        total_quantity = envelope.instruction.size_delta
        filled_quantity = int(total_quantity * self.partial_fill_ratio)
        remaining_quantity = total_quantity - filled_quantity

        fill_price = envelope.limit_price or 100.0

        self._orders[broker_order_id] = {
            "status": OrderStatus.PARTIALLY_FILLED,
            "fill_price": fill_price,
            "filled_quantity": filled_quantity,
            "remaining_quantity": remaining_quantity,
            "submitted_at": datetime.now(timezone.utc),
        }

        return BrokerResponse(
            success=True,
            broker_order_id=broker_order_id,
            status=OrderStatus.PARTIALLY_FILLED,
            fill_price=fill_price,
            filled_quantity=filled_quantity,
        )

    def _simulate_slippage_fill(
        self, envelope: OrderEnvelope, broker_order_id: str
    ) -> BrokerResponse:
        """Simulate fill with slippage."""
        limit_price = envelope.limit_price or 100.0

        # Apply slippage (worse price for buyer)
        if envelope.instruction.action.value == "open":
            # Buying: fill at higher price
            fill_price = limit_price * (1 + self.slippage_pct)
        else:
            # Selling: fill at lower price
            fill_price = limit_price * (1 - self.slippage_pct)

        filled_quantity = envelope.instruction.size_delta

        self._orders[broker_order_id] = {
            "status": OrderStatus.FILLED,
            "fill_price": fill_price,
            "filled_quantity": filled_quantity,
            "remaining_quantity": 0,
            "submitted_at": datetime.now(timezone.utc),
        }

        return BrokerResponse(
            success=True,
            broker_order_id=broker_order_id,
            status=OrderStatus.FILLED,
            fill_price=fill_price,
            filled_quantity=filled_quantity,
            metadata={"slippage_pct": self.slippage_pct},
        )
