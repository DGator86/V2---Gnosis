# tests/execution/test_broker_simulator.py

"""
Tests for PaperBroker - Phase 8

Test coverage:
- Immediate fill mode
- Delayed fill mode
- Partial fill mode
- Rejection mode
- Slippage mode
- Order validation
- Status queries
- Order cancellation
- Deterministic behavior
"""

from __future__ import annotations

import pytest

from agents.portfolio.schemas import OrderAction, OrderInstruction, StrategyType
from agents.trade_agent.schemas import TradeIdea
from execution.broker import OrderNotFoundError, PaperBroker, PaperMode
from execution.schemas import OrderEnvelope, OrderStatus, OrderType
from execution.registry import generate_idempotency_key


@pytest.fixture
def sample_instruction():
    """Create sample OrderInstruction."""
    idea = TradeIdea(
        asset="SPY",
        strategy_type=StrategyType.LONG_CALL,
        description="Bullish call",
        legs=[],
        total_cost=1000.0,
        max_risk=1000.0,
        recommended_size=1,
        confidence=0.8,
    )

    return OrderInstruction(
        action=OrderAction.OPEN,
        asset="SPY",
        strategy_type=StrategyType.LONG_CALL,
        size_delta=1,
        notional_risk=1000.0,
        reason="test order",
        source_idea=idea,
    )


@pytest.fixture
def sample_envelope(sample_instruction):
    """Create sample OrderEnvelope."""
    idempotency_key = generate_idempotency_key(sample_instruction)

    return OrderEnvelope(
        idempotency_key=idempotency_key,
        instruction=sample_instruction,
        order_type=OrderType.LIMIT,
        limit_price=450.0,
    )


class TestImmediateFillMode:
    """Test immediate fill mode."""

    def test_immediate_fill_at_limit_price(self, sample_envelope):
        """Test order fills instantly at limit price."""
        broker = PaperBroker(mode=PaperMode.IMMEDIATE_FILL)

        response = broker.submit_order(sample_envelope)

        assert response.success is True
        assert response.status == OrderStatus.FILLED
        assert response.fill_price == sample_envelope.limit_price
        assert response.filled_quantity == sample_envelope.instruction.size_delta
        assert response.broker_order_id is not None

    def test_immediate_fill_status_query(self, sample_envelope):
        """Test status query after immediate fill."""
        broker = PaperBroker(mode=PaperMode.IMMEDIATE_FILL)

        response = broker.submit_order(sample_envelope)
        status = broker.fetch_status(response.broker_order_id)

        assert status.status == OrderStatus.FILLED
        assert status.fill_price == sample_envelope.limit_price
        assert status.filled_quantity == sample_envelope.instruction.size_delta


class TestDelayedFillMode:
    """Test delayed fill mode."""

    def test_delayed_fill_returns_submitted(self, sample_envelope):
        """Test delayed fill returns submitted status."""
        broker = PaperBroker(mode=PaperMode.DELAYED_FILL, delay_seconds=1.0)

        response = broker.submit_order(sample_envelope)

        assert response.success is True
        assert response.status == OrderStatus.SUBMITTED
        assert response.broker_order_id is not None

    def test_delayed_fill_status_initially_submitted(self, sample_envelope):
        """Test status query shows submitted before delay."""
        broker = PaperBroker(mode=PaperMode.DELAYED_FILL, delay_seconds=10.0)

        response = broker.submit_order(sample_envelope)
        status = broker.fetch_status(response.broker_order_id)

        assert status.status == OrderStatus.SUBMITTED


class TestPartialFillMode:
    """Test partial fill mode."""

    def test_partial_fill_fills_partial_quantity(self, sample_envelope):
        """Test partial fill mode fills only part of order."""
        broker = PaperBroker(mode=PaperMode.PARTIAL_FILL, partial_fill_ratio=0.5)

        # Order for 2 contracts
        sample_envelope.instruction.size_delta = 2

        response = broker.submit_order(sample_envelope)

        assert response.success is True
        assert response.status == OrderStatus.PARTIALLY_FILLED
        assert response.filled_quantity == 1  # 50% of 2
        assert response.fill_price == sample_envelope.limit_price

    def test_partial_fill_status_shows_remaining(self, sample_envelope):
        """Test status query shows filled and remaining quantities."""
        broker = PaperBroker(mode=PaperMode.PARTIAL_FILL, partial_fill_ratio=0.5)

        sample_envelope.instruction.size_delta = 4

        response = broker.submit_order(sample_envelope)
        status = broker.fetch_status(response.broker_order_id)

        assert status.filled_quantity == 2  # 50% of 4
        assert status.remaining_quantity == 2  # Remaining 50%


class TestRejectedMode:
    """Test rejection mode."""

    def test_rejected_mode_rejects_order(self, sample_envelope):
        """Test rejection mode rejects all orders."""
        broker = PaperBroker(mode=PaperMode.REJECTED)

        response = broker.submit_order(sample_envelope)

        assert response.success is False
        assert response.status == OrderStatus.REJECTED
        assert response.error_code == "REJECTED"
        assert response.error_message is not None

    def test_rejected_status_query(self, sample_envelope):
        """Test status query for rejected order."""
        broker = PaperBroker(mode=PaperMode.REJECTED)

        response = broker.submit_order(sample_envelope)
        status = broker.fetch_status(response.broker_order_id)

        assert status.status == OrderStatus.REJECTED


