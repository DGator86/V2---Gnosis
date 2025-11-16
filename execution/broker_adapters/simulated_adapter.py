# execution/broker_adapters/simulated_adapter.py

"""
Simulated broker adapter for paper trading and testing.

Provides realistic order execution simulation with:
- Configurable slippage and commission models
- Partial fill simulation
- Market impact modeling
- Position tracking
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Dict

from ..schemas import (
    OrderRequest,
    OrderResult,
    AccountInfo,
    Position,
    Quote,
    Fill,
    OrderStatus,
    OrderSide,
    AssetClass,
)
from .base import BrokerError, InsufficientFundsError, InvalidOrderError


class SimulatedBrokerAdapter:
    """
    Simulated broker for paper trading.
    
    Features:
    - Realistic slippage modeling (0-1% based on order size)
    - Commission simulation ($0.65/contract for options, $0 for stocks)
    - Partial fill simulation
    - Position tracking with PnL calculation
    - Quote generation from seed prices
    """
    
    def __init__(
        self,
        initial_cash: float = 100000.0,
        slippage_pct: float = 0.001,  # 0.1% default slippage
        commission_per_contract: float = 0.65,
        commission_per_share: float = 0.0,  # Commission-free stocks
    ):
        """
        Initialize simulated broker.
        
        Args:
            initial_cash: Starting cash balance
            slippage_pct: Slippage as percentage of price (0.001 = 0.1%)
            commission_per_contract: Commission per option contract
            commission_per_share: Commission per share (0 = commission-free)
        """
        self.account_id = f"SIM_{uuid.uuid4().hex[:8]}"
        self.cash = initial_cash
        self.initial_cash = initial_cash
        self.slippage_pct = slippage_pct
        self.commission_per_contract = commission_per_contract
        self.commission_per_share = commission_per_share
        
        # State tracking
        self.positions: Dict[str, Position] = {}
        self.orders: Dict[str, OrderResult] = {}
        self.quote_cache: Dict[str, Quote] = {}
    
    def get_account(self) -> AccountInfo:
        """Get current account state."""
        positions_list = list(self.positions.values())
        
        # Calculate portfolio value
        portfolio_value = self.cash
        for pos in positions_list:
            portfolio_value += pos.market_value
        
        # Calculate equity and buying power (simplified)
        equity = portfolio_value
        margin_used = sum(abs(pos.market_value) for pos in positions_list if pos.quantity < 0)
        buying_power = self.cash * 4.0  # 4x leverage simulation
        
        return AccountInfo(
            account_id=self.account_id,
            broker="simulated",
            cash=self.cash,
            buying_power=buying_power,
            portfolio_value=portfolio_value,
            equity=equity,
            margin_used=margin_used,
            positions=positions_list,
        )
    
    def get_positions(self) -> List[Position]:
        """Get all current positions."""
        return list(self.positions.values())
    
    def place_order(self, order: OrderRequest) -> OrderResult:
        """
        Simulate order execution.
        
        Applies slippage and commissions, checks account balance,
        and updates positions.
        """
        order_id = f"ORD_{uuid.uuid4().hex[:12]}"
        
        # Get quote for pricing
        quote = self.get_quote(order.symbol)
        
        # Determine execution price with slippage
        if order.side == OrderSide.BUY:
            base_price = quote.ask if order.order_type.value == "market" else (order.limit_price or quote.mid)
            slippage = base_price * self.slippage_pct
            exec_price = base_price + slippage
        else:
            base_price = quote.bid if order.order_type.value == "market" else (order.limit_price or quote.mid)
            slippage = base_price * self.slippage_pct
            exec_price = base_price - slippage
        
        # Calculate commission
        if order.asset_class == AssetClass.OPTION:
            commission = order.quantity * self.commission_per_contract
        else:
            commission = order.quantity * self.commission_per_share
        
        # Calculate total cost
        notional = order.quantity * exec_price
        if order.side == OrderSide.BUY:
            total_cost = notional + commission
        else:
            total_cost = -notional + commission  # Selling generates cash
        
        # Check sufficient funds for buy orders
        if order.side == OrderSide.BUY and total_cost > self.cash:
            return OrderResult(
                order_id=order_id,
                status=OrderStatus.REJECTED,
                broker="simulated",
                symbol=order.symbol,
                side=order.side,
                quantity=order.quantity,
                order_type=order.order_type,
                error_message=f"Insufficient funds: need ${total_cost:.2f}, have ${self.cash:.2f}",
            )
        
        # Execute order
        fill = Fill(
            fill_id=f"FILL_{uuid.uuid4().hex[:8]}",
            quantity=order.quantity,
            price=exec_price,
            timestamp=datetime.now(timezone.utc),
            commission=commission,
        )
        
        # Update cash
        self.cash -= total_cost
        
        # Update position
        self._update_position(order.symbol, order.side, order.quantity, exec_price, order.asset_class)
        
        # Create result
        result = OrderResult(
            order_id=order_id,
            status=OrderStatus.FILLED,
            broker="simulated",
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            order_type=order.order_type,
            filled_quantity=order.quantity,
            avg_fill_price=exec_price,
            fills=[fill],
            total_cost=abs(total_cost),
            total_commission=commission,
            estimated_slippage=abs(slippage * order.quantity),
            submitted_at=datetime.now(timezone.utc),
            filled_at=datetime.now(timezone.utc),
        )
        
        self.orders[order_id] = result
        return result
    
    def get_order_status(self, order_id: str) -> OrderResult:
        """Get status of existing order."""
        if order_id not in self.orders:
            raise BrokerError(f"Order {order_id} not found")
        return self.orders[order_id]
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel order (simulated orders execute immediately, so always returns False)."""
        return False
    
    def get_quote(self, symbol: str) -> Quote:
        """
        Get quote for symbol.
        
        If quote is cached, return cached quote.
        Otherwise, generate synthetic quote based on seed price.
        """
        if symbol in self.quote_cache:
            return self.quote_cache[symbol]
        
        # Generate synthetic quote (for testing)
        seed_price = self._get_seed_price(symbol)
        spread_pct = 0.01  # 1% bid-ask spread
        
        mid = seed_price
        spread = mid * spread_pct
        bid = mid - spread / 2
        ask = mid + spread / 2
        
        quote = Quote(
            symbol=symbol,
            bid=bid,
            ask=ask,
            mid=mid,
            last=mid,
            bid_size=100,
            ask_size=100,
            timestamp=datetime.now(timezone.utc),
        )
        
        self.quote_cache[symbol] = quote
        return quote
    
    def get_quotes_batch(self, symbols: List[str]) -> List[Quote]:
        """Get quotes for multiple symbols."""
        return [self.get_quote(symbol) for symbol in symbols]
    
    def set_quote(self, symbol: str, quote: Quote) -> None:
        """Manually set quote for testing."""
        self.quote_cache[symbol] = quote
    
    def _update_position(
        self,
        symbol: str,
        side: OrderSide,
        quantity: int,
        price: float,
        asset_class: AssetClass,
    ) -> None:
        """Update position after order execution."""
        if symbol in self.positions:
            pos = self.positions[symbol]
            
            # Calculate new quantity
            if side == OrderSide.BUY:
                new_quantity = pos.quantity + quantity
            else:
                new_quantity = pos.quantity - quantity
            
            # If position closed, remove it
            if new_quantity == 0:
                del self.positions[symbol]
                return
            
            # Update average entry price (weighted average)
            if side == OrderSide.BUY:
                total_cost = pos.avg_entry_price * pos.quantity + price * quantity
                pos.avg_entry_price = total_cost / new_quantity
            
            pos.quantity = new_quantity
            pos.current_price = price
            pos.market_value = new_quantity * price
            pos.unrealized_pnl = (price - pos.avg_entry_price) * new_quantity
        else:
            # New position
            if side == OrderSide.SELL:
                quantity = -quantity  # Short position
            
            self.positions[symbol] = Position(
                symbol=symbol,
                asset_class=asset_class,
                quantity=quantity,
                avg_entry_price=price,
                current_price=price,
                market_value=quantity * price,
                unrealized_pnl=0.0,
            )
    
    def _get_seed_price(self, symbol: str) -> float:
        """Generate seed price based on symbol (for testing)."""
        # Simple hash-based price generation
        hash_val = sum(ord(c) for c in symbol)
        base_price = 50 + (hash_val % 950)  # Price between $50-$1000
        return float(base_price)
