# execution/schemas.py

"""
Execution layer data schemas for Trade Agent v3.

Defines order requests, execution results, account info, positions,
quotes, and execution costs using Pydantic v2.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, ConfigDict


class OrderType(str, Enum):
    """Order type classification."""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class OrderSide(str, Enum):
    """Order side (buy/sell)."""
    BUY = "buy"
    SELL = "sell"


class OrderStatus(str, Enum):
    """Order execution status."""
    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIAL_FILL = "partial_fill"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class TimeInForce(str, Enum):
    """Order time-in-force."""
    DAY = "day"
    GTC = "gtc"  # Good till cancelled
    IOC = "ioc"  # Immediate or cancel
    FOK = "fok"  # Fill or kill


class AssetClass(str, Enum):
    """Asset class for trading."""
    STOCK = "stock"
    OPTION = "option"
    CRYPTO = "crypto"


class OptionLeg(BaseModel):
    """Single option leg in a multi-leg order."""
    model_config = ConfigDict(frozen=False)
    
    symbol: str = Field(description="Option symbol (OCC format)")
    side: OrderSide
    quantity: int = Field(gt=0)
    option_type: str = Field(description="'call' or 'put'")
    strike: float = Field(gt=0)
    expiry: str = Field(description="Expiry date (ISO format)")


class OrderRequest(BaseModel):
    """
    Unified order request structure for all brokers.
    
    Supports single-leg (stock/option) and multi-leg (spreads) orders.
    """
    model_config = ConfigDict(frozen=False)
    
    asset_class: AssetClass
    symbol: str
    side: OrderSide
    quantity: int = Field(gt=0)
    order_type: OrderType = OrderType.LIMIT
    time_in_force: TimeInForce = TimeInForce.DAY
    
    # Pricing
    limit_price: Optional[float] = Field(default=None, gt=0)
    stop_price: Optional[float] = Field(default=None, gt=0)
    
    # Multi-leg support
    legs: List[OptionLeg] = Field(default_factory=list)
    
    # Execution preferences
    allow_partial_fills: bool = True
    max_slippage_pct: Optional[float] = Field(default=0.02, description="Max allowed slippage (2% default)")
    
    # Metadata
    strategy_id: Optional[str] = None
    notes: Optional[str] = None


class Fill(BaseModel):
    """Individual fill for an order."""
    model_config = ConfigDict(frozen=False)
    
    fill_id: str
    quantity: int = Field(gt=0)
    price: float = Field(gt=0)
    timestamp: datetime
    commission: float = 0.0


class OrderResult(BaseModel):
    """
    Result of order submission/execution.
    
    Contains order ID, status, fills, and execution details.
    """
    model_config = ConfigDict(frozen=False)
    
    order_id: str
    status: OrderStatus
    broker: str
    
    # Order details
    symbol: str
    side: OrderSide
    quantity: int
    order_type: OrderType
    
    # Execution details
    filled_quantity: int = 0
    avg_fill_price: Optional[float] = None
    fills: List[Fill] = Field(default_factory=list)
    
    # Cost breakdown
    total_cost: float = 0.0
    total_commission: float = 0.0
    estimated_slippage: float = 0.0
    
    # Timestamps
    submitted_at: Optional[datetime] = None
    filled_at: Optional[datetime] = None
    
    # Error handling
    error_message: Optional[str] = None


class Position(BaseModel):
    """Current position for an asset."""
    model_config = ConfigDict(frozen=False)
    
    symbol: str
    asset_class: AssetClass
    quantity: int  # Can be negative for shorts
    avg_entry_price: float
    current_price: float
    market_value: float
    unrealized_pnl: float
    realized_pnl: float = 0.0


class AccountInfo(BaseModel):
    """Broker account information."""
    model_config = ConfigDict(frozen=False)
    
    account_id: str
    broker: str
    cash: float = Field(ge=0)
    buying_power: float = Field(ge=0)
    portfolio_value: float = Field(ge=0)
    equity: float = Field(ge=0)
    margin_used: float = Field(ge=0)
    positions: List[Position] = Field(default_factory=list)


class Quote(BaseModel):
    """Real-time quote for an asset."""
    model_config = ConfigDict(frozen=False)
    
    symbol: str
    bid: float = Field(ge=0)  # Allow 0 when market is closed
    ask: float = Field(ge=0)  # Allow 0 when market is closed
    mid: float = Field(ge=0)  # Allow 0 when market is closed
    last: float = Field(ge=0)  # Allow 0 when market is closed
    bid_size: int = Field(ge=0, default=0)
    ask_size: int = Field(ge=0, default=0)
    timestamp: datetime
    
    @property
    def spread_pct(self) -> float:
        """Bid-ask spread as percentage of mid."""
        if self.mid == 0:
            return 0.0
        return (self.ask - self.bid) / self.mid


class ExecutionCost(BaseModel):
    """
    Comprehensive execution cost breakdown.
    
    Includes bid-ask spread, estimated slippage, commissions,
    and market impact for cost-aware order routing.
    """
    model_config = ConfigDict(frozen=False)
    
    symbol: str
    quantity: int
    
    # Cost components
    bid_ask_spread: float = Field(ge=0, description="Bid-ask spread in dollars")
    estimated_slippage: float = Field(ge=0, description="Expected slippage in dollars")
    commission: float = Field(ge=0, description="Broker commission")
    market_impact: float = Field(ge=0, description="Estimated market impact")
    
    # Totals
    total_cost: float = Field(ge=0, description="Sum of all costs")
    cost_as_pct_of_notional: float = Field(ge=0, description="Total cost as % of order notional")
    
    # Fill probability
    fill_probability: float = Field(ge=0, le=1.0, description="Estimated fill probability (0-1)")
    
    # Recommendations
    recommended_order_type: OrderType = OrderType.LIMIT
    recommended_limit_price: Optional[float] = None


class RoutingDecision(BaseModel):
    """Smart router decision for an order."""
    model_config = ConfigDict(frozen=False)
    
    order_type: OrderType
    limit_price: Optional[float] = None
    time_in_force: TimeInForce = TimeInForce.DAY
    split_order: bool = False
    split_quantities: List[int] = Field(default_factory=list)
    reasoning: str = ""
