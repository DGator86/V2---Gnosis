# execution/router.py

"""
Smart order router for Trade Agent v3.

Intelligent routing logic that:
- Chooses optimal order type (market/limit)
- Splits large orders to minimize market impact
- Provides peg-to-mid pricing for options
- Adapts routing based on market conditions
"""

from __future__ import annotations

from typing import Optional, List

from .schemas import (
    OrderRequest,
    OrderType,
    OrderSide,
    TimeInForce,
    RoutingDecision,
    Quote,
    AssetClass,
)
from .cost_model import ExecutionCostModel


class SmartOrderRouter:
    """
    Intelligent order routing engine.
    
    Makes routing decisions based on:
    - Execution cost analysis
    - Fill probability
    - Order size relative to liquidity
    - Asset class (stocks vs options)
    """
    
    def __init__(
        self,
        cost_model: Optional[ExecutionCostModel] = None,
        max_order_pct_of_adv: float = 0.10,  # Max 10% of ADV
        spread_threshold_for_market: float = 0.01,  # <1% spread = market ok
    ):
        """
        Initialize smart router.
        
        Args:
            cost_model: ExecutionCostModel for cost analysis
            max_order_pct_of_adv: Max order size as % of ADV before splitting
            spread_threshold_for_market: Max spread % for market orders
        """
        self.cost_model = cost_model or ExecutionCostModel()
        self.max_order_pct_of_adv = max_order_pct_of_adv
        self.spread_threshold_for_market = spread_threshold_for_market
    
    def route_order(
        self,
        order: OrderRequest,
        quote: Quote,
        adv: Optional[float] = None,
    ) -> RoutingDecision:
        """
        Make intelligent routing decision for an order.
        
        Args:
            order: Order request
            quote: Current quote
            adv: Average daily volume (optional)
        
        Returns:
            RoutingDecision with routing parameters
        """
        # Analyze execution costs for different order types
        costs = self.cost_model.compare_order_types(
            order.symbol,
            quote,
            order.quantity,
            order.side,
            order.asset_class,
        )
        
        # Decision logic
        market_cost = costs[OrderType.MARKET]
        limit_cost = costs[OrderType.LIMIT]
        
        # 1. Check if order should be split
        split_order = False
        split_quantities: List[int] = []
        
        if adv is not None and adv > 0:
            order_pct = order.quantity / adv
            if order_pct > self.max_order_pct_of_adv:
                split_order = True
                # Split into chunks of max_order_pct_of_adv
                chunk_size = int(adv * self.max_order_pct_of_adv)
                num_chunks = (order.quantity + chunk_size - 1) // chunk_size
                split_quantities = [chunk_size] * (num_chunks - 1)
                split_quantities.append(order.quantity - sum(split_quantities))
        
        # 2. Choose order type
        # Use market if spread is tight and we need certainty
        if quote.spread_pct < self.spread_threshold_for_market:
            order_type = OrderType.MARKET
            limit_price = None
            reasoning = f"Tight spread ({quote.spread_pct:.2%}) favors market order"
        else:
            # Use limit order with peg-to-mid pricing
            order_type = OrderType.LIMIT
            
            # Peg to midpoint, adjusted for fill probability
            if order.side == OrderSide.BUY:
                # Bid slightly aggressive to improve fill
                limit_price = quote.mid + (quote.ask - quote.mid) * 0.2
            else:
                # Offer slightly aggressive to improve fill
                limit_price = quote.mid - (quote.mid - quote.bid) * 0.2
            
            reasoning = f"Wide spread ({quote.spread_pct:.2%}) requires limit order at ${limit_price:.2f}"
        
        # 3. Add split order reasoning
        if split_order:
            reasoning += f" | Order split into {len(split_quantities)} chunks to minimize market impact"
        
        return RoutingDecision(
            order_type=order_type,
            limit_price=limit_price,
            time_in_force=TimeInForce.DAY,
            split_order=split_order,
            split_quantities=split_quantities,
            reasoning=reasoning,
        )
    
    def get_optimal_limit_price(
        self,
        quote: Quote,
        side: OrderSide,
        aggressiveness: float = 0.2,
    ) -> float:
        """
        Calculate optimal limit price.
        
        Args:
            quote: Current quote
            side: Buy or sell
            aggressiveness: How aggressive (0=passive, 1=aggressive)
        
        Returns:
            Optimal limit price
        """
        if side == OrderSide.BUY:
            # Interpolate between bid and ask
            return quote.bid + (quote.ask - quote.bid) * aggressiveness
        else:
            # Interpolate between ask and bid
            return quote.ask - (quote.ask - quote.bid) * aggressiveness
