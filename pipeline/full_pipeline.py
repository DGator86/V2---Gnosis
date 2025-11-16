# pipeline/full_pipeline.py

"""
Full Pipeline Orchestration

Wires together:
  Engines (Hedge, Liquidity, Sentiment) → Composer → Trade Agent → Execution

DI-friendly, function-based, and side-effect-free except for I/O.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Protocol

from agents.hedge_agent_v3 import HedgeAgentV3
from agents.liquidity_agent_v1 import LiquidityAgentV1
from agents.sentiment_agent_v1 import SentimentAgentV1
from agents.composer.composer_agent import ComposerAgent
from agents.trade_agent.trade_agent_v2 import TradeAgentV2
from agents.trade_agent.schemas import TradeIdea, ComposerTradeContext

from execution.broker_adapters.simulated_adapter import SimulatedBrokerAdapter
from execution.schemas import OrderRequest, OrderResult, OrderSide, AssetClass

from optimizer.kelly_refinement import recommended_risk_fraction


# ============================================================
# PROTOCOLS
# ============================================================

class BrokerAdapter(Protocol):
    """Protocol for broker adapters."""
    def place_order(self, order: OrderRequest) -> OrderResult: ...


class HyperparameterProvider(Protocol):
    """Protocol for hyperparameter providers."""
    def get_best_params(self, symbol: str, regime: Dict[str, str]) -> Dict[str, Any]: ...


class PredictionModel(Protocol):
    """Protocol for ML prediction models."""
    def predict(self, features: Dict[str, float]) -> Dict[str, float]: ...


# ============================================================
# PIPELINE COMPONENTS
# ============================================================

@dataclass
class PipelineComponents:
    """
    Container for all pipeline components.
    
    DI-friendly: construct once, pass to run_full_pipeline_for_symbol().
    """
    # Agents (replace with engines when available)
    hedge_agent: HedgeAgentV3
    liquidity_agent: LiquidityAgentV1
    sentiment_agent: SentimentAgentV1
    composer_agent: ComposerAgent
    trade_agent: TradeAgentV2
    
    # Execution
    broker: BrokerAdapter
    
    # Optional extensions
    hyperparam_provider: Optional[HyperparameterProvider] = None
    prediction_model: Optional[PredictionModel] = None
    
    # Config
    config: Optional[Dict[str, Any]] = None


def build_default_pipeline_components(
    config: Optional[Dict[str, Any]] = None,
    broker: Optional[BrokerAdapter] = None,
    hyperparam_provider: Optional[HyperparameterProvider] = None,
    prediction_model: Optional[PredictionModel] = None,
) -> PipelineComponents:
    """
    Build default pipeline components with sensible defaults.
    
    Args:
        config: Optional configuration dict
        broker: Optional broker adapter (defaults to SimulatedBrokerAdapter)
        hyperparam_provider: Optional hyperparameter provider
        prediction_model: Optional ML prediction model
    
    Returns:
        PipelineComponents ready for pipeline execution
    """
    if config is None:
        config = {}
    
    # Create agents (will be replaced with engines eventually)
    hedge_agent = HedgeAgentV3(config=config.get("hedge", {}))
    liquidity_agent = LiquidityAgentV1(config=config.get("liquidity", {}))
    sentiment_agent = SentimentAgentV1(config=config.get("sentiment", {}))
    
    # Composer needs agents and reference price getter
    def get_reference_price() -> float:
        return 450.0  # Placeholder - would come from market data in production
    
    composer_agent = ComposerAgent(
        hedge_agent=hedge_agent,
        liquidity_agent=liquidity_agent,
        sentiment_agent=sentiment_agent,
        reference_price_getter=get_reference_price,
    )
    
    # Trade agent
    trade_agent = TradeAgentV2(
        default_capital=config.get("default_capital", 100_000.0)
    )
    
    # Broker
    if broker is None:
        broker = SimulatedBrokerAdapter(
            initial_cash=config.get("initial_cash", 100_000.0),
            slippage_pct=config.get("slippage_pct", 0.001),
            commission_per_contract=config.get("commission_per_contract", 0.65),
        )
    
    return PipelineComponents(
        hedge_agent=hedge_agent,
        liquidity_agent=liquidity_agent,
        sentiment_agent=sentiment_agent,
        composer_agent=composer_agent,
        trade_agent=trade_agent,
        broker=broker,
        hyperparam_provider=hyperparam_provider,
        prediction_model=prediction_model,
        config=config,
    )


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def _infer_regime_key(composer_context: ComposerTradeContext) -> Dict[str, str]:
    """Infer regime classification from composer context."""
    # Map context to regime buckets
    vol_regime = composer_context.volatility_regime.value if composer_context.volatility_regime else "mid"
    
    # Infer VIX bucket from vol regime
    vix_bucket = "low" if vol_regime == "vol_crush" else "high" if vol_regime == "vol_expansion" else "mid"
    
    # Infer trend from direction
    trend_bucket = "up" if composer_context.direction.value == "bullish" else "down" if composer_context.direction.value == "bearish" else "neutral"
    
    # Infer dealer positioning from gamma exposure
    dealer_bucket = "short_gamma" if composer_context.gamma_exposure < -0.5 else "long_gamma" if composer_context.gamma_exposure > 0.5 else "neutral"
    
    # Infer liquidity from score
    liquidity_bucket = "high" if composer_context.liquidity_score > 0.7 else "low" if composer_context.liquidity_score < 0.3 else "mid"
    
    return {
        "vix_bucket": vix_bucket,
        "trend_bucket": trend_bucket,
        "dealer_bucket": dealer_bucket,
        "liquidity_bucket": liquidity_bucket,
    }


def _apply_ml_and_kelly_sizing(
    trade_ideas: List[TradeIdea],
    composer_context: ComposerTradeContext,
    prediction_model: Optional[PredictionModel],
) -> List[TradeIdea]:
    """
    Apply ML predictions and Kelly sizing to trade ideas.
    
    Args:
        trade_ideas: List of trade ideas
        composer_context: Composer context with market state
        prediction_model: Optional ML model
    
    Returns:
        Updated trade ideas with adjusted sizing
    """
    if not prediction_model or not trade_ideas:
        return trade_ideas
    
    # Build features from context
    features = {
        "confidence": composer_context.confidence,
        "elastic_energy": composer_context.elastic_energy,
        "gamma_exposure": composer_context.gamma_exposure,
        "vanna_exposure": composer_context.vanna_exposure,
        "charm_exposure": composer_context.charm_exposure,
        "liquidity_score": composer_context.liquidity_score,
    }
    
    # Get ML prediction
    prediction = prediction_model.predict(features)
    ml_confidence = prediction.get("prob_up", composer_context.confidence)
    
    # Use regime-based Kelly sizing
    empirical_win_rate = prediction.get("win_rate", 0.55)
    avg_win = prediction.get("avg_win", 1.0)
    avg_loss = prediction.get("avg_loss", 1.0)
    
    risk_fraction = recommended_risk_fraction(
        empirical_win_rate=empirical_win_rate,
        avg_win=avg_win,
        avg_loss=avg_loss,
        confidence=ml_confidence,
        global_risk_cap=0.02,
    )
    
    # Apply to all ideas
    updated: List[TradeIdea] = []
    for idea in trade_ideas:
        # Create updated copy with risk fraction
        # (assumes TradeIdea is immutable or we create new instance)
        updated.append(idea)
        
        # TODO: Apply risk_fraction to idea.recommended_size
        # This would require modifying TradeIdea or creating wrapper
    
    return updated


def _convert_trade_ideas_to_orders(trade_ideas: List[TradeIdea]) -> List[OrderRequest]:
    """
    Convert trade ideas into executable order requests.
    
    Args:
        trade_ideas: List of trade ideas
    
    Returns:
        List of order requests
    """
    orders: List[OrderRequest] = []
    
    for idea in trade_ideas:
        for leg in idea.legs:
            # Build order request from leg
            order = OrderRequest(
                symbol=f"{idea.asset}_{leg.option_type[0].upper()}{leg.strike}_{leg.expiry}",
                side=OrderSide.BUY if leg.side == "long" else OrderSide.SELL,
                quantity=leg.quantity,
                asset_class=AssetClass.OPTION,
            )
            orders.append(order)
    
    return orders


def execute_trade_ideas(
    trade_ideas: List[TradeIdea],
    broker: BrokerAdapter,
    mode: Literal["paper", "live"] = "paper",
) -> List[OrderResult]:
    """
    Execute trade ideas through broker adapter.
    
    Args:
        trade_ideas: List of trade ideas to execute
        broker: Broker adapter
        mode: Execution mode (paper or live)
    
    Returns:
        List of order results
    """
    orders = _convert_trade_ideas_to_orders(trade_ideas)
    
    results: List[OrderResult] = []
    for order in orders:
        result = broker.place_order(order)
        results.append(result)
    
    return results


# ============================================================
# MAIN PIPELINE FUNCTION
# ============================================================

def run_full_pipeline_for_symbol(
    symbol: str,
    as_of: datetime,
    components: PipelineComponents,
    mode: Literal["paper", "live"] = "paper",
    execute: bool = False,
    underlying_price: Optional[float] = None,
    capital: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Run full pipeline for a symbol.
    
    Orchestrates:
      1. Data ingestion (placeholder - would fetch real data)
      2. Agent execution (hedge, liquidity, sentiment)
      3. Composer fusion
      4. Trade generation
      5. ML enhancement (if available)
      6. Optional execution
    
    Args:
        symbol: Trading symbol (e.g., "SPY")
        as_of: Timestamp for pipeline execution
        components: Pipeline components (agents, broker, etc.)
        mode: Execution mode ("paper" or "live")
        execute: Whether to execute trades
        underlying_price: Optional underlying price (defaults to 450.0)
        capital: Optional capital allocation (defaults to 100k)
    
    Returns:
        Dictionary with:
            - symbol: str
            - as_of: datetime
            - composer_context: ComposerTradeContext
            - trade_ideas: List[TradeIdea]
            - order_results: List[OrderResult]
    """
    # 1) Data ingestion (placeholder - in production would fetch from market data adapter)
    if underlying_price is None:
        underlying_price = 450.0
    
    if capital is None:
        capital = 100_000.0
    
    # 2) Run agents
    # Note: In current architecture, agents maintain internal state
    # In production, would pass market data snapshots here
    
    # 3) Get composer output
    # ComposerAgent.compose() returns CompositeMarketDirective
    # We need to call it with the current market state
    
    # For now, create a placeholder context directly
    # (In production, ComposerAgent would generate this from agent outputs)
    from agents.trade_agent.schemas import (
        Direction,
        ExpectedMove,
        VolatilityRegime,
        Timeframe,
    )
    
    composer_context = ComposerTradeContext(
        asset=symbol,
        direction=Direction.BULLISH,  # Would come from composer
        confidence=0.7,
        expected_move=ExpectedMove.MEDIUM,
        volatility_regime=VolatilityRegime.MID,
        timeframe=Timeframe.SWING,
        elastic_energy=1.0,
        gamma_exposure=0.0,
        vanna_exposure=0.0,
        charm_exposure=0.0,
        liquidity_score=0.8,
    )
    
    # 4) Get regime-based hyperparameters (if provider exists)
    hyperparams: Dict[str, Any] = {}
    if components.hyperparam_provider is not None:
        regime_key = _infer_regime_key(composer_context)
        hyperparams = components.hyperparam_provider.get_best_params(symbol, regime_key)
    
    # 5) Generate trade ideas
    trade_ideas = components.trade_agent.generate_trade_ideas(
        ctx=composer_context,
        underlying_price=underlying_price,
        capital=capital,
    )
    
    # 6) Apply ML predictions and Kelly sizing (if model exists)
    trade_ideas = _apply_ml_and_kelly_sizing(
        trade_ideas=trade_ideas,
        composer_context=composer_context,
        prediction_model=components.prediction_model,
    )
    
    # 7) Optional execution
    order_results: List[OrderResult] = []
    if execute:
        order_results = execute_trade_ideas(
            trade_ideas=trade_ideas,
            broker=components.broker,
            mode=mode,
        )
    
    return {
        "symbol": symbol,
        "as_of": as_of,
        "composer_context": composer_context,
        "trade_ideas": trade_ideas,
        "order_results": order_results,
        "hyperparams": hyperparams,
    }
