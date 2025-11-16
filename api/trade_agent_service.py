# api/trade_agent_service.py

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query

from agents.composer.schemas import CompositeMarketDirective
from agents.trade_agent import TradeAgentV2, TradeIdea, StrategyType
from agents.trade_agent.composer_adapter import directive_to_context
from agents.trade_agent.schemas import Timeframe


router = APIRouter(prefix="/trade-agent", tags=["trade-agent"])


def get_trade_agent() -> TradeAgentV2:
    """Dependency injection for Trade Agent instance."""
    return TradeAgentV2()


@router.post("/generate", response_model=List[TradeIdea])
def generate_trades(
    directive: CompositeMarketDirective,
    asset: str = Query(..., description="Symbol/ticker for the trade ideas"),
    underlying_price: float = Query(..., description="Current underlying price"),
    capital: float | None = Query(None, description="Optional capital for sizing (default: 10000)"),
    timeframe: Timeframe | None = Query(None, description="Optional timeframe override"),
    agent: TradeAgentV2 = Depends(get_trade_agent),
) -> List[TradeIdea]:
    """
    Generate a ranked list of trade ideas from a CompositeMarketDirective.
    
    This endpoint consumes the output of the Composer Agent and produces
    actionable trade ideas (stock and options strategies).
    
    Args:
        directive: CompositeMarketDirective from Composer
        asset: Symbol (e.g., "SPY", "AAPL")
        underlying_price: Current price of underlying
        capital: Optional capital for sizing calculations
        timeframe: Optional timeframe override
        
    Returns:
        List of TradeIdea objects ranked by score
        
    Example:
        ```
        POST /trade-agent/generate?asset=SPY&underlying_price=450.0
        {
            "direction": 1,
            "strength": 65.0,
            "confidence": 0.75,
            "volatility": 45.0,
            "energy_cost": 1.2,
            "trade_style": "momentum",
            ...
        }
        ```
    """
    try:
        ctx = directive_to_context(
            directive=directive,
            asset=asset,
            timeframe=timeframe,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to convert directive to context: {exc}"
        ) from exc
    
    try:
        ideas = agent.generate_trade_ideas(
            ctx=ctx,
            underlying_price=underlying_price,
            capital=capital,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Trade idea generation failed: {exc}"
        ) from exc
    
    return ideas


@router.get("/strategies", response_model=List[str])
def list_strategies() -> List[str]:
    """
    List all available strategy types.
    
    Returns:
        List of strategy type names
    """
    return [s.value for s in StrategyType]


@router.get("/health")
def health() -> dict:
    """
    Health check for Trade Agent service.
    
    Returns:
        Status dictionary
    """
    return {
        "status": "ok",
        "component": "trade_agent_v2",
        "version": "2.0.0",
    }
