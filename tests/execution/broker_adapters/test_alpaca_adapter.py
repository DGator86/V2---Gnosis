# tests/execution/broker_adapters/test_alpaca_adapter.py

"""
Tests for Alpaca broker adapter.

Uses mocking to avoid real API calls during testing.
Real integration tests should be run manually with paper trading account.
"""

import os
import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch, MagicMock

from execution.broker_adapters.alpaca_adapter import AlpacaBrokerAdapter
from execution.broker_adapters.base import (
    BrokerError,
    InsufficientFundsError,
    InvalidOrderError,
    BrokerConnectionError,
)
from execution.schemas import (
    OrderRequest,
    OrderSide,
    OrderType,
    TimeInForce,
    AssetClass,
    OrderStatus,
)


class TestAlpacaBrokerAdapterInitialization:
    """Test Alpaca adapter initialization and connection."""
    
    def test_initialization_with_explicit_credentials(self):
        """Test initialization with explicit API credentials."""
        with patch("execution.broker_adapters.alpaca_adapter.TradingClient") as mock_client:
            # Mock successful connection
            mock_instance = Mock()
            mock_client.return_value = mock_instance
            mock_instance.get_account.return_value = Mock()
            
            adapter = AlpacaBrokerAdapter(
                api_key="test_key",
                secret_key="test_secret",
                base_url="https://paper-api.alpaca.markets",
                paper=True,
            )
            
            assert adapter.api_key == "test_key"
            assert adapter.secret_key == "test_secret"
            assert adapter.paper is True
    
    def test_initialization_with_env_variables(self, monkeypatch):
        """Test initialization with environment variables."""
        monkeypatch.setenv("ALPACA_API_KEY", "env_key")
        monkeypatch.setenv("ALPACA_SECRET_KEY", "env_secret")
        monkeypatch.setenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")
        
        with patch("execution.broker_adapters.alpaca_adapter.TradingClient") as mock_client:
            mock_instance = Mock()
            mock_client.return_value = mock_instance
            mock_instance.get_account.return_value = Mock()
            
            adapter = AlpacaBrokerAdapter()
            
            assert adapter.api_key == "env_key"
            assert adapter.secret_key == "env_secret"
    
    def test_initialization_missing_credentials(self):
        """Test initialization fails with missing credentials."""
        with pytest.raises(BrokerConnectionError, match="credentials not found"):
            AlpacaBrokerAdapter(api_key=None, secret_key=None)
    
    def test_initialization_connection_failure(self):
        """Test initialization fails on connection error."""
        with patch("execution.broker_adapters.alpaca_adapter.TradingClient") as mock_client:
            mock_instance = Mock()
            mock_client.return_value = mock_instance
            mock_instance.get_account.side_effect = Exception("Connection failed")
            
            with pytest.raises(BrokerConnectionError, match="Failed to connect"):
                AlpacaBrokerAdapter(
                    api_key="test_key",
                    secret_key="test_secret",
                )


