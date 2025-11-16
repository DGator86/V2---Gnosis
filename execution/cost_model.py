# execution/cost_model.py

"""
Execution cost modeling for Trade Agent v3.

Provides comprehensive cost estimation including:
- Bid-ask spread costs
- Slippage modeling
- Commission structures
- Market impact estimation
- Fill probability prediction
"""

from __future__ import annotations

import math
from typing import Optional

from .schemas import (
    Quote,
    ExecutionCost,
    OrderType,
    OrderSide,
    AssetClass,
)


class ExecutionCostModel:
    """
    Models execution costs for order routing decisions.
    
    Considers:
    - Bid-ask spread (immediate cost)
    - Expected slippage (aggressive orders)
    - Commissions (broker-specific)
    - Market impact (large orders)
    - Fill probability (limit orders)
    """
    
    def __init__(
        self,
        commission_per_contract: float = 0.65,
        commission_per_share: float = 0.0,
        base_slippage_pct: float = 0.001,  # 0.1%
        market_impact_coef: float = 0.0001,  # Impact per 1% of ADV
    ):
        """
        Initialize cost model.
        
        Args:
            commission_per_contract: Commission per option contract
            commission_per_share: Commission per share
            base_slippage_pct: Base slippage percentage
            market_impact_coef: Market impact coefficient
        """
        self.commission_per_contract = commission_per_contract
        self.commission_per_share = commission_per_share
        self.base_slippage_pct = base_slippage_pct
        self.market_impact_coef = market_impact_coef
    
    def estimate_cost(
        self,
        symbol: str,
        quote: Quote,
        quantity: int,
        side: OrderSide,
        asset_class: AssetClass,
        order_type: OrderType = OrderType.LIMIT,
        adv: Optional[float] = None,  # Average daily volume
    ) -> ExecutionCost:
        """
        Comprehensive cost estimation.
        
        Args:
            symbol: Ticker symbol
            quote: Current quote
            quantity: Order quantity
            side: Buy or sell
            asset_class: Stock or option
            order_type: Market or limit
            adv: Average daily volume (for market impact)
        
        Returns:
            ExecutionCost with breakdown
        """
        # 1. Bid-ask spread cost
        spread_per_unit = quote.ask - quote.bid
        bid_ask_cost = spread_per_unit * quantity / 2  # Half spread assumption
        
        # 2. Slippage (higher for market orders)
        if order_type == OrderType.MARKET:
            slippage_pct = self.base_slippage_pct * 3  # 3x for market orders
        else:
            slippage_pct = self.base_slippage_pct
        
        reference_price = quote.mid
        slippage_cost = reference_price * quantity * slippage_pct
        
        # 3. Commission
        if asset_class == AssetClass.OPTION:
            commission = quantity * self.commission_per_contract
        else:
            commission = quantity * self.commission_per_share
        
        # 4. Market impact (if ADV provided)
        market_impact = 0.0
        if adv is not None and adv > 0:
            order_pct_of_adv = quantity / adv
            # Square root model: impact = coefficient * sqrt(quantity / ADV)
            market_impact = reference_price * quantity * self.market_impact_coef * math.sqrt(order_pct_of_adv)
        
        # Total cost
        total = bid_ask_cost + slippage_cost + commission + market_impact
        
        # Cost as percentage of notional
        notional = reference_price * quantity
        cost_pct = (total / notional) if notional > 0 else 0.0
        
        # Fill probability (limit orders have lower fill probability)
        fill_prob = self._estimate_fill_probability(order_type, quote)
        
        # Recommended order type and price
        recommended_type, recommended_price = self._recommend_order_params(
            quote, side, order_type, fill_prob
        )
        
        return ExecutionCost(
            symbol=symbol,
            quantity=quantity,
            bid_ask_spread=bid_ask_cost,
            estimated_slippage=slippage_cost,
            commission=commission,
            market_impact=market_impact,
            total_cost=total,
            cost_as_pct_of_notional=cost_pct,
            fill_probability=fill_prob,
            recommended_order_type=recommended_type,
            recommended_limit_price=recommended_price,
        )
    
    def _estimate_fill_probability(
        self,
        order_type: OrderType,
        quote: Quote,
    ) -> float:
        """
        Estimate fill probability based on order type and spread.
        
        Market orders: 100% fill probability
        Limit orders: Depends on spread width
        """
        if order_type == OrderType.MARKET:
            return 1.0
        
        # For limit orders, wider spreads = lower fill probability
        spread_pct = quote.spread_pct
        
        if spread_pct < 0.01:  # <1% spread
            return 0.95
        elif spread_pct < 0.02:  # 1-2% spread
            return 0.85
        elif spread_pct < 0.05:  # 2-5% spread
            return 0.70
        else:  # >5% spread
            return 0.50
    
    def _recommend_order_params(
        self,
        quote: Quote,
        side: OrderSide,
        current_type: OrderType,
        fill_prob: float,
    ) -> tuple[OrderType, Optional[float]]:
        """
        Recommend order type and limit price based on conditions.
        
        Returns:
            Tuple of (recommended order type, recommended limit price)
        """
        # If spread is tight (<1%), market orders are acceptable
        if quote.spread_pct < 0.01:
            return OrderType.MARKET, None
        
        # Otherwise, use limit orders at midpoint
        if side == OrderSide.BUY:
            # Bid slightly above mid to improve fill probability
            limit_price = quote.mid + (quote.ask - quote.mid) * 0.25
        else:
            # Offer slightly below mid to improve fill probability
            limit_price = quote.mid - (quote.mid - quote.bid) * 0.25
        
        return OrderType.LIMIT, limit_price
    
    def compare_order_types(
        self,
        symbol: str,
        quote: Quote,
        quantity: int,
        side: OrderSide,
        asset_class: AssetClass,
    ) -> dict[OrderType, ExecutionCost]:
        """
        Compare costs across order types.
        
        Returns:
            Dictionary mapping order type to execution cost
        """
        results = {}
        
        for order_type in [OrderType.MARKET, OrderType.LIMIT]:
            cost = self.estimate_cost(
                symbol, quote, quantity, side, asset_class, order_type
            )
            results[order_type] = cost
        
        return results
