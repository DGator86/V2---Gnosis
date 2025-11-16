# tests/execution/test_execution_layer.py

"""
Comprehensive tests for Trade Agent v3 execution layer.

Tests cover:
- Simulated broker functionality
- Execution cost modeling
- Smart order routing
- Order lifecycle management
"""

from datetime import datetime, timezone

import pytest

from execution.schemas import (
    OrderRequest,
    OrderType,
    OrderSide,
    TimeInForce,
    AssetClass,
    Quote,
)
from execution.broker_adapters.simulated_adapter import SimulatedBrokerAdapter
from execution.cost_model import ExecutionCostModel
from execution.router import SmartOrderRouter
from execution.order_controller import OrderLifecycleController


@pytest.fixture
def simulated_broker():
    """Create simulated broker with $100k initial cash."""
    return SimulatedBrokerAdapter(initial_cash=100000.0)


@pytest.fixture
def sample_quote():
    """Create sample quote for SPY."""
    return Quote(
        symbol="SPY",
        bid=450.0,
        ask=450.50,
        mid=450.25,
        last=450.30,
        bid_size=1000,
        ask_size=1000,
        timestamp=datetime.now(timezone.utc),
    )


@pytest.fixture
def cost_model():
    """Create execution cost model."""
    return ExecutionCostModel(
        commission_per_contract=0.65,
        commission_per_share=0.0,
    )


@pytest.fixture
def router(cost_model):
    """Create smart order router."""
    return SmartOrderRouter(cost_model=cost_model)


class TestSimulatedBroker:
    """Test simulated broker adapter."""
    
    def test_initialization(self, simulated_broker):
        """Test broker initialization."""
        account = simulated_broker.get_account()
        
        assert account.cash == 100000.0
        assert account.broker == "simulated"
        assert len(account.positions) == 0
    
    def test_place_buy_order_stock(self, simulated_broker, sample_quote):
        """Test placing buy order for stock."""
        simulated_broker.set_quote("SPY", sample_quote)
        
        order = OrderRequest(
            asset_class=AssetClass.STOCK,
            symbol="SPY",
            side=OrderSide.BUY,
            quantity=10,
            order_type=OrderType.MARKET,
        )
        
        result = simulated_broker.place_order(order)
        
        assert result.status.value == "filled"
        assert result.filled_quantity == 10
        assert result.avg_fill_price is not None
        assert result.total_commission == 0.0  # Commission-free stocks
    
    def test_place_sell_order(self, simulated_broker, sample_quote):
        """Test placing sell order (short)."""
        simulated_broker.set_quote("SPY", sample_quote)
        
        order = OrderRequest(
            asset_class=AssetClass.STOCK,
            symbol="SPY",
            side=OrderSide.SELL,
            quantity=10,
            order_type=OrderType.MARKET,
        )
        
        result = simulated_broker.place_order(order)
        
        assert result.status.value == "filled"
        # Cash should increase (short sale proceeds)
        account = simulated_broker.get_account()
        assert account.cash > 100000.0
    
    def test_insufficient_funds(self, simulated_broker):
        """Test order rejection with insufficient funds."""
        # Try to buy with more money than available
        quote = Quote(
            symbol="EXPENSIVE",
            bid=100000.0,
            ask=100000.0,
            mid=100000.0,
            last=100000.0,
            bid_size=100,
            ask_size=100,
            timestamp=datetime.now(timezone.utc),
        )
        simulated_broker.set_quote("EXPENSIVE", quote)
        
        order = OrderRequest(
            asset_class=AssetClass.STOCK,
            symbol="EXPENSIVE",
            side=OrderSide.BUY,
            quantity=2,  # Would cost >$200k
            order_type=OrderType.MARKET,
        )
        
        result = simulated_broker.place_order(order)
        
        assert result.status.value == "rejected"
        assert "Insufficient funds" in result.error_message
    
    def test_position_tracking(self, simulated_broker, sample_quote):
        """Test position tracking after trades."""
        simulated_broker.set_quote("SPY", sample_quote)
        
        # Buy 10 shares
        order1 = OrderRequest(
            asset_class=AssetClass.STOCK,
            symbol="SPY",
            side=OrderSide.BUY,
            quantity=10,
            order_type=OrderType.MARKET,
        )
        simulated_broker.place_order(order1)
        
        positions = simulated_broker.get_positions()
        assert len(positions) == 1
        assert positions[0].symbol == "SPY"
        assert positions[0].quantity == 10
        
        # Buy 5 more
        order2 = OrderRequest(
            asset_class=AssetClass.STOCK,
            symbol="SPY",
            side=OrderSide.BUY,
            quantity=5,
            order_type=OrderType.MARKET,
        )
        simulated_broker.place_order(order2)
        
        positions = simulated_broker.get_positions()
        assert len(positions) == 1
        assert positions[0].quantity == 15
    
    def test_close_position(self, simulated_broker, sample_quote):
        """Test closing a position."""
        simulated_broker.set_quote("SPY", sample_quote)
        
        # Open position
        order1 = OrderRequest(
            asset_class=AssetClass.STOCK,
            symbol="SPY",
            side=OrderSide.BUY,
            quantity=10,
            order_type=OrderType.MARKET,
        )
        simulated_broker.place_order(order1)
        
        # Close position
        order2 = OrderRequest(
            asset_class=AssetClass.STOCK,
            symbol="SPY",
            side=OrderSide.SELL,
            quantity=10,
            order_type=OrderType.MARKET,
        )
        simulated_broker.place_order(order2)
        
        positions = simulated_broker.get_positions()
        assert len(positions) == 0