class TestSlippageMode:
    """Test slippage mode."""

    def test_slippage_mode_fills_with_slippage(self, sample_envelope):
        """Test slippage mode fills at worse price."""
        broker = PaperBroker(mode=PaperMode.SLIPPAGE, slippage_pct=0.01)  # 1%

        response = broker.submit_order(sample_envelope)

        assert response.success is True
        assert response.status == OrderStatus.FILLED

        # For open (buy) orders, slippage means higher price
        expected_fill = sample_envelope.limit_price * 1.01
        assert response.fill_price == pytest.approx(expected_fill, rel=1e-6)

    def test_slippage_metadata_included(self, sample_envelope):
        """Test slippage mode includes slippage in metadata."""
        broker = PaperBroker(mode=PaperMode.SLIPPAGE, slippage_pct=0.02)

        response = broker.submit_order(sample_envelope)

        assert "slippage_pct" in response.metadata
        assert response.metadata["slippage_pct"] == 0.02


class TestOrderValidation:
    """Test order validation."""

    def test_zero_size_delta_rejected(self, sample_envelope):
        """Test orders with zero size are rejected."""
        broker = PaperBroker(mode=PaperMode.IMMEDIATE_FILL)

        sample_envelope.instruction.size_delta = 0

        response = broker.submit_order(sample_envelope)

        assert response.success is False
        assert response.status == OrderStatus.REJECTED
        assert "INVALID_SIZE" in response.error_code

    def test_negative_size_delta_rejected(self, sample_envelope):
        """Test orders with negative size are rejected."""
        broker = PaperBroker(mode=PaperMode.IMMEDIATE_FILL)

        sample_envelope.instruction.size_delta = -1

        response = broker.submit_order(sample_envelope)

        assert response.success is False
        assert response.status == OrderStatus.REJECTED


class TestOrderCancellation:
    """Test order cancellation."""

    def test_cancel_submitted_order_succeeds(self, sample_envelope):
        """Test canceling submitted order succeeds."""
        broker = PaperBroker(mode=PaperMode.DELAYED_FILL)

        response = broker.submit_order(sample_envelope)
        assert response.status == OrderStatus.SUBMITTED

        cancel_response = broker.cancel_order(response.broker_order_id)

        assert cancel_response.success is True
        assert cancel_response.status == OrderStatus.CANCELLED

    def test_cancel_filled_order_fails(self, sample_envelope):
        """Test canceling filled order fails."""
        broker = PaperBroker(mode=PaperMode.IMMEDIATE_FILL)

        response = broker.submit_order(sample_envelope)
        assert response.status == OrderStatus.FILLED

        cancel_response = broker.cancel_order(response.broker_order_id)

        assert cancel_response.success is False
        assert cancel_response.error_code == "CANNOT_CANCEL"

    def test_cancel_nonexistent_order_raises(self):
        """Test canceling nonexistent order raises error."""
        broker = PaperBroker(mode=PaperMode.IMMEDIATE_FILL)

        with pytest.raises(OrderNotFoundError):
            broker.cancel_order("NONEXISTENT-ORDER")


class TestStatusQueries:
    """Test status query operations."""

    def test_fetch_status_nonexistent_order_raises(self):
        """Test querying nonexistent order raises error."""
        broker = PaperBroker(mode=PaperMode.IMMEDIATE_FILL)

        with pytest.raises(OrderNotFoundError):
            broker.fetch_status("NONEXISTENT-ORDER")

    def test_fetch_status_returns_current_state(self, sample_envelope):
        """Test status query returns current order state."""
        broker = PaperBroker(mode=PaperMode.IMMEDIATE_FILL)

        response = broker.submit_order(sample_envelope)
        status = broker.fetch_status(response.broker_order_id)

        assert status.broker_order_id == response.broker_order_id
        assert status.status == response.status
        assert status.fill_price == response.fill_price


class TestAccountInfo:
    """Test account info queries."""

    def test_get_account_info_returns_paper_account(self):
        """Test account info returns simulated account."""
        broker = PaperBroker()

        account = broker.get_account_info()

        assert account["equity"] == 100_000.0
        assert account["cash"] == 50_000.0
        assert account["buying_power"] == 200_000.0
        assert account["account_type"] == "paper"


class TestDeterministicBehavior:
    """Test deterministic behavior for testing."""

    def test_same_input_same_output(self, sample_envelope):
        """Test deterministic: same input → same output."""
        broker1 = PaperBroker(mode=PaperMode.IMMEDIATE_FILL)
        broker2 = PaperBroker(mode=PaperMode.IMMEDIATE_FILL)

        response1 = broker1.submit_order(sample_envelope)
        response2 = broker2.submit_order(sample_envelope)

        # Same fill behavior (though order IDs will differ)
        assert response1.status == response2.status
        assert response1.fill_price == response2.fill_price
        assert response1.filled_quantity == response2.filled_quantity

    def test_slippage_deterministic(self, sample_envelope):
        """Test slippage is deterministic for given parameters."""
        broker1 = PaperBroker(mode=PaperMode.SLIPPAGE, slippage_pct=0.01)
        broker2 = PaperBroker(mode=PaperMode.SLIPPAGE, slippage_pct=0.01)

        response1 = broker1.submit_order(sample_envelope)
        response2 = broker2.submit_order(sample_envelope)

        assert response1.fill_price == response2.fill_price