class TestAlpacaBrokerAdapterAccountManagement:
    """Test account and position management."""
    
    @pytest.fixture
    def mock_adapter(self):
        """Create mocked Alpaca adapter."""
        with patch("execution.broker_adapters.alpaca_adapter.TradingClient") as mock_client:
            mock_instance = Mock()
            mock_client.return_value = mock_instance
            mock_instance.get_account.return_value = Mock()
            
            adapter = AlpacaBrokerAdapter(
                api_key="test_key",
                secret_key="test_secret",
            )
            
            yield adapter
    
    def test_get_account_success(self, mock_adapter):
        """Test successful account retrieval."""
        # Mock account response
        mock_account = Mock()
        mock_account.account_number = "TEST123"
        mock_account.cash = "100000.00"
        mock_account.buying_power = "100000.00"
        mock_account.portfolio_value = "100000.00"
        mock_account.equity = "100000.00"
        mock_account.initial_margin = "0.00"
        
        mock_adapter.client.get_account.return_value = mock_account
        mock_adapter.client.get_all_positions.return_value = []
        
        account = mock_adapter.get_account()
        
        assert account.account_id == "TEST123"
        assert account.broker == "alpaca"
        assert account.cash == 100000.0
        assert account.buying_power == 100000.0
        assert len(account.positions) == 0
    
    def test_get_positions_success(self, mock_adapter):
        """Test successful position retrieval."""
        # Mock position response
        mock_position = Mock()
        mock_position.symbol = "SPY"
        mock_position.asset_class = "us_equity"
        mock_position.qty = "10"
        mock_position.avg_entry_price = "450.00"
        mock_position.current_price = "455.00"
        mock_position.market_value = "4550.00"
        mock_position.unrealized_pl = "50.00"
        
        mock_adapter.client.get_all_positions.return_value = [mock_position]
        
        positions = mock_adapter.get_positions()
        
        assert len(positions) == 1
        assert positions[0].symbol == "SPY"
        assert positions[0].quantity == 10
        assert positions[0].unrealized_pnl == 50.0
    
    def test_get_account_failure(self, mock_adapter):
        """Test account retrieval failure."""
        mock_adapter.client.get_account.side_effect = Exception("API error")
        
        with pytest.raises(BrokerError, match="Failed to get account info"):
            mock_adapter.get_account()


class TestAlpacaBrokerAdapterOrderPlacement:
    """Test order placement functionality."""
    
    @pytest.fixture
    def mock_adapter(self):
        """Create mocked Alpaca adapter."""
        with patch("execution.broker_adapters.alpaca_adapter.TradingClient") as mock_client:
            mock_instance = Mock()
            mock_client.return_value = mock_instance
            mock_instance.get_account.return_value = Mock()
            
            adapter = AlpacaBrokerAdapter(
                api_key="test_key",
                secret_key="test_secret",
            )
            
            yield adapter
    
    def test_place_market_order_success(self, mock_adapter):
        """Test successful market order placement."""
        # Mock order response
        mock_order = Mock()
        mock_order.id = "order_123"
        mock_order.symbol = "SPY"
        mock_order.qty = "10"
        mock_order.side = "buy"
        mock_order.order_type = "market"
        mock_order.status = "new"
        mock_order.filled_qty = "0"
        mock_order.filled_avg_price = None
        mock_order.submitted_at = datetime.now(timezone.utc)
        mock_order.filled_at = None
        mock_order.asset_class = "us_equity"
        
        mock_adapter.client.submit_order.return_value = mock_order
        
        order_request = OrderRequest(
            asset_class=AssetClass.STOCK,
            symbol="SPY",
            side=OrderSide.BUY,
            quantity=10,
            order_type=OrderType.MARKET,
        )
        
        result = mock_adapter.place_order(order_request)
        
        assert result.order_id == "order_123"
        assert result.symbol == "SPY"
        assert result.quantity == 10
        assert result.status == OrderStatus.SUBMITTED
        assert result.broker == "alpaca"
    
    def test_place_limit_order_success(self, mock_adapter):
        """Test successful limit order placement."""
        mock_order = Mock()
        mock_order.id = "order_456"
        mock_order.symbol = "SPY"
        mock_order.qty = "5"
        mock_order.side = "sell"
        mock_order.order_type = "limit"
        mock_order.status = "new"
        mock_order.filled_qty = "0"
        mock_order.filled_avg_price = None
        mock_order.submitted_at = datetime.now(timezone.utc)
        mock_order.filled_at = None
        mock_order.asset_class = "us_equity"
        
        mock_adapter.client.submit_order.return_value = mock_order
        
        order_request = OrderRequest(
            asset_class=AssetClass.STOCK,
            symbol="SPY",
            side=OrderSide.SELL,
            quantity=5,
            order_type=OrderType.LIMIT,
            limit_price=460.0,
        )
        
        result = mock_adapter.place_order(order_request)
        
        assert result.order_id == "order_456"
        assert result.side == OrderSide.SELL
        assert result.order_type == OrderType.LIMIT
    
    def test_place_limit_order_missing_price(self, mock_adapter):
        """Test limit order fails without limit price."""
        order_request = OrderRequest(
            asset_class=AssetClass.STOCK,
            symbol="SPY",
            side=OrderSide.BUY,
            quantity=10,
            order_type=OrderType.LIMIT,
            limit_price=None,  # Missing required field
        )
        
        with pytest.raises(InvalidOrderError, match="Limit price required"):
            mock_adapter.place_order(order_request)
    
    def test_place_order_insufficient_funds(self, mock_adapter):
        """Test order fails with insufficient funds."""
        mock_adapter.client.submit_order.side_effect = Exception("Insufficient buying power")
        
        order_request = OrderRequest(
            asset_class=AssetClass.STOCK,
            symbol="SPY",
            side=OrderSide.BUY,
            quantity=1000,  # Too large
            order_type=OrderType.MARKET,
        )
        
        with pytest.raises(InsufficientFundsError, match="Insufficient funds"):
            mock_adapter.place_order(order_request)
    
    def test_place_order_invalid_symbol(self, mock_adapter):
        """Test order fails with invalid symbol."""
        mock_adapter.client.submit_order.side_effect = Exception("Symbol not found")
        
        order_request = OrderRequest(
            asset_class=AssetClass.STOCK,
            symbol="INVALID_SYMBOL",
            side=OrderSide.BUY,
            quantity=10,
            order_type=OrderType.MARKET,
        )
        
        with pytest.raises(InvalidOrderError, match="Invalid order"):
            mock_adapter.place_order(order_request)


