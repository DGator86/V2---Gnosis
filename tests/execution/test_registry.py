# tests/execution/test_registry.py

"""
Tests for ExecutionRegistry - Phase 8

Test coverage:
- Record creation and persistence
- Idempotency key deduplication
- Status updates and history tracking
- Query operations (by ID, status, all)
- Retry count increments
- Database durability
- Envelope <-> Record conversion
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from uuid import uuid4

import pytest

from agents.portfolio.schemas import OrderAction, OrderInstruction, StrategyType
from agents.trade_agent.schemas import TradeIdea
from execution.registry import ExecutionRegistry, generate_idempotency_key
from execution.schemas import OrderEnvelope, OrderStatus, OrderType


@pytest.fixture
def temp_registry():
    """Create temporary registry for testing."""
    # Create temp dir and let DuckDB create the file
    temp_dir = tempfile.mkdtemp()
    db_path = Path(temp_dir) / "test_registry.db"

    registry = ExecutionRegistry(db_path=db_path)
    yield registry
    registry.close()

    # Cleanup
    import shutil
    if Path(temp_dir).exists():
        shutil.rmtree(temp_dir)


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


class TestRegistryBasics:
    """Test basic registry operations."""

    def test_create_envelope_new_order(self, temp_registry, sample_envelope):
        """Test creating new order envelope."""
        envelope, is_new = temp_registry.create_envelope(sample_envelope)

        assert is_new is True
        assert envelope.order_id == sample_envelope.order_id
        assert envelope.status == OrderStatus.PENDING

        # Verify persisted
        record = temp_registry.get_by_id(envelope.order_id)
        assert record is not None
        assert record.order_id == envelope.order_id

    def test_create_envelope_duplicate_idempotency_key(
        self, temp_registry, sample_envelope
    ):
        """Test idempotency: same key returns existing envelope."""
        # First submission
        envelope1, is_new1 = temp_registry.create_envelope(sample_envelope)
        assert is_new1 is True

        # Second submission with same idempotency key
        envelope2, is_new2 = temp_registry.create_envelope(sample_envelope)
        assert is_new2 is False
        assert envelope2.order_id == envelope1.order_id  # Same order

    def test_get_by_id_returns_record(self, temp_registry, sample_envelope):
        """Test fetching order by ID."""
        envelope, _ = temp_registry.create_envelope(sample_envelope)

        record = temp_registry.get_by_id(envelope.order_id)

        assert record is not None
        assert record.order_id == envelope.order_id
        assert record.status == OrderStatus.PENDING

    def test_get_by_id_nonexistent_returns_none(self, temp_registry):
        """Test fetching nonexistent order returns None."""
        record = temp_registry.get_by_id(uuid4())
        assert record is None

    def test_get_by_idempotency_key(self, temp_registry, sample_envelope):
        """Test fetching order by idempotency key."""
        envelope, _ = temp_registry.create_envelope(sample_envelope)

        fetched = temp_registry.get_by_idempotency_key(envelope.idempotency_key)

        assert fetched is not None
        assert fetched.order_id == envelope.order_id


class TestStatusUpdates:
    """Test status update operations."""

    def test_update_status_simple(self, temp_registry, sample_envelope):
        """Test simple status update."""
        envelope, _ = temp_registry.create_envelope(sample_envelope)

        temp_registry.update_status(
            order_id=envelope.order_id,
            status=OrderStatus.SUBMITTED,
            broker_order_id="BROKER-123",
        )

        record = temp_registry.get_by_id(envelope.order_id)
        assert record.status == OrderStatus.SUBMITTED
        assert record.broker_order_id == "BROKER-123"

    def test_update_status_with_fill_details(self, temp_registry, sample_envelope):
        """Test status update with fill details."""
        envelope, _ = temp_registry.create_envelope(sample_envelope)

        temp_registry.update_status(
            order_id=envelope.order_id,
            status=OrderStatus.FILLED,
            broker_order_id="BROKER-123",
            fill_price=450.25,
            filled_quantity=1,
        )

        record = temp_registry.get_by_id(envelope.order_id)
        assert record.status == OrderStatus.FILLED
        assert record.fill_price == 450.25
        assert record.filled_quantity == 1

    def test_update_status_with_error(self, temp_registry, sample_envelope):
        """Test status update with error message."""
        envelope, _ = temp_registry.create_envelope(sample_envelope)

        temp_registry.update_status(
            order_id=envelope.order_id,
            status=OrderStatus.ERROR,
            error_message="Network timeout",
        )

        record = temp_registry.get_by_id(envelope.order_id)
        assert record.status == OrderStatus.ERROR
        assert record.error_message == "Network timeout"

    def test_status_history_tracking(self, temp_registry, sample_envelope):
        """Test status history is appended on updates."""
        envelope, _ = temp_registry.create_envelope(sample_envelope)

        # Initial state
        record = temp_registry.get_by_id(envelope.order_id)
        assert len(record.status_history) == 1

        # Update to submitted
        temp_registry.update_status(
            order_id=envelope.order_id,
            status=OrderStatus.SUBMITTED,
        )

        record = temp_registry.get_by_id(envelope.order_id)
        assert len(record.status_history) == 2
        assert record.status_history[-1]["new_status"] == "submitted"

        # Update to filled
        temp_registry.update_status(
            order_id=envelope.order_id,
            status=OrderStatus.FILLED,
            fill_price=450.0,
        )

        record = temp_registry.get_by_id(envelope.order_id)
        assert len(record.status_history) == 3
        assert record.status_history[-1]["new_status"] == "filled"


class TestQueryOperations:
    """Test query operations."""

    def test_get_by_status(self, temp_registry, sample_instruction):
        """Test fetching orders by status."""
        # Create multiple orders with different statuses
        env1 = OrderEnvelope(
            idempotency_key="key1",
            instruction=sample_instruction,
            order_type=OrderType.LIMIT,
            limit_price=450.0,
        )
        env2 = OrderEnvelope(
            idempotency_key="key2",
            instruction=sample_instruction,
            order_type=OrderType.LIMIT,
            limit_price=451.0,
        )

        temp_registry.create_envelope(env1)
        temp_registry.create_envelope(env2)

        # Update one to SUBMITTED
        temp_registry.update_status(
            order_id=env1.order_id,
            status=OrderStatus.SUBMITTED,
        )

        # Query by status
        pending = temp_registry.get_by_status(OrderStatus.PENDING)
        submitted = temp_registry.get_by_status(OrderStatus.SUBMITTED)

        assert len(pending) == 1
        assert pending[0].order_id == env2.order_id

        assert len(submitted) == 1
        assert submitted[0].order_id == env1.order_id

    def test_get_all_returns_recent_first(self, temp_registry, sample_instruction):
        """Test get_all returns orders in reverse chronological order."""
        # Create multiple orders
        envelopes = []
        for i in range(5):
            env = OrderEnvelope(
                idempotency_key=f"key{i}",
                instruction=sample_instruction,
                order_type=OrderType.LIMIT,
                limit_price=450.0 + i,
            )
            temp_registry.create_envelope(env)
            envelopes.append(env)

        # Get all orders
        all_orders = temp_registry.get_all(limit=10)

        assert len(all_orders) == 5

        # Most recent first
        assert all_orders[0].order_id == envelopes[-1].order_id
        assert all_orders[-1].order_id == envelopes[0].order_id

    def test_get_all_respects_limit(self, temp_registry, sample_instruction):
        """Test get_all respects limit parameter."""
        # Create 10 orders
        for i in range(10):
            env = OrderEnvelope(
                idempotency_key=f"key{i}",
                instruction=sample_instruction,
                order_type=OrderType.LIMIT,
                limit_price=450.0 + i,
            )
            temp_registry.create_envelope(env)

        # Get with limit
        orders = temp_registry.get_all(limit=3)
        assert len(orders) == 3


class TestRetryTracking:
    """Test retry count tracking."""

    def test_increment_retry(self, temp_registry, sample_envelope):
        """Test incrementing retry count."""
        envelope, _ = temp_registry.create_envelope(sample_envelope)

        # Initial retry count
        record = temp_registry.get_by_id(envelope.order_id)
        assert record.retry_count == 0

        # Increment
        new_count = temp_registry.increment_retry(envelope.order_id)
        assert new_count == 1

        record = temp_registry.get_by_id(envelope.order_id)
        assert record.retry_count == 1

        # Increment again
        new_count = temp_registry.increment_retry(envelope.order_id)
        assert new_count == 2


class TestDurability:
    """Test database durability."""

    def test_database_persists_across_connections(self, sample_envelope):
        """Test orders persist when registry is closed and reopened."""
        temp_dir = tempfile.mkdtemp()
        db_path = Path(temp_dir) / "test_persist.db"

        try:
            # Create registry, add order, close
            registry1 = ExecutionRegistry(db_path=db_path)
            envelope, _ = registry1.create_envelope(sample_envelope)
            order_id = envelope.order_id
            registry1.close()

            # Reopen registry, verify order exists
            registry2 = ExecutionRegistry(db_path=db_path)
            record = registry2.get_by_id(order_id)

            assert record is not None
            assert record.order_id == order_id
            assert record.status == OrderStatus.PENDING

            registry2.close()

        finally:
            # Cleanup
            import shutil
            if Path(temp_dir).exists():
                shutil.rmtree(temp_dir)


class TestConversion:
    """Test envelope <-> record conversion."""

    def test_envelope_to_record_conversion(self, temp_registry, sample_envelope):
        """Test converting envelope to record preserves data."""
        envelope, _ = temp_registry.create_envelope(sample_envelope)

        record = temp_registry.get_by_id(envelope.order_id)

        assert record.order_id == envelope.order_id
        assert record.idempotency_key == envelope.idempotency_key
        assert record.status == envelope.status
        assert record.order_type == envelope.order_type.value
        assert record.limit_price == envelope.limit_price

    def test_record_to_envelope_conversion(self, temp_registry, sample_envelope):
        """Test converting record back to envelope preserves data."""
        envelope1, _ = temp_registry.create_envelope(sample_envelope)

        record = temp_registry.get_by_id(envelope1.order_id)
        envelope2 = temp_registry._record_to_envelope(record)

        assert envelope2.order_id == envelope1.order_id
        assert envelope2.idempotency_key == envelope1.idempotency_key
        assert envelope2.status == envelope1.status
        assert envelope2.order_type == envelope1.order_type
        assert envelope2.limit_price == envelope1.limit_price
        assert envelope2.instruction.asset == envelope1.instruction.asset