class TestExecutionCostModel:
    """Test execution cost modeling."""
    
    def test_market_order_cost(self, cost_model, sample_quote):
        """Test cost estimation for market order."""
        cost = cost_model.estimate_cost(
            symbol="SPY",
            quote=sample_quote,
            quantity=100,
            side=OrderSide.BUY,
            asset_class=AssetClass.STOCK,
            order_type=OrderType.MARKET,
        )
        
        assert cost.total_cost > 0
        assert cost.bid_ask_spread > 0
        assert cost.estimated_slippage > 0
        assert cost.commission == 0.0  # Commission-free stocks
        assert 0.0 <= cost.fill_probability <= 1.0
    
    def test_limit_order_cost(self, cost_model, sample_quote):
        """Test cost estimation for limit order."""
        cost = cost_model.estimate_cost(
            symbol="SPY",
            quote=sample_quote,
            quantity=100,
            side=OrderSide.BUY,
            asset_class=AssetClass.STOCK,
            order_type=OrderType.LIMIT,
        )
        
        # Limit orders should have some slippage but less than market orders
        assert cost.estimated_slippage > 0
        assert cost.fill_probability < 1.0  # Less than 100% for limit
    
    def test_option_commission(self, cost_model, sample_quote):
        """Test commission calculation for options."""
        cost = cost_model.estimate_cost(
            symbol="SPY250117C00450000",
            quote=sample_quote,
            quantity=10,
            side=OrderSide.BUY,
            asset_class=AssetClass.OPTION,
            order_type=OrderType.LIMIT,
        )
        
        # Options have commissions
        expected_commission = 10 * 0.65
        assert cost.commission == expected_commission
    
    def test_market_impact(self, cost_model, sample_quote):
        """Test market impact estimation."""
        # Large order relative to ADV
        cost = cost_model.estimate_cost(
            symbol="SPY",
            quote=sample_quote,
            quantity=100000,
            side=OrderSide.BUY,
            asset_class=AssetClass.STOCK,
            order_type=OrderType.MARKET,
            adv=1000000.0,  # 10% of ADV
        )
        
        assert cost.market_impact > 0
    
    def test_compare_order_types(self, cost_model, sample_quote):
        """Test comparison of order types."""
        comparison = cost_model.compare_order_types(
            symbol="SPY",
            quote=sample_quote,
            quantity=100,
            side=OrderSide.BUY,
            asset_class=AssetClass.STOCK,
        )
        
        assert OrderType.MARKET in comparison
        assert OrderType.LIMIT in comparison
        
        # Market orders typically have higher cost but 100% fill probability
        assert comparison[OrderType.MARKET].fill_probability == 1.0


