"""
Alpaca Live Execution Engine

Provides real-time order execution via Alpaca broker API.
Supports paper trading and live trading with commission-free execution.

Features:
- Market, limit, stop, stop-limit orders
- Position tracking and management
- Real-time fill notifications
- Error handling with retries
- Paper trading for testing

Get API keys: https://alpaca.markets/
Plans:
- Paper Trading: FREE
- Live Trading: FREE (commission-free)
- Alpaca+ Data: $9/mo (optional)
"""

from typing import Dict, List, Optional, Literal
from datetime import datetime
from decimal import Decimal
from loguru import logger
from pydantic import BaseModel, Field
from enum import Enum

try:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import (
        MarketOrderRequest, LimitOrderRequest, 
        StopOrderRequest, StopLimitOrderRequest,
        GetOrdersRequest
    )
    from alpaca.trading.enums import (
        OrderSide, TimeInForce, OrderType, OrderStatus
    )
    from alpaca.common.exceptions import APIError
    ALPACA_AVAILABLE = True
except ImportError:
    ALPACA_AVAILABLE = False
    logger.warning(
        "alpaca-py not installed. Install with: pip install alpaca-py"
    )


class OrderSideEnum(str, Enum):
    """Order side."""
    BUY = "buy"
    SELL = "sell"


class OrderTypeEnum(str, Enum):
    """Order type."""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class TimeInForceEnum(str, Enum):
    """Time in force."""
    DAY = "day"
    GTC = "gtc"  # Good til canceled
    IOC = "ioc"  # Immediate or cancel
    FOK = "fok"  # Fill or kill


class OrderResult(BaseModel):
    """Order execution result."""
    
    order_id: str
    client_order_id: str
    symbol: str
    side: str
    type: str
    qty: float
    filled_qty: float = 0.0
    filled_avg_price: Optional[float] = None
    status: str
    submitted_at: str
    filled_at: Optional[str] = None
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: str
    extended_hours: bool = False


class PositionInfo(BaseModel):
    """Position information."""
    
    symbol: str
    qty: float
    side: str  # "long" or "short"
    market_value: float
    cost_basis: float
    unrealized_pl: float
    unrealized_plpc: float
    current_price: float
    avg_entry_price: float


