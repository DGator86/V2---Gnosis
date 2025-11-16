# execution/orchestrator.py

"""
Execution Orchestrator v1.0 - Phase 8

Central coordination layer for order execution.

This orchestrator:
1. Converts OrderInstruction → OrderEnvelope
2. Persists envelope BEFORE broker submission (crash-safe)
3. Submits order to broker
4. Updates registry with broker response
5. Retries on transient failures
6. Enforces idempotency
7. Provides status queries
8. Enables audit trail and replay

This is the ONLY layer that talks to brokers.
All other code talks to this orchestrator.
"""

from __future__ import annotations

import logging
import time
from typing import Optional
from uuid import UUID

from execution.broker.base import AbstractBrokerAdapter, NetworkError
from execution.registry import ExecutionRegistry, generate_idempotency_key
from execution.schemas import BrokerResponse, OrderEnvelope, OrderStatus, OrderType
from agents.portfolio.schemas import OrderInstruction

logger = logging.getLogger(__name__)


class ExecutionOrchestrator:
    """
    Execution orchestration layer.

    Provides crash-safe, idempotent, auditable order execution.
    """

    def __init__(
        self,
        broker: AbstractBrokerAdapter,
        registry: Optional[ExecutionRegistry] = None,
        max_retries: int = 3,
        retry_delay_seconds: float = 1.0,
    ):
        """
        Initialize orchestrator.

        Args:
            broker: Broker adapter implementation
            registry: Execution registry (creates default if None)
            max_retries: Max retry attempts for transient failures
            retry_delay_seconds: Delay between retries
        """
        self.broker = broker
        self.registry = registry or ExecutionRegistry()
        self.max_retries = max_retries
        self.retry_delay_seconds = retry_delay_seconds

    def submit(
        self,
        instruction: OrderInstruction,
        order_type: OrderType = OrderType.LIMIT,
        limit_price: Optional[float] = None,
    ) -> OrderEnvelope:
        """
        Submit order for execution.

        This is the main entry point. It:
        1. Creates OrderEnvelope with idempotency key
        2. Checks registry for duplicates (idempotency)
        3. Persists envelope BEFORE broker submission
        4. Submits to broker
        5. Updates registry with broker response

        Args:
            instruction: Order instruction from Portfolio Manager
            order_type: Broker order type (market, limit, etc.)
            limit_price: Limit price (required for limit orders)

        Returns:
            OrderEnvelope with current status

        Raises:
            ValueError: If limit_price missing for limit order
        """
        # Validate limit price for limit orders
        if order_type == OrderType.LIMIT and limit_price is None:
            raise ValueError("Limit price required for limit orders")

        # Generate idempotency key
        idempotency_key = generate_idempotency_key(instruction)

        # Create envelope
        envelope = OrderEnvelope(
            idempotency_key=idempotency_key,
            instruction=instruction,
            order_type=order_type,
            limit_price=limit_price,
            status=OrderStatus.PENDING,
        )

        # Persist envelope (crash-safe)
        envelope, is_new = self.registry.create_envelope(envelope)

        if not is_new:
            # Duplicate order detected via idempotency key
            logger.info(
                f"Duplicate order detected: {envelope.order_id} "
                f"(idempotency_key={idempotency_key})"
            )
            return envelope

        logger.info(
            f"Created new order: {envelope.order_id} "
            f"(asset={instruction.asset}, "
            f"strategy={instruction.strategy_type}, "
            f"size={instruction.size_delta})"
        )

        # Submit to broker with retries
        response = self._submit_with_retry(envelope)

        # Update registry with broker response
        self._update_from_response(envelope, response)

        # Reload envelope from registry to get updated state
        updated_envelope = self.registry.get_by_id(envelope.order_id)
        if updated_envelope:
            envelope = self.registry._record_to_envelope(updated_envelope)

        return envelope

    def get_status(self, order_id: UUID) -> Optional[OrderEnvelope]:
        """
        Get current status of an order.

        Args:
            order_id: Order ID

        Returns:
            OrderEnvelope if found, None otherwise
        """
        record = self.registry.get_by_id(order_id)
        if not record:
            return None

        return self.registry._record_to_envelope(record)

    def cancel(self, order_id: UUID) -> OrderEnvelope:
        """
        Cancel a pending order.

        Args:
            order_id: Order ID

        Returns:
            OrderEnvelope with updated status

        Raises:
            ValueError: If order not found
        """
        # Get current envelope
        envelope = self.get_status(order_id)
        if not envelope:
            raise ValueError(f"Order not found: {order_id}")

        # Can only cancel pending/submitted orders
        if envelope.status not in [OrderStatus.PENDING, OrderStatus.SUBMITTED]:
            logger.warning(
                f"Cannot cancel order {order_id}: "
                f"status is {envelope.status}"
            )
            return envelope

        # Cancel via broker
        if envelope.broker_order_id:
            response = self.broker.cancel_order(envelope.broker_order_id)
            self._update_from_response(envelope, response)
        else:
            # Order not yet submitted to broker, just update status
            self.registry.update_status(
                order_id=order_id,
                status=OrderStatus.CANCELLED,
            )

        # Reload envelope
        updated_envelope = self.get_status(order_id)
        return updated_envelope or envelope

    def get_logs(
        self,
        order_id: Optional[UUID] = None,
        status: Optional[OrderStatus] = None,
        limit: int = 100,
    ) -> list[dict]:
        """
        Get execution logs.

        Args:
            order_id: Filter by order ID
            status: Filter by status
            limit: Max number of records

        Returns:
            List of order records as dicts
        """
        if order_id:
            record = self.registry.get_by_id(order_id)
            return [record.model_dump()] if record else []

        elif status:
            records = self.registry.get_by_status(status)
            return [r.model_dump() for r in records[:limit]]

        else:
            records = self.registry.get_all(limit=limit)
            return [r.model_dump() for r in records]

    def close(self) -> None:
        """Close orchestrator and cleanup resources."""
        self.registry.close()

    # Private helper methods

    def _submit_with_retry(self, envelope: OrderEnvelope) -> BrokerResponse:
        """
        Submit order to broker with retry logic.

        Args:
            envelope: Order envelope

        Returns:
            BrokerResponse from broker

        Retries on NetworkError up to max_retries times.
        """
        last_error = None

        for attempt in range(self.max_retries):
            try:
                # Submit to broker
                response = self.broker.submit_order(envelope)

                logger.info(
                    f"Order {envelope.order_id} submitted to broker: "
                    f"broker_order_id={response.broker_order_id}, "
                    f"status={response.status}"
                )

                return response

            except NetworkError as e:
                last_error = e
                logger.warning(
                    f"Network error submitting order {envelope.order_id} "
                    f"(attempt {attempt + 1}/{self.max_retries}): {e}"
                )

                # Increment retry count in registry
                self.registry.increment_retry(envelope.order_id)

                # Wait before retry
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay_seconds * (attempt + 1))

            except Exception as e:
                # Non-retryable error
                logger.error(
                    f"Error submitting order {envelope.order_id}: {e}"
                )

                # Update status to error
                self.registry.update_status(
                    order_id=envelope.order_id,
                    status=OrderStatus.ERROR,
                    error_message=str(e),
                )

                return BrokerResponse(
                    success=False,
                    status=OrderStatus.ERROR,
                    error_code="SUBMISSION_ERROR",
                    error_message=str(e),
                )

        # Max retries exceeded
        logger.error(
            f"Max retries exceeded for order {envelope.order_id}: {last_error}"
        )

        self.registry.update_status(
            order_id=envelope.order_id,
            status=OrderStatus.ERROR,
            error_message=f"Max retries exceeded: {last_error}",
        )

        return BrokerResponse(
            success=False,
            status=OrderStatus.ERROR,
            error_code="MAX_RETRIES_EXCEEDED",
            error_message=str(last_error),
        )

    def _update_from_response(
        self, envelope: OrderEnvelope, response: BrokerResponse
    ) -> None:
        """
        Update registry from broker response.

        Args:
            envelope: Order envelope
            response: Broker response
        """
        self.registry.update_status(
            order_id=envelope.order_id,
            status=response.status,
            broker_order_id=response.broker_order_id,
            fill_price=response.fill_price,
            filled_quantity=response.filled_quantity,
            error_message=response.error_message,
        )

        logger.info(
            f"Updated order {envelope.order_id}: "
            f"status={response.status}, "
            f"broker_order_id={response.broker_order_id}"
        )