class TestSmartOrderRouter:
    """Test smart order routing."""
    
    def test_tight_spread_market_order(self, router):
        """Test routing with tight spread (should use market order)."""
        quote = Quote(
            symbol="SPY",
            bid=450.00,
            ask=450.05,  # 0.01% spread
            mid=450.025,
            last=450.03,
            bid_size=1000,
            ask_size=1000,
            timestamp=datetime.now(timezone.utc),
        )
        
        order = OrderRequest(
            asset_class=AssetClass.STOCK,
            symbol="SPY",
            side=OrderSide.BUY,
            quantity=100,
            order_type=OrderType.LIMIT,  # Will be changed by router
        )
        
        decision = router.route_order(order, quote)
        
        assert decision.order_type == OrderType.MARKET
        assert "Tight spread" in decision.reasoning
    
    def test_wide_spread_limit_order(self, router):
        """Test routing with wide spread (should use limit order)."""
        quote = Quote(
            symbol="ILLIQUID",
            bid=100.0,
            ask=105.0,  # 5% spread
            mid=102.5,
            last=102.0,
            bid_size=10,
            ask_size=10,
            timestamp=datetime.now(timezone.utc),
        )
        
        order = OrderRequest(
            asset_class=AssetClass.STOCK,
            symbol="ILLIQUID",
            side=OrderSide.BUY,
            quantity=10,
            order_type=OrderType.MARKET,  # Will be changed by router
        )
        
        decision = router.route_order(order, quote)
        
        assert decision.order_type == OrderType.LIMIT
        assert decision.limit_price is not None
        assert "Wide spread" in decision.reasoning
    
    def test_order_splitting(self, router):
        """Test order splitting for large orders."""
        quote = Quote(
            symbol="SPY",
            bid=450.0,
            ask=450.50,
            mid=450.25,
            last=450.30,
            bid_size=1000,
            ask_size=1000,
            timestamp=datetime.now(timezone.utc),
        )
        
        # Order for 20% of ADV (should be split)
        order = OrderRequest(
            asset_class=AssetClass.STOCK,
            symbol="SPY",
            side=OrderSide.BUY,
            quantity=200000,
            order_type=OrderType.MARKET,
        )
        
        decision = router.route_order(order, quote, adv=1000000.0)
        
        assert decision.split_order is True
        assert len(decision.split_quantities) > 1
        assert sum(decision.split_quantities) == 200000
        assert "split" in decision.reasoning.lower()


class TestOrderLifecycleController:
    """Test order lifecycle management."""
    
    def test_submit_order(self, simulated_broker, router, sample_quote):
        """Test order submission through controller."""
        controller = OrderLifecycleController(broker=simulated_broker, router=router)
        simulated_broker.set_quote("SPY", sample_quote)
        
        order = OrderRequest(
            asset_class=AssetClass.STOCK,
            symbol="SPY",
            side=OrderSide.BUY,
            quantity=10,
            order_type=OrderType.MARKET,
        )
        
        result = controller.submit_order(order, sample_quote)
        
        assert result.status.value == "filled"
        assert result.order_id is not None
    
    def test_active_order_tracking(self, simulated_broker, router, sample_quote):
        """Test tracking of active orders."""
        controller = OrderLifecycleController(broker=simulated_broker, router=router)
        simulated_broker.set_quote("SPY", sample_quote)
        
        # Simulated broker fills immediately, so no active orders
        # This test validates the tracking mechanism
        active = controller.get_active_orders()
        assert isinstance(active, dict)


class TestIntegration:
    """Integration tests for complete execution workflow."""
    
    def test_end_to_end_execution(self, simulated_broker, router, sample_quote):
        """Test complete execution flow from order to fill."""
        # 1. Initialize components
        controller = OrderLifecycleController(broker=simulated_broker, router=router)
        simulated_broker.set_quote("SPY", sample_quote)
        
        # 2. Create order
        order = OrderRequest(
            asset_class=AssetClass.STOCK,
            symbol="SPY",
            side=OrderSide.BUY,
            quantity=100,
            order_type=OrderType.LIMIT,
        )
        
        # 3. Submit through controller (router will optimize)
        result = controller.submit_order(order, sample_quote)
        
        # 4. Verify execution
        assert result.status.value == "filled"
        assert result.filled_quantity == 100
        
        # 5. Check account state
        account = simulated_broker.get_account()
        assert len(account.positions) == 1
        assert account.positions[0].symbol == "SPY"
        assert account.positions[0].quantity == 100
        
        # 6. Verify costs were computed
        assert result.total_cost > 0