class TestAlpacaBrokerAdapterOrderManagement:
    """Test order status and cancellation."""
    
    @pytest.fixture
    def mock_adapter(self):
        """Create mocked Alpaca adapter."""
        with patch("execution.broker_adapters.alpaca_adapter.TradingClient") as mock_client:
            mock_instance = Mock()
            mock_client.return_value = mock_instance
            mock_instance.get_account.return_value = Mock()
            
            adapter = AlpacaBrokerAdapter(
                api_key="test_key",
                secret_key="test_secret",
            )
            
            yield adapter
    
    def test_get_order_status_filled(self, mock_adapter):
        """Test getting status of filled order."""
        mock_order = Mock()
        mock_order.id = "order_123"
        mock_order.symbol = "SPY"
        mock_order.qty = "10"
        mock_order.side = "buy"
        mock_order.order_type = "market"
        mock_order.status = "filled"
        mock_order.filled_qty = "10"
        mock_order.filled_avg_price = "455.50"
        mock_order.submitted_at = datetime.now(timezone.utc)
        mock_order.filled_at = datetime.now(timezone.utc)
        mock_order.asset_class = "us_equity"
        
        mock_adapter.client.get_order_by_id.return_value = mock_order
        
        result = mock_adapter.get_order_status("order_123")
        
        assert result.status == OrderStatus.FILLED
        assert result.filled_quantity == 10
        assert result.avg_fill_price == 455.50
        assert len(result.fills) == 1
    
    def test_cancel_order_success(self, mock_adapter):
        """Test successful order cancellation."""
        mock_adapter.client.cancel_order_by_id.return_value = None
        
        success = mock_adapter.cancel_order("order_123")
        
        assert success is True
    
    def test_cancel_order_failure(self, mock_adapter):
        """Test order cancellation failure."""
        mock_adapter.client.cancel_order_by_id.side_effect = Exception("Order not found")
        
        success = mock_adapter.cancel_order("invalid_order")
        
        assert success is False


