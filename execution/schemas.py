# execution/schemas.py

"""
Execution Layer Schemas - Phase 8

Defines the data structures for execution orchestration:
- OrderEnvelope: Wraps OrderInstruction with metadata for durability
- ExecutionRecord: Persisted state in registry
- BrokerResponse: Response from broker adapter
- BrokerStatus: Status enumeration

All schemas use Pydantic v2 for validation.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from agents.portfolio.schemas import OrderInstruction


class OrderStatus(str, Enum):
    """Order lifecycle states."""

    PENDING = "pending"  # Created, not yet submitted
    SUBMITTED = "submitted"  # Sent to broker
    FILLED = "filled"  # Completely filled
    PARTIALLY_FILLED = "partially_filled"  # Partial fill
    CANCELLED = "cancelled"  # User/system cancelled
    REJECTED = "rejected"  # Broker rejected
    ERROR = "error"  # System error


class OrderType(str, Enum):
    """Broker order types."""

    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class OrderEnvelope(BaseModel):
    """
    Wraps OrderInstruction with execution metadata.

    This is the durable unit that gets persisted BEFORE
    submission to broker. Contains all information needed
    for idempotency, recovery, and audit trail.
    """

    # Identity
    order_id: UUID = Field(
        default_factory=uuid4, description="UUIDv4 for this envelope"
    )
    idempotency_key: str = Field(
        ..., description="Hash of OrderInstruction for deduplication"
    )

    # Timing
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Envelope creation timestamp"
    )
    submitted_at: Optional[datetime] = Field(
        None, description="Broker submission timestamp"
    )
    filled_at: Optional[datetime] = Field(None, description="Fill completion timestamp")

    # Status
    status: OrderStatus = Field(
        default=OrderStatus.PENDING, description="Current order status"
    )
    retry_count: int = Field(default=0, ge=0, description="Number of retry attempts")

    # Core instruction
    instruction: OrderInstruction = Field(..., description="Original order instruction")

    # Broker details
    broker_order_id: Optional[str] = Field(
        None, description="Broker-assigned order ID"
    )
    order_type: OrderType = Field(
        default=OrderType.LIMIT, description="Broker order type"
    )
    limit_price: Optional[float] = Field(
        None, ge=0.0, description="Limit price (if applicable)"
    )

    # Execution details
    fill_price: Optional[float] = Field(None, ge=0.0, description="Actual fill price")
    filled_quantity: int = Field(
        default=0, ge=0, description="Number of contracts/shares filled"
    )

    # Error tracking
    error_message: Optional[str] = Field(None, description="Error details if any")

    class Config:
        frozen = False  # Allow updates for status tracking


class ExecutionRecord(BaseModel):
    """
    Persisted record in ExecutionRegistry.

    This is what gets stored in DuckDB. Contains full
    history of status transitions for audit trail.
    """

    order_id: UUID = Field(..., description="Order envelope ID")
    idempotency_key: str = Field(..., description="Deduplication key")

    # Current state
    status: OrderStatus = Field(..., description="Current status")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, description="Last update timestamp"
    )

    # Instruction (serialized as JSON)
    instruction_json: str = Field(..., description="OrderInstruction as JSON")

    # Broker details
    broker_order_id: Optional[str] = Field(None, description="Broker order ID")
    order_type: str = Field(..., description="Order type (market, limit, etc.)")
    limit_price: Optional[float] = Field(None, description="Limit price")

    # Execution details
    fill_price: Optional[float] = Field(None, description="Fill price")
    filled_quantity: int = Field(default=0, description="Filled quantity")

    # Error tracking
    error_message: Optional[str] = Field(None, description="Error message")
    retry_count: int = Field(default=0, description="Retry attempts")

    # History tracking (append-only log)
    status_history: list[dict] = Field(
        default_factory=list, description="Status transition log"
    )


class BrokerResponse(BaseModel):
    """
    Response from broker adapter after order submission.

    Standardized across all broker implementations.
    """

    success: bool = Field(..., description="Whether submission succeeded")
    broker_order_id: Optional[str] = Field(None, description="Broker-assigned ID")
    status: OrderStatus = Field(..., description="Order status")

    # Execution details (if filled immediately)
    fill_price: Optional[float] = Field(None, ge=0.0, description="Fill price")
    filled_quantity: int = Field(default=0, ge=0, description="Filled quantity")

    # Timing
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Response timestamp"
    )

    # Error details (if failed)
    error_code: Optional[str] = Field(None, description="Broker error code")
    error_message: Optional[str] = Field(None, description="Error description")

    # Additional metadata
    metadata: dict = Field(
        default_factory=dict, description="Broker-specific metadata"
    )


class BrokerStatus(BaseModel):
    """
    Status query response from broker.

    Used to check current state of an order.
    """

    broker_order_id: str = Field(..., description="Broker order ID")
    status: OrderStatus = Field(..., description="Current status")

    # Execution details
    fill_price: Optional[float] = Field(None, description="Fill price")
    filled_quantity: int = Field(default=0, description="Filled quantity")
    remaining_quantity: int = Field(default=0, description="Remaining quantity")

    # Timing
    submitted_at: Optional[datetime] = Field(None, description="Submission time")
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, description="Last update time"
    )

    # Additional info
    metadata: dict = Field(default_factory=dict, description="Broker metadata")
