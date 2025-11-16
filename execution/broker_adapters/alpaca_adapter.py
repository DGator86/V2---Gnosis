# execution/broker_adapters/alpaca_adapter.py

"""
Alpaca broker adapter for Trade Agent v3.

Implements the BrokerAdapter protocol using Alpaca's REST API.
Supports both paper trading and live trading modes.

Environment Variables Required:
    ALPACA_API_KEY: Your Alpaca API key
    ALPACA_SECRET_KEY: Your Alpaca secret key
    ALPACA_BASE_URL: Base URL (paper or live)
        Paper: https://paper-api.alpaca.markets
        Live: https://api.alpaca.markets
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import List, Optional
from uuid import uuid4

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import (
    MarketOrderRequest,
    LimitOrderRequest,
    StopOrderRequest,
    StopLimitOrderRequest,
    GetOrdersRequest,
)
from alpaca.trading.enums import (
    OrderSide as AlpacaOrderSide,
    OrderType as AlpacaOrderType,
    TimeInForce as AlpacaTimeInForce,
    OrderStatus as AlpacaOrderStatus,
    AssetClass as AlpacaAssetClass,
)
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestQuoteRequest

from ..schemas import (
    OrderRequest,
    OrderResult,
    AccountInfo,
    Position,
    Quote,
    OrderType,
    OrderSide,
    OrderStatus,
    TimeInForce,
    AssetClass,
    Fill,
)
from .base import (
    BrokerAdapter,
    BrokerError,
    InsufficientFundsError,
    InvalidOrderError,
    BrokerConnectionError,
)


class AlpacaBrokerAdapter:
    """
    Alpaca broker adapter implementation.
    
    Provides live and paper trading through Alpaca's API.
    Implements the BrokerAdapter protocol for execution layer compatibility.
    
    Features:
        - Real-time order placement (market, limit, stop, stop-limit)
        - Position and account management
        - Real-time quote data
        - Commission-free stock/ETF trading
        - Paper trading support
    
    Example:
        >>> adapter = AlpacaBrokerAdapter(
        ...     api_key="PKELRVPCSCXJOWMMQIQEHH3LOJ",
        ...     secret_key="Ezf2dYZD1M85tYBGUbJb7374rmmyz6H7eTtWNhk6mMZx",
        ...     paper=True
        ... )
        >>> account = adapter.get_account()
        >>> print(f"Buying power: ${account.buying_power:,.2f}")
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        base_url: Optional[str] = None,
        paper: bool = True,
    ):
        """
        Initialize Alpaca broker adapter.
        
        Args:
            api_key: Alpaca API key (reads from ALPACA_API_KEY env if None)
            secret_key: Alpaca secret key (reads from ALPACA_SECRET_KEY env if None)
            base_url: Base URL (reads from ALPACA_BASE_URL env if None)
            paper: If True, use paper trading (default: True)
        
        Raises:
            BrokerConnectionError: If credentials are invalid or connection fails
        """
        self.api_key = api_key or os.getenv("ALPACA_API_KEY")
        self.secret_key = secret_key or os.getenv("ALPACA_SECRET_KEY")
        self.base_url = base_url or os.getenv("ALPACA_BASE_URL")
        self.paper = paper
        
        if not self.api_key or not self.secret_key:
            raise BrokerConnectionError(
                "Alpaca API credentials not found. Set ALPACA_API_KEY and "
                "ALPACA_SECRET_KEY environment variables or pass them explicitly."
            )
        
        # Default to paper trading URL if not specified
        if not self.base_url:
            self.base_url = "https://paper-api.alpaca.markets"
            self.paper = True
        
        try:
            # Initialize trading client
            self.client = TradingClient(
                api_key=self.api_key,
                secret_key=self.secret_key,
                paper=self.paper,
                url_override=self.base_url if self.base_url else None,
            )
            
            # Initialize data client (for quotes)
            self.data_client = StockHistoricalDataClient(
                api_key=self.api_key,
                secret_key=self.secret_key,
            )
            
            # Test connection
            self.client.get_account()
            
        except Exception as e:
            raise BrokerConnectionError(f"Failed to connect to Alpaca: {str(e)}")
    
    def get_account(self) -> AccountInfo:
        """
        Retrieve current account information.
        
        Returns:
            AccountInfo with cash, buying power, positions, etc.
        
        Raises:
            BrokerError: If account retrieval fails
        """
        try:
            account = self.client.get_account()
            positions = self.get_positions()
            
            return AccountInfo(
                account_id=account.account_number,
                broker="alpaca",
                cash=float(account.cash),
                buying_power=float(account.buying_power),
                portfolio_value=float(account.portfolio_value),
                equity=float(account.equity),
                margin_used=float(account.initial_margin) if account.initial_margin else 0.0,
                positions=positions,
            )
        except Exception as e:
            raise BrokerError(f"Failed to get account info: {str(e)}")
    
    def get_positions(self) -> List[Position]:
        """
        Get all current positions.
        
        Returns:
            List of Position objects
        
        Raises:
            BrokerError: If position retrieval fails
        """
        try:
            alpaca_positions = self.client.get_all_positions()
            
            positions = []
            for pos in alpaca_positions:
                positions.append(Position(
                    symbol=pos.symbol,
                    asset_class=self._map_asset_class_from_alpaca(pos.asset_class),
                    quantity=int(pos.qty),
                    avg_entry_price=float(pos.avg_entry_price),
                    current_price=float(pos.current_price),
                    market_value=float(pos.market_value),
                    unrealized_pnl=float(pos.unrealized_pl),
                    realized_pnl=0.0,  # Alpaca doesn't provide this in position object
                ))
            
            return positions
        except Exception as e:
            raise BrokerError(f"Failed to get positions: {str(e)}")
    
    def place_order(self, order: OrderRequest) -> OrderResult:
        """
        Submit an order to Alpaca.
        
        Args:
            order: OrderRequest with order details
        
        Returns:
            OrderResult with order ID and status
        
        Raises:
            InsufficientFundsError: If account has insufficient funds
            InvalidOrderError: If order parameters are invalid
            BrokerError: If order submission fails
        """
        try:
            # Map our order types to Alpaca order types
            alpaca_order = self._build_alpaca_order(order)
            
            # Submit order
            submitted_order = self.client.submit_order(alpaca_order)
            
            # Convert to OrderResult
            return self._convert_alpaca_order_to_result(submitted_order, order)
            
        except (InsufficientFundsError, InvalidOrderError, BrokerError):
            # Re-raise our own exceptions as-is
            raise
        except Exception as e:
            error_msg = str(e).lower()
            
            if "insufficient" in error_msg or "buying power" in error_msg:
                raise InsufficientFundsError(f"Insufficient funds: {str(e)}")
            elif "invalid" in error_msg or "not found" in error_msg:
                raise InvalidOrderError(f"Invalid order: {str(e)}")
            else:
                raise BrokerError(f"Failed to place order: {str(e)}")
    
    def get_order_status(self, order_id: str) -> OrderResult:
        """
        Check status of an existing order.
        
        Args:
            order_id: Alpaca's order identifier
        
        Returns:
            OrderResult with current status and fills
        
        Raises:
            BrokerError: If order status retrieval fails
        """
        try:
            alpaca_order = self.client.get_order_by_id(order_id)
            
            # Convert to OrderResult (with minimal OrderRequest context)
            order_request = OrderRequest(
                asset_class=self._map_asset_class_from_alpaca(alpaca_order.asset_class),
                symbol=alpaca_order.symbol,
                side=self._map_side_from_alpaca(alpaca_order.side),
                quantity=int(alpaca_order.qty),
                order_type=self._map_order_type_from_alpaca(alpaca_order.order_type),
            )
            
            return self._convert_alpaca_order_to_result(alpaca_order, order_request)
            
        except Exception as e:
            raise BrokerError(f"Failed to get order status: {str(e)}")
    
    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel a pending order.
        
        Args:
            order_id: Alpaca's order identifier
        
        Returns:
            True if cancellation successful, False otherwise
        """
        try:
            self.client.cancel_order_by_id(order_id)
            return True
        except Exception:
            return False
    
    def get_quote(self, symbol: str) -> Quote:
        """
        Get real-time quote for a symbol.
        
        Args:
            symbol: Ticker symbol (e.g., 'SPY')
        
        Returns:
            Quote with bid, ask, last, sizes
        
        Raises:
            BrokerError: If quote retrieval fails
        """
        try:
            request = StockLatestQuoteRequest(symbol_or_symbols=symbol)
            quotes = self.data_client.get_stock_latest_quote(request)
            
            alpaca_quote = quotes[symbol]
            
            # Calculate mid price
            bid = float(alpaca_quote.bid_price)
            ask = float(alpaca_quote.ask_price)
            mid = (bid + ask) / 2.0
            
            return Quote(
                symbol=symbol,
                bid=bid,
                ask=ask,
                mid=mid,
                last=mid,  # Alpaca doesn't provide last in latest_quote
                bid_size=int(alpaca_quote.bid_size),
                ask_size=int(alpaca_quote.ask_size),
                timestamp=alpaca_quote.timestamp.replace(tzinfo=timezone.utc),
            )
            
        except Exception as e:
            raise BrokerError(f"Failed to get quote for {symbol}: {str(e)}")
    
    def get_quotes_batch(self, symbols: List[str]) -> List[Quote]:
        """
        Get quotes for multiple symbols (batch request).
        
        Args:
            symbols: List of ticker symbols
        
        Returns:
            List of Quote objects
        
        Raises:
            BrokerError: If batch quote retrieval fails
        """
        try:
            request = StockLatestQuoteRequest(symbol_or_symbols=symbols)
            quotes_dict = self.data_client.get_stock_latest_quote(request)
            
            quotes = []
            for symbol, alpaca_quote in quotes_dict.items():
                bid = float(alpaca_quote.bid_price)
                ask = float(alpaca_quote.ask_price)
                mid = (bid + ask) / 2.0
                
                quotes.append(Quote(
                    symbol=symbol,
                    bid=bid,
                    ask=ask,
                    mid=mid,
                    last=mid,
                    bid_size=int(alpaca_quote.bid_size),
                    ask_size=int(alpaca_quote.ask_size),
                    timestamp=alpaca_quote.timestamp.replace(tzinfo=timezone.utc),
                ))
            
            return quotes
            
        except Exception as e:
            raise BrokerError(f"Failed to get batch quotes: {str(e)}")
    
    # ========== Helper Methods ==========
    
    def _build_alpaca_order(self, order: OrderRequest):
        """Convert OrderRequest to Alpaca order request."""
        # Map our enums to Alpaca enums
        side = AlpacaOrderSide.BUY if order.side == OrderSide.BUY else AlpacaOrderSide.SELL
        tif = self._map_time_in_force_to_alpaca(order.time_in_force)
        
        # Build appropriate order type
        if order.order_type == OrderType.MARKET:
            return MarketOrderRequest(
                symbol=order.symbol,
                qty=order.quantity,
                side=side,
                time_in_force=tif,
            )
        elif order.order_type == OrderType.LIMIT:
            if not order.limit_price:
                raise InvalidOrderError("Limit price required for limit orders")
            return LimitOrderRequest(
                symbol=order.symbol,
                qty=order.quantity,
                side=side,
                time_in_force=tif,
                limit_price=order.limit_price,
            )
        elif order.order_type == OrderType.STOP:
            if not order.stop_price:
                raise InvalidOrderError("Stop price required for stop orders")
            return StopOrderRequest(
                symbol=order.symbol,
                qty=order.quantity,
                side=side,
                time_in_force=tif,
                stop_price=order.stop_price,
            )
        elif order.order_type == OrderType.STOP_LIMIT:
            if not order.limit_price or not order.stop_price:
                raise InvalidOrderError("Limit and stop price required for stop-limit orders")
            return StopLimitOrderRequest(
                symbol=order.symbol,
                qty=order.quantity,
                side=side,
                time_in_force=tif,
                limit_price=order.limit_price,
                stop_price=order.stop_price,
            )
        else:
            raise InvalidOrderError(f"Unsupported order type: {order.order_type}")
    
    def _convert_alpaca_order_to_result(self, alpaca_order, original_order: OrderRequest) -> OrderResult:
        """Convert Alpaca order to OrderResult."""
        # Map status
        status = self._map_status_from_alpaca(alpaca_order.status)
        
        # Extract fills
        fills = []
        if alpaca_order.filled_qty and int(alpaca_order.filled_qty) > 0:
            # Alpaca doesn't provide detailed fill breakdown in basic order object
            # We create a single Fill entry with average price
            fills.append(Fill(
                fill_id=f"fill_{alpaca_order.id}",
                quantity=int(alpaca_order.filled_qty),
                price=float(alpaca_order.filled_avg_price) if alpaca_order.filled_avg_price else 0.0,
                timestamp=alpaca_order.filled_at if alpaca_order.filled_at else datetime.now(timezone.utc),
                commission=0.0,  # Alpaca is commission-free for stocks
            ))
        
        # Calculate totals
        filled_qty = int(alpaca_order.filled_qty) if alpaca_order.filled_qty else 0
        avg_price = float(alpaca_order.filled_avg_price) if alpaca_order.filled_avg_price else None
        total_cost = filled_qty * avg_price if avg_price else 0.0
        
        return OrderResult(
            order_id=str(alpaca_order.id),
            status=status,
            broker="alpaca",
            symbol=alpaca_order.symbol,
            side=self._map_side_from_alpaca(alpaca_order.side),
            quantity=int(alpaca_order.qty),
            order_type=self._map_order_type_from_alpaca(alpaca_order.order_type),
            filled_quantity=filled_qty,
            avg_fill_price=avg_price,
            fills=fills,
            total_cost=total_cost,
            total_commission=0.0,  # Commission-free
            estimated_slippage=0.0,  # Not available from Alpaca
            submitted_at=alpaca_order.submitted_at.replace(tzinfo=timezone.utc) if alpaca_order.submitted_at else None,
            filled_at=alpaca_order.filled_at.replace(tzinfo=timezone.utc) if alpaca_order.filled_at else None,
            error_message=None,
        )
    
    def _map_time_in_force_to_alpaca(self, tif: TimeInForce) -> AlpacaTimeInForce:
        """Map our TimeInForce to Alpaca's."""
        mapping = {
            TimeInForce.DAY: AlpacaTimeInForce.DAY,
            TimeInForce.GTC: AlpacaTimeInForce.GTC,
            TimeInForce.IOC: AlpacaTimeInForce.IOC,
            TimeInForce.FOK: AlpacaTimeInForce.FOK,
        }
        return mapping.get(tif, AlpacaTimeInForce.DAY)
    
    def _map_status_from_alpaca(self, status: AlpacaOrderStatus) -> OrderStatus:
        """Map Alpaca order status to our OrderStatus."""
        mapping = {
            AlpacaOrderStatus.NEW: OrderStatus.SUBMITTED,
            AlpacaOrderStatus.ACCEPTED: OrderStatus.SUBMITTED,
            AlpacaOrderStatus.PENDING_NEW: OrderStatus.PENDING,
            AlpacaOrderStatus.PARTIALLY_FILLED: OrderStatus.PARTIAL_FILL,
            AlpacaOrderStatus.FILLED: OrderStatus.FILLED,
            AlpacaOrderStatus.CANCELED: OrderStatus.CANCELLED,
            AlpacaOrderStatus.REJECTED: OrderStatus.REJECTED,
            AlpacaOrderStatus.EXPIRED: OrderStatus.EXPIRED,
        }
        return mapping.get(status, OrderStatus.PENDING)
    
    def _map_side_from_alpaca(self, side: AlpacaOrderSide) -> OrderSide:
        """Map Alpaca order side to our OrderSide."""
        return OrderSide.BUY if side == AlpacaOrderSide.BUY else OrderSide.SELL
    
    def _map_order_type_from_alpaca(self, order_type: AlpacaOrderType) -> OrderType:
        """Map Alpaca order type to our OrderType."""
        mapping = {
            AlpacaOrderType.MARKET: OrderType.MARKET,
            AlpacaOrderType.LIMIT: OrderType.LIMIT,
            AlpacaOrderType.STOP: OrderType.STOP,
            AlpacaOrderType.STOP_LIMIT: OrderType.STOP_LIMIT,
        }
        return mapping.get(order_type, OrderType.MARKET)
    
    def _map_asset_class_from_alpaca(self, asset_class) -> AssetClass:
        """Map Alpaca asset class to our AssetClass."""
        # Alpaca's asset_class might be string or enum
        asset_str = str(asset_class).lower()
        if "stock" in asset_str or "us_equity" in asset_str:
            return AssetClass.STOCK
        elif "option" in asset_str:
            return AssetClass.OPTION
        elif "crypto" in asset_str:
            return AssetClass.CRYPTO
        else:
            return AssetClass.STOCK  # Default to stock