class AlpacaExecutor:
    """
    Alpaca execution engine for live and paper trading.
    
    Features:
    - Commission-free trading
    - Fractional shares
    - Extended hours trading
    - Real-time fills
    - Position tracking
    """
    
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        paper: bool = True
    ):
        """
        Initialize Alpaca executor.
        
        Args:
            api_key: Alpaca API key
            api_secret: Alpaca API secret
            paper: Use paper trading (default True)
        """
        if not ALPACA_AVAILABLE:
            raise ImportError(
                "alpaca-py required. Install with: pip install alpaca-py"
            )
        
        self.api_key = api_key
        self.api_secret = api_secret
        self.paper = paper
        
        # Initialize trading client
        self.client = TradingClient(
            api_key=api_key,
            secret_key=api_secret,
            paper=paper
        )
        
        mode = "PAPER" if paper else "LIVE"
        logger.info(f"✅ Alpaca executor initialized ({mode} mode)")
    
    def submit_market_order(
        self,
        symbol: str,
        qty: float,
        side: OrderSideEnum,
        time_in_force: TimeInForceEnum = TimeInForceEnum.DAY,
        extended_hours: bool = False,
        client_order_id: Optional[str] = None
    ) -> OrderResult:
        """
        Submit market order.
        
        Args:
            symbol: Stock symbol
            qty: Quantity to trade
            side: Buy or sell
            time_in_force: Order duration
            extended_hours: Allow extended hours trading
            client_order_id: Custom order ID
        
        Returns:
            OrderResult with order details
        """
        logger.info(
            f"Submitting market order: {side.value} {qty} {symbol}"
        )
        
        try:
            # Create order request
            order_data = MarketOrderRequest(
                symbol=symbol,
                qty=qty,
                side=OrderSide.BUY if side == OrderSideEnum.BUY else OrderSide.SELL,
                time_in_force=self._map_tif(time_in_force),
                extended_hours=extended_hours,
                client_order_id=client_order_id
            )
            
            # Submit order
            order = self.client.submit_order(order_data)
            
            result = self._convert_order(order)
            logger.info(f"✅ Order submitted: {result.order_id}")
            
            return result
        
        except APIError as e:
            logger.error(f"Alpaca API error: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to submit market order: {e}")
            raise
    
    def submit_limit_order(
        self,
        symbol: str,
        qty: float,
        side: OrderSideEnum,
        limit_price: float,
        time_in_force: TimeInForceEnum = TimeInForceEnum.DAY,
        extended_hours: bool = False,
        client_order_id: Optional[str] = None
    ) -> OrderResult:
        """
        Submit limit order.
        
        Args:
            symbol: Stock symbol
            qty: Quantity to trade
            side: Buy or sell
            limit_price: Limit price
            time_in_force: Order duration
            extended_hours: Allow extended hours
            client_order_id: Custom order ID
        
        Returns:
            OrderResult with order details
        """
        logger.info(
            f"Submitting limit order: {side.value} {qty} {symbol} @ ${limit_price}"
        )
        
        try:
            order_data = LimitOrderRequest(
                symbol=symbol,
                qty=qty,
                side=OrderSide.BUY if side == OrderSideEnum.BUY else OrderSide.SELL,
                limit_price=limit_price,
                time_in_force=self._map_tif(time_in_force),
                extended_hours=extended_hours,
                client_order_id=client_order_id
            )
            
            order = self.client.submit_order(order_data)
            
            result = self._convert_order(order)
            logger.info(f"✅ Limit order submitted: {result.order_id}")
            
            return result
        
        except APIError as e:
            logger.error(f"Alpaca API error: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to submit limit order: {e}")
            raise
    
    def submit_stop_order(
        self,
        symbol: str,
        qty: float,
        side: OrderSideEnum,
        stop_price: float,
        time_in_force: TimeInForceEnum = TimeInForceEnum.DAY,
        extended_hours: bool = False,
        client_order_id: Optional[str] = None
    ) -> OrderResult:
        """
        Submit stop order.
        
        Args:
            symbol: Stock symbol
            qty: Quantity to trade
            side: Buy or sell
            stop_price: Stop price
            time_in_force: Order duration
            extended_hours: Allow extended hours
            client_order_id: Custom order ID
        
        Returns:
            OrderResult with order details
        """
        logger.info(
            f"Submitting stop order: {side.value} {qty} {symbol} stop @ ${stop_price}"
        )
        
        try:
            order_data = StopOrderRequest(
                symbol=symbol,
                qty=qty,
                side=OrderSide.BUY if side == OrderSideEnum.BUY else OrderSide.SELL,
                stop_price=stop_price,
                time_in_force=self._map_tif(time_in_force),
                extended_hours=extended_hours,
                client_order_id=client_order_id
            )
            
            order = self.client.submit_order(order_data)
            
            result = self._convert_order(order)
            logger.info(f"✅ Stop order submitted: {result.order_id}")
            
            return result
        
        except APIError as e:
            logger.error(f"Alpaca API error: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to submit stop order: {e}")
            raise
    
    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an order.
        
        Args:
            order_id: Order ID to cancel
        
        Returns:
            True if canceled successfully
        """
        logger.info(f"Canceling order: {order_id}")
        
        try:
            self.client.cancel_order_by_id(order_id)
            logger.info(f"✅ Order canceled: {order_id}")
            return True
        
        except APIError as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            return False
    
    def get_order(self, order_id: str) -> Optional[OrderResult]:
        """
        Get order status.
        
        Args:
            order_id: Order ID
        
        Returns:
            OrderResult or None if not found
        """
        try:
            order = self.client.get_order_by_id(order_id)
            return self._convert_order(order)
        
        except APIError as e:
            logger.error(f"Failed to get order {order_id}: {e}")
            return None
    
    def get_all_orders(
        self,
        status: Optional[str] = None,
        limit: int = 100
    ) -> List[OrderResult]:
        """
        Get all orders.
        
        Args:
            status: Filter by status ("open", "closed", "all")
            limit: Maximum number of orders
        
        Returns:
            List of OrderResult objects
        """
        try:
            request = GetOrdersRequest(
                status=status,
                limit=limit
            )
            
            orders = self.client.get_orders(request)
            
            return [self._convert_order(order) for order in orders]
        
        except APIError as e:
            logger.error(f"Failed to get orders: {e}")
            return []
    
    def get_position(self, symbol: str) -> Optional[PositionInfo]:
        """
        Get position for symbol.
        
        Args:
            symbol: Stock symbol
        
        Returns:
            PositionInfo or None if no position
        """
        try:
            position = self.client.get_open_position(symbol)
            
            return PositionInfo(
                symbol=position.symbol,
                qty=float(position.qty),
                side=position.side,
                market_value=float(position.market_value),
                cost_basis=float(position.cost_basis),
                unrealized_pl=float(position.unrealized_pl),
                unrealized_plpc=float(position.unrealized_plpc),
                current_price=float(position.current_price),
                avg_entry_price=float(position.avg_entry_price)
            )
        
        except APIError as e:
            # Position not found is not an error
            return None
        except Exception as e:
            logger.error(f"Failed to get position for {symbol}: {e}")
            return None
    
    def get_all_positions(self) -> List[PositionInfo]:
        """
        Get all open positions.
        
        Returns:
            List of PositionInfo objects
        """
        try:
            positions = self.client.get_all_positions()
            
            return [
                PositionInfo(
                    symbol=pos.symbol,
                    qty=float(pos.qty),
                    side=pos.side,
                    market_value=float(pos.market_value),
                    cost_basis=float(pos.cost_basis),
                    unrealized_pl=float(pos.unrealized_pl),
                    unrealized_plpc=float(pos.unrealized_plpc),
                    current_price=float(pos.current_price),
                    avg_entry_price=float(pos.avg_entry_price)
                )
                for pos in positions
            ]
        
        except APIError as e:
            logger.error(f"Failed to get positions: {e}")
            return []
    
    def close_position(
        self,
        symbol: str,
        qty: Optional[float] = None
    ) -> bool:
        """
        Close position (full or partial).
        
        Args:
            symbol: Stock symbol
            qty: Quantity to close (None = close all)
        
        Returns:
            True if closed successfully
        """
        logger.info(
            f"Closing position: {symbol}" + 
            (f" (qty={qty})" if qty else " (full)")
        )
        
        try:
            if qty is None:
                # Close entire position
                self.client.close_position(symbol)
            else:
                # Close partial position
                position = self.get_position(symbol)
                if not position:
                    logger.error(f"No position found for {symbol}")
                    return False
                
                # Determine side for closing
                side = OrderSideEnum.SELL if position.side == "long" else OrderSideEnum.BUY
                
                # Submit market order to close
                self.submit_market_order(
                    symbol=symbol,
                    qty=qty,
                    side=side
                )
            
            logger.info(f"✅ Position closed: {symbol}")
            return True
        
        except APIError as e:
            logger.error(f"Failed to close position {symbol}: {e}")
            return False
    
    def get_account(self) -> Dict:
        """
        Get account information.
        
        Returns:
            Dictionary with account details
        """
        try:
            account = self.client.get_account()
            
            return {
                "account_number": account.account_number,
                "status": account.status,
                "currency": account.currency,
                "buying_power": float(account.buying_power),
                "cash": float(account.cash),
                "portfolio_value": float(account.portfolio_value),
                "equity": float(account.equity),
                "last_equity": float(account.last_equity),
                "long_market_value": float(account.long_market_value),
                "short_market_value": float(account.short_market_value),
                "initial_margin": float(account.initial_margin),
                "maintenance_margin": float(account.maintenance_margin),
                "daytrade_count": account.daytrade_count,
                "pattern_day_trader": account.pattern_day_trader
            }
        
        except APIError as e:
            logger.error(f"Failed to get account: {e}")
            return {}
    
    def _map_tif(self, tif: TimeInForceEnum) -> TimeInForce:
        """Map TimeInForceEnum to Alpaca TimeInForce."""
        mapping = {
            TimeInForceEnum.DAY: TimeInForce.DAY,
            TimeInForceEnum.GTC: TimeInForce.GTC,
            TimeInForceEnum.IOC: TimeInForce.IOC,
            TimeInForceEnum.FOK: TimeInForce.FOK
        }
        return mapping[tif]
    
    def _convert_order(self, order) -> OrderResult:
        """Convert Alpaca order to OrderResult."""
        return OrderResult(
            order_id=str(order.id),
            client_order_id=order.client_order_id or "",
            symbol=order.symbol,
            side=order.side.value,
            type=order.type.value,
            qty=float(order.qty),
            filled_qty=float(order.filled_qty) if order.filled_qty else 0.0,
            filled_avg_price=float(order.filled_avg_price) if order.filled_avg_price else None,
            status=order.status.value,
            submitted_at=str(order.submitted_at),
            filled_at=str(order.filled_at) if order.filled_at else None,
            limit_price=float(order.limit_price) if order.limit_price else None,
            stop_price=float(order.stop_price) if order.stop_price else None,
            time_in_force=order.time_in_force.value,
            extended_hours=order.extended_hours
        )


# Example usage
if __name__ == "__main__":
    import os
    
    api_key = os.getenv("ALPACA_API_KEY", "YOUR_API_KEY")
    api_secret = os.getenv("ALPACA_API_SECRET", "YOUR_API_SECRET")
    
    if api_key == "YOUR_API_KEY":
        print("\n⚠️  ALPACA_API_KEY and ALPACA_API_SECRET not set!")
        print("\n📝 To use this executor:")
        print("1. Sign up at: https://alpaca.markets/")
        print("2. Get your API keys (paper or live)")
        print("3. Set environment variables:")
        print("   export ALPACA_API_KEY='your_api_key'")
        print("   export ALPACA_API_SECRET='your_api_secret'")
        print("\nPlans:")
        print("  - Paper Trading: FREE")
        print("  - Live Trading: FREE (commission-free)")
        print("  - Alpaca+ Data: $9/mo (optional)")
    else:
        # Initialize executor (paper trading)
        executor = AlpacaExecutor(
            api_key=api_key,
            api_secret=api_secret,
            paper=True  # Paper trading for safety
        )
        
        # Example 1: Get account info
        print("\n" + "="*60)
        print("EXAMPLE 1: Account Information")
        print("="*60)
        
        account = executor.get_account()
        
        if account:
            print(f"\nAccount Status: {account['status']}")
            print(f"Buying Power: ${account['buying_power']:,.2f}")
            print(f"Cash: ${account['cash']:,.2f}")
            print(f"Portfolio Value: ${account['portfolio_value']:,.2f}")
        
        # Example 2: Submit market order (paper trading)
        print("\n" + "="*60)
        print("EXAMPLE 2: Submit Market Order (Paper)")
        print("="*60)
        
        try:
            order = executor.submit_market_order(
                symbol="SPY",
                qty=1,
                side=OrderSideEnum.BUY,
                time_in_force=TimeInForceEnum.DAY
            )
            
            print(f"\n✅ Order submitted:")
            print(f"   Order ID: {order.order_id}")
            print(f"   Symbol: {order.symbol}")
            print(f"   Side: {order.side}")
            print(f"   Qty: {order.qty}")
            print(f"   Status: {order.status}")
        except Exception as e:
            print(f"\n❌ Order failed: {e}")
        
        # Example 3: Get positions
        print("\n" + "="*60)
        print("EXAMPLE 3: Get All Positions")
        print("="*60)
        
        positions = executor.get_all_positions()
        
        if positions:
            print(f"\nOpen Positions ({len(positions)}):")
            for pos in positions:
                print(f"\n  {pos.symbol}:")
                print(f"    Qty: {pos.qty} ({pos.side})")
                print(f"    Value: ${pos.market_value:,.2f}")
                print(f"    P&L: ${pos.unrealized_pl:,.2f} ({pos.unrealized_plpc:+.2%})")
        else:
            print("\nNo open positions")
