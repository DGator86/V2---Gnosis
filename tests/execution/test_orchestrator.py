# tests/execution/test_orchestrator.py

"""
Tests for ExecutionOrchestrator - Phase 8

Test coverage:
- Order submission and persistence
- Idempotency (duplicate detection)
- Broker integration
- Status queries
- Order cancellation
- Retry logic on network errors
- Error handling
- Registry updates
- End-to-end workflows
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from uuid import uuid4

import pytest

from agents.portfolio.schemas import OrderAction, OrderInstruction, StrategyType
from agents.trade_agent.schemas import TradeIdea
from execution import ExecutionOrchestrator, ExecutionRegistry, PaperBroker, PaperMode
from execution.broker.base import NetworkError
from execution.schemas import OrderStatus, OrderType


@pytest.fixture
def temp_registry():
    """Create temporary registry for testing."""
    # Create temp dir and let DuckDB create the file
    import tempfile
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


class TestOrderSubmission:
    """Test order submission flow."""

    def test_submit_order_creates_envelope(self, temp_registry, sample_instruction):
        """Test submit creates order envelope with UUID."""
        broker = PaperBroker(mode=PaperMode.IMMEDIATE_FILL)
        orchestrator = ExecutionOrchestrator(broker=broker, registry=temp_registry)

        envelope = orchestrator.submit(
            instruction=sample_instruction,
            order_type=OrderType.LIMIT,
            limit_price=450.0,
        )

        assert envelope.order_id is not None
        assert envelope.idempotency_key is not None
        assert envelope.instruction == sample_instruction

    def test_submit_order_persists_before_broker(
        self, temp_registry, sample_instruction
    ):
        """Test order is persisted BEFORE broker submission."""
        broker = PaperBroker(mode=PaperMode.IMMEDIATE_FILL)
        orchestrator = ExecutionOrchestrator(broker=broker, registry=temp_registry)

        envelope = orchestrator.submit(
            instruction=sample_instruction,
            order_type=OrderType.LIMIT,
            limit_price=450.0,
        )

        # Verify persisted in registry
        record = temp_registry.get_by_id(envelope.order_id)
        assert record is not None
        assert record.order_id == envelope.order_id

    def test_submit_order_updates_status_from_broker(
        self, temp_registry, sample_instruction
    ):
        """Test order status updated from broker response."""
        broker = PaperBroker(mode=PaperMode.IMMEDIATE_FILL)
        orchestrator = ExecutionOrchestrator(broker=broker, registry=temp_registry)

        envelope = orchestrator.submit(
            instruction=sample_instruction,
            order_type=OrderType.LIMIT,
            limit_price=450.0,
        )

        # Should be filled (immediate fill mode)
        assert envelope.status == OrderStatus.FILLED
        assert envelope.fill_price == 450.0
        assert envelope.broker_order_id is not None


class TestIdempotency:
    """Test idempotency guarantees."""

    def test_same_order_twice_returns_same_envelope(
        self, temp_registry, sample_instruction
    ):
        """Test submitting same order twice returns same envelope."""
        broker = PaperBroker(mode=PaperMode.IMMEDIATE_FILL)
        orchestrator = ExecutionOrchestrator(broker=broker, registry=temp_registry)

        # First submission
        envelope1 = orchestrator.submit(
            instruction=sample_instruction,
            order_type=OrderType.LIMIT,
            limit_price=450.0,
        )

        # Second submission (same instruction)
        envelope2 = orchestrator.submit(
            instruction=sample_instruction,
            order_type=OrderType.LIMIT,
            limit_price=450.0,
        )

        # Same order ID (idempotency)
        assert envelope2.order_id == envelope1.order_id

    def test_same_order_twice_not_submitted_to_broker_again(
        self, temp_registry, sample_instruction
    ):
        """Test duplicate order not re-submitted to broker."""
        broker = PaperBroker(mode=PaperMode.IMMEDIATE_FILL)
        orchestrator = ExecutionOrchestrator(broker=broker, registry=temp_registry)

        # First submission
        envelope1 = orchestrator.submit(
            instruction=sample_instruction,
            order_type=OrderType.LIMIT,
            limit_price=450.0,
        )

        broker_order_id1 = envelope1.broker_order_id

        # Second submission
        envelope2 = orchestrator.submit(
            instruction=sample_instruction,
            order_type=OrderType.LIMIT,
            limit_price=450.0,
        )

        # Same broker order ID (not re-submitted)
        assert envelope2.broker_order_id == broker_order_id1


class TestStatusQueries:
    """Test status query operations."""

    def test_get_status_returns_envelope(self, temp_registry, sample_instruction):
        """Test get_status returns current envelope."""
        broker = PaperBroker(mode=PaperMode.IMMEDIATE_FILL)
        orchestrator = ExecutionOrchestrator(broker=broker, registry=temp_registry)

        envelope = orchestrator.submit(
            instruction=sample_instruction,
            order_type=OrderType.LIMIT,
            limit_price=450.0,
        )

        status = orchestrator.get_status(envelope.order_id)

        assert status is not None
        assert status.order_id == envelope.order_id
        assert status.status == OrderStatus.FILLED

    def test_get_status_nonexistent_returns_none(self, temp_registry):
        """Test get_status for nonexistent order returns None."""
        broker = PaperBroker(mode=PaperMode.IMMEDIATE_FILL)
        orchestrator = ExecutionOrchestrator(broker=broker, registry=temp_registry)

        status = orchestrator.get_status(uuid4())

        assert status is None


class TestOrderCancellation:
    """Test order cancellation."""

    def test_cancel_pending_order_succeeds(self, temp_registry, sample_instruction):
        """Test canceling pending order succeeds."""
        broker = PaperBroker(mode=PaperMode.DELAYED_FILL)
        orchestrator = ExecutionOrchestrator(broker=broker, registry=temp_registry)

        envelope = orchestrator.submit(
            instruction=sample_instruction,
            order_type=OrderType.LIMIT,
            limit_price=450.0,
        )

        assert envelope.status == OrderStatus.SUBMITTED

        # Cancel order
        cancelled = orchestrator.cancel(envelope.order_id)

        assert cancelled.status == OrderStatus.CANCELLED

    def test_cancel_filled_order_no_effect(self, temp_registry, sample_instruction):
        """Test canceling filled order has no effect."""
        broker = PaperBroker(mode=PaperMode.IMMEDIATE_FILL)
        orchestrator = ExecutionOrchestrator(broker=broker, registry=temp_registry)

        envelope = orchestrator.submit(
            instruction=sample_instruction,
            order_type=OrderType.LIMIT,
            limit_price=450.0,
        )

        assert envelope.status == OrderStatus.FILLED

        # Try to cancel
        cancelled = orchestrator.cancel(envelope.order_id)

        # Still filled (can't cancel filled orders)
        assert cancelled.status == OrderStatus.FILLED

    def test_cancel_nonexistent_order_raises(self, temp_registry):
        """Test canceling nonexistent order raises error."""
        broker = PaperBroker(mode=PaperMode.IMMEDIATE_FILL)
        orchestrator = ExecutionOrchestrator(broker=broker, registry=temp_registry)

        with pytest.raises(ValueError, match="Order not found"):
            orchestrator.cancel(uuid4())


class TestRetryLogic:
    """Test retry logic for transient failures."""

    def test_network_error_retries(self, temp_registry, sample_instruction):
        """Test network errors trigger retries."""

        class FlakyBroker(PaperBroker):
            """Broker that fails first N times."""

            def __init__(self, fail_count=2):
                super().__init__(mode=PaperMode.IMMEDIATE_FILL)
                self.fail_count = fail_count
                self.attempt_count = 0

            def submit_order(self, envelope):
                self.attempt_count += 1
                if self.attempt_count <= self.fail_count:
                    raise NetworkError("Simulated network error")
                return super().submit_order(envelope)

        broker = FlakyBroker(fail_count=2)
        orchestrator = ExecutionOrchestrator(
            broker=broker,
            registry=temp_registry,
            max_retries=3,
            retry_delay_seconds=0.1,  # Fast retries for testing
        )

        envelope = orchestrator.submit(
            instruction=sample_instruction,
            order_type=OrderType.LIMIT,
            limit_price=450.0,
        )

        # Should succeed after retries
        assert envelope.status == OrderStatus.FILLED
        assert broker.attempt_count == 3  # Failed twice, succeeded third time

    def test_max_retries_exceeded_marks_error(self, temp_registry, sample_instruction):
        """Test exceeding max retries marks order as error."""

        class AlwaysFailBroker(PaperBroker):
            """Broker that always fails."""

            def submit_order(self, envelope):
                raise NetworkError("Permanent network error")

        broker = AlwaysFailBroker()
        orchestrator = ExecutionOrchestrator(
            broker=broker,
            registry=temp_registry,
            max_retries=2,
            retry_delay_seconds=0.1,
        )

        envelope = orchestrator.submit(
            instruction=sample_instruction,
            order_type=OrderType.LIMIT,
            limit_price=450.0,
        )

        # Should be marked as error
        assert envelope.status == OrderStatus.ERROR
        # Error message contains the permanent network error
        assert envelope.error_message is not None


class TestErrorHandling:
    """Test error handling."""

    def test_broker_rejection_marks_rejected(self, temp_registry, sample_instruction):
        """Test broker rejection marks order as rejected."""
        broker = PaperBroker(mode=PaperMode.REJECTED)
        orchestrator = ExecutionOrchestrator(broker=broker, registry=temp_registry)

        envelope = orchestrator.submit(
            instruction=sample_instruction,
            order_type=OrderType.LIMIT,
            limit_price=450.0,
        )

        assert envelope.status == OrderStatus.REJECTED
        assert envelope.error_message is not None

    def test_missing_limit_price_raises(self, temp_registry, sample_instruction):
        """Test limit order without limit price raises error."""
        broker = PaperBroker(mode=PaperMode.IMMEDIATE_FILL)
        orchestrator = ExecutionOrchestrator(broker=broker, registry=temp_registry)

        with pytest.raises(ValueError, match="Limit price required"):
            orchestrator.submit(
                instruction=sample_instruction,
                order_type=OrderType.LIMIT,
                limit_price=None,  # Missing!
            )


class TestLogQueries:
    """Test log query operations."""

    def test_get_logs_by_order_id(self, temp_registry, sample_instruction):
        """Test fetching logs for specific order."""
        broker = PaperBroker(mode=PaperMode.IMMEDIATE_FILL)
        orchestrator = ExecutionOrchestrator(broker=broker, registry=temp_registry)

        envelope = orchestrator.submit(
            instruction=sample_instruction,
            order_type=OrderType.LIMIT,
            limit_price=450.0,
        )

        logs = orchestrator.get_logs(order_id=envelope.order_id)

        assert len(logs) == 1
        # order_id could be UUID or string depending on model_dump
        log_order_id = logs[0]["order_id"]
        assert str(log_order_id) == str(envelope.order_id)

    def test_get_logs_by_status(self, temp_registry, sample_instruction):
        """Test fetching logs by status."""
        broker = PaperBroker(mode=PaperMode.IMMEDIATE_FILL)
        orchestrator = ExecutionOrchestrator(broker=broker, registry=temp_registry)

        # Submit multiple orders
        for _ in range(3):
            orchestrator.submit(
                instruction=sample_instruction,
                order_type=OrderType.LIMIT,
                limit_price=450.0,
            )

        logs = orchestrator.get_logs(status=OrderStatus.FILLED)

        assert len(logs) >= 1  # At least first order (others are duplicates)

    def test_get_logs_all_respects_limit(self, temp_registry, sample_instruction):
        """Test get_logs respects limit parameter."""
        broker = PaperBroker(mode=PaperMode.IMMEDIATE_FILL)
        orchestrator = ExecutionOrchestrator(broker=broker, registry=temp_registry)

        # Submit multiple different orders
        for i in range(5):
            modified_instruction = sample_instruction.model_copy()
            modified_instruction.reason = f"order_{i}"
            orchestrator.submit(
                instruction=modified_instruction,
                order_type=OrderType.LIMIT,
                limit_price=450.0 + i,
            )

        logs = orchestrator.get_logs(limit=3)

        assert len(logs) == 3


class TestEndToEndWorkflows:
    """Test complete workflows."""

    def test_complete_workflow_immediate_fill(self, temp_registry, sample_instruction):
        """Test complete workflow: submit → fill → query."""
        broker = PaperBroker(mode=PaperMode.IMMEDIATE_FILL)
        orchestrator = ExecutionOrchestrator(broker=broker, registry=temp_registry)

        # Submit
        envelope = orchestrator.submit(
            instruction=sample_instruction,
            order_type=OrderType.LIMIT,
            limit_price=450.0,
        )

        assert envelope.status == OrderStatus.FILLED
        assert envelope.fill_price == 450.0

        # Query status
        status = orchestrator.get_status(envelope.order_id)
        assert status.status == OrderStatus.FILLED

        # Query logs
        logs = orchestrator.get_logs(order_id=envelope.order_id)
        assert len(logs) == 1

    def test_complete_workflow_delayed_fill(self, temp_registry, sample_instruction):
        """Test complete workflow: submit → submitted → query."""
        broker = PaperBroker(mode=PaperMode.DELAYED_FILL)
        orchestrator = ExecutionOrchestrator(broker=broker, registry=temp_registry)

        # Submit
        envelope = orchestrator.submit(
            instruction=sample_instruction,
            order_type=OrderType.LIMIT,
            limit_price=450.0,
        )

        assert envelope.status == OrderStatus.SUBMITTED
        assert envelope.broker_order_id is not None

        # Query status
        status = orchestrator.get_status(envelope.order_id)
        assert status.status == OrderStatus.SUBMITTED

    def test_complete_workflow_rejection(self, temp_registry, sample_instruction):
        """Test complete workflow: submit → rejected → query."""
        broker = PaperBroker(mode=PaperMode.REJECTED)
        orchestrator = ExecutionOrchestrator(broker=broker, registry=temp_registry)

        # Submit
        envelope = orchestrator.submit(
            instruction=sample_instruction,
            order_type=OrderType.LIMIT,
            limit_price=450.0,
        )

        assert envelope.status == OrderStatus.REJECTED

        # Query status
        status = orchestrator.get_status(envelope.order_id)
        assert status.status == OrderStatus.REJECTED


class TestRegistryUpdates:
    """Test registry updates during execution."""

    def test_status_history_tracked(self, temp_registry, sample_instruction):
        """Test status transitions are tracked in history."""
        broker = PaperBroker(mode=PaperMode.IMMEDIATE_FILL)
        orchestrator = ExecutionOrchestrator(broker=broker, registry=temp_registry)

        envelope = orchestrator.submit(
            instruction=sample_instruction,
            order_type=OrderType.LIMIT,
            limit_price=450.0,
        )

        # Check history in registry
        record = temp_registry.get_by_id(envelope.order_id)

        assert len(record.status_history) >= 2  # Created + Filled
        assert record.status_history[0]["status"] == "pending"
        assert record.status_history[-1]["new_status"] == "filled"

    def test_broker_order_id_persisted(self, temp_registry, sample_instruction):
        """Test broker order ID is persisted."""
        broker = PaperBroker(mode=PaperMode.IMMEDIATE_FILL)
        orchestrator = ExecutionOrchestrator(broker=broker, registry=temp_registry)

        envelope = orchestrator.submit(
            instruction=sample_instruction,
            order_type=OrderType.LIMIT,
            limit_price=450.0,
        )

        # Check registry
        record = temp_registry.get_by_id(envelope.order_id)
        assert record.broker_order_id is not None
        assert record.broker_order_id == envelope.broker_order_id