class TestAlpacaBrokerAdapterQuotes:
    """Test quote retrieval functionality."""
    
    @pytest.fixture
    def mock_adapter(self):
        """Create mocked Alpaca adapter."""
        with patch("execution.broker_adapters.alpaca_adapter.TradingClient") as mock_trading:
            with patch("execution.broker_adapters.alpaca_adapter.StockHistoricalDataClient") as mock_data:
                mock_trading_instance = Mock()
                mock_trading.return_value = mock_trading_instance
                mock_trading_instance.get_account.return_value = Mock()
                
                mock_data_instance = Mock()
                mock_data.return_value = mock_data_instance
                
                adapter = AlpacaBrokerAdapter(
                    api_key="test_key",
                    secret_key="test_secret",
                )
                
                yield adapter
    
    def test_get_quote_success(self, mock_adapter):
        """Test successful single quote retrieval."""
        mock_quote = Mock()
        mock_quote.bid_price = 454.50
        mock_quote.ask_price = 454.60
        mock_quote.bid_size = 100
        mock_quote.ask_size = 200
        mock_quote.timestamp = datetime.now(timezone.utc)
        
        mock_adapter.data_client.get_stock_latest_quote.return_value = {"SPY": mock_quote}
        
        quote = mock_adapter.get_quote("SPY")
        
        assert quote.symbol == "SPY"
        assert quote.bid == 454.50
        assert quote.ask == 454.60
        assert quote.mid == 454.55
        assert quote.bid_size == 100
        assert quote.ask_size == 200
    
    def test_get_quotes_batch_success(self, mock_adapter):
        """Test successful batch quote retrieval."""
        mock_quote_spy = Mock()
        mock_quote_spy.bid_price = 454.50
        mock_quote_spy.ask_price = 454.60
        mock_quote_spy.bid_size = 100
        mock_quote_spy.ask_size = 200
        mock_quote_spy.timestamp = datetime.now(timezone.utc)
        
        mock_quote_qqq = Mock()
        mock_quote_qqq.bid_price = 380.00
        mock_quote_qqq.ask_price = 380.10
        mock_quote_qqq.bid_size = 150
        mock_quote_qqq.ask_size = 180
        mock_quote_qqq.timestamp = datetime.now(timezone.utc)
        
        mock_adapter.data_client.get_stock_latest_quote.return_value = {
            "SPY": mock_quote_spy,
            "QQQ": mock_quote_qqq,
        }
        
        quotes = mock_adapter.get_quotes_batch(["SPY", "QQQ"])
        
        assert len(quotes) == 2
        assert quotes[0].symbol in ["SPY", "QQQ"]
        assert quotes[1].symbol in ["SPY", "QQQ"]
    
    def test_get_quote_failure(self, mock_adapter):
        """Test quote retrieval failure."""
        mock_adapter.data_client.get_stock_latest_quote.side_effect = Exception("API error")
        
        with pytest.raises(BrokerError, match="Failed to get quote"):
            mock_adapter.get_quote("INVALID")


@pytest.mark.integration
@pytest.mark.skipif(
    "ALPACA_API_KEY" not in os.environ,
    reason="Alpaca credentials not available"
)
class TestAlpacaBrokerAdapterIntegration:
    """
    Integration tests with real Alpaca paper trading account.
    
    These tests require valid Alpaca paper trading credentials in environment variables.
    Run with: pytest -m integration tests/execution/broker_adapters/test_alpaca_adapter.py
    """
    
    @pytest.fixture
    def real_adapter(self):
        """Create real Alpaca adapter (paper trading)."""
        import os
        return AlpacaBrokerAdapter(
            api_key=os.getenv("ALPACA_API_KEY"),
            secret_key=os.getenv("ALPACA_SECRET_KEY"),
            paper=True,
        )
    
    def test_real_get_account(self, real_adapter):
        """Test real account retrieval."""
        account = real_adapter.get_account()
        
        assert account.account_id is not None
        assert account.broker == "alpaca"
        assert account.cash >= 0
        assert account.buying_power >= 0
    
    def test_real_get_quote(self, real_adapter):
        """Test real quote retrieval for SPY."""
        quote = real_adapter.get_quote("SPY")
        
        assert quote.symbol == "SPY"
        assert quote.bid > 0
        assert quote.ask > 0
        assert quote.ask >= quote.bid
        assert quote.spread_pct < 0.01  # Spread should be < 1% for SPY
