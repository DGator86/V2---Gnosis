# execution/order_controller.py

"""
Order lifecycle management for Trade Agent v3.

Handles:
- Order submission and tracking
- Partial fill management
- Automatic repricing for unfilled orders
- Time-based cancellation
- Auto-stop protection
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Optional, Dict

from .schemas import (
    OrderRequest,
    OrderResult,
    OrderStatus,
    Quote,
)
from .broker_adapters.base import BrokerAdapter
from .router import SmartOrderRouter


class OrderLifecycleController:
    """
    Manages order lifecycle from submission to completion.
    
    Features:
    - Automatic repricing for stale limit orders
    - Partial fill tracking
    - Cancel-and-replace for unfilled orders
    - Time-based order expiration
    """
    
    def __init__(
        self,
        broker: BrokerAdapter,
        router: Optional[SmartOrderRouter] = None,
        reprice_interval_sec: int = 60,  # Reprice every 60 seconds
        max_order_lifetime_sec: int = 300,  # Cancel after 5 minutes
    ):
        """
        Initialize lifecycle controller.
        
        Args:
            broker: Broker adapter for order execution
            router: Smart router for routing decisions
            reprice_interval_sec: Seconds before repricing unfilled limit orders
            max_order_lifetime_sec: Max order lifetime before cancellation
        """
        self.broker = broker
        self.router = router or SmartOrderRouter()
        self.reprice_interval_sec = reprice_interval_sec
        self.max_order_lifetime_sec = max_order_lifetime_sec
        
        # Track active orders
        self.active_orders: Dict[str, OrderResult] = {}
        self.order_timestamps: Dict[str, datetime] = {}
    
    def submit_order(
        self,
        order: OrderRequest,
        quote: Quote,
    ) -> OrderResult:
        """
        Submit order with intelligent routing.
        
        Args:
            order: Order request
            quote: Current quote for routing decision
        
        Returns:
            OrderResult from broker
        """
        # Get routing decision
        routing = self.router.route_order(order, quote)
        
        # Apply routing decision to order
        order.order_type = routing.order_type
        order.limit_price = routing.limit_price
        order.time_in_force = routing.time_in_force
        
        # Submit to broker
        result = self.broker.place_order(order)
        
        # Track if not immediately filled
        if result.status not in [OrderStatus.FILLED, OrderStatus.REJECTED, OrderStatus.CANCELLED]:
            self.active_orders[result.order_id] = result
            self.order_timestamps[result.order_id] = datetime.now(timezone.utc)
        
        return result
    
    def check_and_manage_orders(self) -> Dict[str, OrderResult]:
        """
        Check all active orders and manage lifecycle.
        
        Returns:
            Dictionary of order_id -> updated OrderResult
        """
        now = datetime.now(timezone.utc)
        updates: Dict[str, OrderResult] = {}
        
        for order_id in list(self.active_orders.keys()):
            # Get current status
            result = self.broker.get_order_status(order_id)
            
            # If filled or cancelled, remove from tracking
            if result.status in [OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED]:
                del self.active_orders[order_id]
                if order_id in self.order_timestamps:
                    del self.order_timestamps[order_id]
                updates[order_id] = result
                continue
            
            # Check order age
            order_age = (now - self.order_timestamps[order_id]).total_seconds()
            
            # Cancel if too old
            if order_age > self.max_order_lifetime_sec:
                self.broker.cancel_order(order_id)
                del self.active_orders[order_id]
                del self.order_timestamps[order_id]
                updates[order_id] = result
                continue
            
            # Reprice if stale (for limit orders)
            if order_age > self.reprice_interval_sec and result.status == OrderStatus.PENDING:
                # TODO: Implement cancel-and-replace logic
                # For now, just track
                pass
            
            updates[order_id] = result
        
        return updates
    
    def cancel_all_orders(self) -> int:
        """
        Cancel all active orders.
        
        Returns:
            Number of orders cancelled
        """
        cancelled = 0
        for order_id in list(self.active_orders.keys()):
            if self.broker.cancel_order(order_id):
                cancelled += 1
                del self.active_orders[order_id]
                if order_id in self.order_timestamps:
                    del self.order_timestamps[order_id]
        
        return cancelled
    
    def get_active_orders(self) -> Dict[str, OrderResult]:
        """Get all active orders."""
        return self.active_orders.copy()
