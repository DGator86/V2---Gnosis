# execution/registry.py

"""
Execution Registry - Phase 8

Durable, idempotent order persistence using DuckDB.

This registry guarantees:
1. Idempotency: Same order twice → deduplicated
2. Durability: Orders persisted before broker submission
3. Recoverability: System can restart without losing state
4. Auditability: Full history of status transitions
5. Query-ability: Fast lookups by ID, status, time range

Uses DuckDB for:
- ACID transactions
- Fast analytical queries
- Single-file portability
- No external dependencies
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import UUID

import duckdb

from execution.schemas import ExecutionRecord, OrderEnvelope, OrderStatus


class ExecutionRegistry:
    """
    Durable order registry with idempotency guarantees.

    All orders are persisted BEFORE submission to broker.
    Provides crash-safe recovery and full audit trail.
    """

    def __init__(self, db_path: str | Path = "execution_registry.db"):
        """
        Initialize registry.

        Args:
            db_path: Path to DuckDB database file
        """
        self.db_path = Path(db_path)
        self._conn: Optional[duckdb.DuckDBPyConnection] = None
        self._initialize_db()

    def _initialize_db(self) -> None:
        """Create database and tables if they don't exist."""
        self._conn = duckdb.connect(str(self.db_path))

        # Create orders table
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS orders (
                order_id VARCHAR PRIMARY KEY,
                idempotency_key VARCHAR UNIQUE NOT NULL,
                status VARCHAR NOT NULL,
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL,
                instruction_json VARCHAR NOT NULL,
                broker_order_id VARCHAR,
                order_type VARCHAR NOT NULL,
                limit_price DOUBLE,
                fill_price DOUBLE,
                filled_quantity INTEGER DEFAULT 0,
                error_message VARCHAR,
                retry_count INTEGER DEFAULT 0,
                status_history VARCHAR NOT NULL
            )
        """
        )

        # Create index on idempotency_key for fast duplicate detection
        self._conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_idempotency_key
            ON orders(idempotency_key)
        """
        )

        # Create index on status for fast status queries
        self._conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_status
            ON orders(status)
        """
        )

        self._conn.commit()

    def create_envelope(
        self, envelope: OrderEnvelope
    ) -> tuple[OrderEnvelope, bool]:
        """
        Create order envelope with idempotency check.

        Args:
            envelope: Order envelope to create

        Returns:
            Tuple of (envelope, is_new)
            - If new: (envelope, True)
            - If duplicate: (existing_envelope, False)
        """
        # Check if idempotency key already exists
        existing = self.get_by_idempotency_key(envelope.idempotency_key)

        if existing:
            # Duplicate order, return existing envelope
            return existing, False

        # New order, persist it
        record = self._envelope_to_record(envelope)
        self._insert_record(record)

        return envelope, True

    def update_status(
        self,
        order_id: UUID,
        status: OrderStatus,
        broker_order_id: Optional[str] = None,
        fill_price: Optional[float] = None,
        filled_quantity: Optional[int] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """
        Update order status and append to history.

        Args:
            order_id: Order ID
            status: New status
            broker_order_id: Broker order ID (if available)
            fill_price: Fill price (if filled)
            filled_quantity: Filled quantity (if filled)
            error_message: Error message (if error)
        """
        # Fetch current record
        record = self.get_by_id(order_id)
        if not record:
            raise ValueError(f"Order not found: {order_id}")

        # Append status transition to history
        record.status_history.append(
            {
                "timestamp": datetime.utcnow().isoformat(),
                "old_status": record.status.value,
                "new_status": status.value,
                "broker_order_id": broker_order_id,
                "fill_price": fill_price,
                "filled_quantity": filled_quantity,
                "error_message": error_message,
            }
        )

        # Update current state
        record.status = status
        record.updated_at = datetime.utcnow()

        if broker_order_id:
            record.broker_order_id = broker_order_id
        if fill_price is not None:
            record.fill_price = fill_price
        if filled_quantity is not None:
            record.filled_quantity = filled_quantity
        if error_message:
            record.error_message = error_message

        # Persist update
        self._update_record(record)

    def increment_retry(self, order_id: UUID) -> int:
        """
        Increment retry count for an order.

        Args:
            order_id: Order ID

        Returns:
            New retry count
        """
        self._conn.execute(
            """
            UPDATE orders
            SET retry_count = retry_count + 1,
                updated_at = ?
            WHERE order_id = ?
        """,
            [datetime.utcnow(), str(order_id)],
        )
        self._conn.commit()

        record = self.get_by_id(order_id)
        return record.retry_count if record else 0

    def get_by_id(self, order_id: UUID) -> Optional[ExecutionRecord]:
        """
        Get order by ID.

        Args:
            order_id: Order ID

        Returns:
            ExecutionRecord if found, None otherwise
        """
        result = self._conn.execute(
            """
            SELECT * FROM orders WHERE order_id = ?
        """,
            [str(order_id)],
        ).fetchone()

        if not result:
            return None

        return self._row_to_record(result)

    def get_by_idempotency_key(
        self, idempotency_key: str
    ) -> Optional[OrderEnvelope]:
        """
        Get order by idempotency key.

        Args:
            idempotency_key: Idempotency key

        Returns:
            OrderEnvelope if found, None otherwise
        """
        result = self._conn.execute(
            """
            SELECT * FROM orders WHERE idempotency_key = ?
        """,
            [idempotency_key],
        ).fetchone()

        if not result:
            return None

        record = self._row_to_record(result)
        return self._record_to_envelope(record)

    def get_by_status(self, status: OrderStatus) -> list[ExecutionRecord]:
        """
        Get all orders with given status.

        Args:
            status: Order status

        Returns:
            List of ExecutionRecords
        """
        results = self._conn.execute(
            """
            SELECT * FROM orders WHERE status = ?
            ORDER BY created_at DESC
        """,
            [status.value],
        ).fetchall()

        return [self._row_to_record(row) for row in results]

    def get_all(self, limit: int = 100) -> list[ExecutionRecord]:
        """
        Get all orders (most recent first).

        Args:
            limit: Max number of records to return

        Returns:
            List of ExecutionRecords
        """
        results = self._conn.execute(
            """
            SELECT * FROM orders
            ORDER BY created_at DESC
            LIMIT ?
        """,
            [limit],
        ).fetchall()

        return [self._row_to_record(row) for row in results]

    def close(self) -> None:
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    # Helper methods

    def _envelope_to_record(self, envelope: OrderEnvelope) -> ExecutionRecord:
        """Convert OrderEnvelope to ExecutionRecord."""
        return ExecutionRecord(
            order_id=envelope.order_id,
            idempotency_key=envelope.idempotency_key,
            status=envelope.status,
            created_at=envelope.created_at,
            updated_at=datetime.utcnow(),
            instruction_json=envelope.instruction.model_dump_json(),
            broker_order_id=envelope.broker_order_id,
            order_type=envelope.order_type.value,
            limit_price=envelope.limit_price,
            fill_price=envelope.fill_price,
            filled_quantity=envelope.filled_quantity,
            error_message=envelope.error_message,
            retry_count=envelope.retry_count,
            status_history=[
                {
                    "timestamp": envelope.created_at.isoformat(),
                    "status": envelope.status.value,
                    "reason": "created",
                }
            ],
        )

    def _record_to_envelope(self, record: ExecutionRecord) -> OrderEnvelope:
        """Convert ExecutionRecord to OrderEnvelope."""
        from agents.portfolio.schemas import OrderInstruction

        instruction = OrderInstruction.model_validate_json(record.instruction_json)

        # Find submission and fill timestamps from history
        submitted_at = None
        filled_at = None

        for event in record.status_history:
            if event.get("new_status") == "submitted":
                submitted_at = datetime.fromisoformat(event["timestamp"])
            if event.get("new_status") == "filled":
                filled_at = datetime.fromisoformat(event["timestamp"])

        return OrderEnvelope(
            order_id=record.order_id,
            idempotency_key=record.idempotency_key,
            created_at=record.created_at,
            submitted_at=submitted_at,
            filled_at=filled_at,
            status=record.status,
            retry_count=record.retry_count,
            instruction=instruction,
            broker_order_id=record.broker_order_id,
            order_type=OrderType(record.order_type),
            limit_price=record.limit_price,
            fill_price=record.fill_price,
            filled_quantity=record.filled_quantity,
            error_message=record.error_message,
        )

    def _insert_record(self, record: ExecutionRecord) -> None:
        """Insert new record into database."""
        self._conn.execute(
            """
            INSERT INTO orders (
                order_id, idempotency_key, status, created_at, updated_at,
                instruction_json, broker_order_id, order_type, limit_price,
                fill_price, filled_quantity, error_message, retry_count,
                status_history
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            [
                str(record.order_id),
                record.idempotency_key,
                record.status.value,
                record.created_at,
                record.updated_at,
                record.instruction_json,
                record.broker_order_id,
                record.order_type,
                record.limit_price,
                record.fill_price,
                record.filled_quantity,
                record.error_message,
                record.retry_count,
                json.dumps(record.status_history),
            ],
        )
        self._conn.commit()

    def _update_record(self, record: ExecutionRecord) -> None:
        """Update existing record in database."""
        self._conn.execute(
            """
            UPDATE orders
            SET status = ?,
                updated_at = ?,
                broker_order_id = ?,
                fill_price = ?,
                filled_quantity = ?,
                error_message = ?,
                retry_count = ?,
                status_history = ?
            WHERE order_id = ?
        """,
            [
                record.status.value,
                record.updated_at,
                record.broker_order_id,
                record.fill_price,
                record.filled_quantity,
                record.error_message,
                record.retry_count,
                json.dumps(record.status_history),
                str(record.order_id),
            ],
        )
        self._conn.commit()

    def _row_to_record(self, row: tuple) -> ExecutionRecord:
        """Convert database row to ExecutionRecord."""
        return ExecutionRecord(
            order_id=UUID(row[0]),
            idempotency_key=row[1],
            status=OrderStatus(row[2]),
            created_at=row[3],
            updated_at=row[4],
            instruction_json=row[5],
            broker_order_id=row[6],
            order_type=row[7],
            limit_price=row[8],
            fill_price=row[9],
            filled_quantity=row[10],
            error_message=row[11],
            retry_count=row[12],
            status_history=json.loads(row[13]),
        )


# Import OrderType here to avoid circular import
from execution.schemas import OrderType


def generate_idempotency_key(instruction: OrderInstruction) -> str:
    """
    Generate idempotency key from OrderInstruction.

    Uses hash of instruction content to detect duplicates.

    Args:
        instruction: Order instruction

    Returns:
        Idempotency key (hex string)
    """
    from agents.portfolio.schemas import OrderInstruction

    # Serialize instruction to dict, then JSON with sorted keys
    data = instruction.model_dump()
    content = json.dumps(data, sort_keys=True)

    # Hash content
    return hashlib.sha256(content.encode()).hexdigest()
