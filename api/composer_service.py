"""
Composer API Service - FastAPI router for real-time market directive composition.

Exposes two main endpoints:
- GET /composer/directive: Clean CompositeMarketDirective for trade systems
- GET /composer/snapshot: Full transparency with engine directives and weights
"""

from datetime import datetime, timezone
from typing import Callable, Dict, Any, Tuple

from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import JSONResponse

from agents.composer.composer_agent import ComposerAgent
from agents.composer.schemas import EngineDirective
from agents.hedge_agent_v3 import HedgeAgentV3
from agents.liquidity_agent_v1 import LiquidityAgentV1
from agents.sentiment_agent_v1 import SentimentAgentV1
from api.schemas_composer import (
    ComposerDirectiveResponse,
    ComposerSnapshotResponse,
    CompositeDirectiveView,
    EngineDirectiveView,
    RegimeWeightsView,
    HealthCheckResponse,
)
from config import AppConfig, load_config
from engines.hedge.hedge_engine_v3 import HedgeEngineV3
from engines.liquidity.liquidity_engine_v1 import LiquidityEngineV1
from engines.sentiment.sentiment_engine_v1_full import SentimentEngineV1
from engines.inputs.stub_adapters import (
    StaticMarketDataAdapter,
    StaticOptionsAdapter,
)

router = APIRouter(prefix="/composer", tags=["composer"])

# Global state for engines (initialized on first request)
_engines_cache: Dict[str, Any] = {}
_config_cache: AppConfig | None = None


# ============================================================================
# DEPENDENCY INJECTION
# ============================================================================

def get_config() -> AppConfig:
    """Get or load application configuration."""
    global _config_cache
    if _config_cache is None:
        _config_cache = load_config()
    return _config_cache


def get_price_from_adapter(symbol: str) -> float:
    """
    Get current price for symbol.
    
    TODO: Wire to real market data adapter (Polygon, Tradier, IB, etc.)
    For now, uses mock data from stub adapter.
    """
    # For production, replace with:
    # market_adapter = get_market_adapter()
    # data = market_adapter.fetch_ohlcv(symbol, lookback=1, now=datetime.now())
    # return float(data["close"][-1])
    
    # Mock for now
    mock_prices = {
        "SPY": 500.0,
        "QQQ": 400.0,
        "AAPL": 180.0,
        "TSLA": 250.0,
    }
    return mock_prices.get(symbol.upper(), 100.0)


def build_engines(config: AppConfig) -> Tuple[HedgeEngineV3, LiquidityEngineV1, SentimentEngineV1]:
    """
    Construct engine instances with adapters and configuration.
    
    This is cached globally to avoid re-initializing engines on every request.
    """
    global _engines_cache
    
    if not _engines_cache:
        # Create adapters
        # TODO: Replace with real adapters for production
        options_adapter = StaticOptionsAdapter()
        market_adapter = StaticMarketDataAdapter()
        
        # Create engines
        hedge_engine = HedgeEngineV3(
            adapter=options_adapter,
            config=config.engines.hedge.model_dump(),
        )
        
        liquidity_engine = LiquidityEngineV1(
            adapter=market_adapter,
            config=config.engines.liquidity.model_dump(),
        )
        
        sentiment_engine = SentimentEngineV1(
            market_adapter=market_adapter,
            config=None,  # Uses defaults
        )
        
        _engines_cache = {
            "hedge": hedge_engine,
            "liquidity": liquidity_engine,
            "sentiment": sentiment_engine,
        }
    
    return (
        _engines_cache["hedge"],
        _engines_cache["liquidity"],
        _engines_cache["sentiment"],
    )


def build_agents(
    config: AppConfig,
    hedge_engine: HedgeEngineV3,
    liquidity_engine: LiquidityEngineV1,
    sentiment_engine: SentimentEngineV1,
) -> Tuple[HedgeAgentV3, LiquidityAgentV1, SentimentAgentV1]:
    """
    Construct agent instances with engines.
    
    Agents are stateless wrappers around engines, so we rebuild them per request.
    """
    hedge_agent = HedgeAgentV3(config.engines.hedge.model_dump())
    liquidity_agent = LiquidityAgentV1(config.engines.liquidity.model_dump())
    sentiment_agent = SentimentAgentV1(config.engines.sentiment.model_dump())
    
    return hedge_agent, liquidity_agent, sentiment_agent


def get_composer_stack(
    symbol: str,
    config: AppConfig = Depends(get_config),
) -> Tuple[ComposerAgent, HedgeAgentV3, LiquidityAgentV1, SentimentAgentV1]:
    """
    High-level factory for Composer wired to real agents + engines.
    
    Returns:
        (composer, hedge_agent, liquidity_agent, sentiment_agent)
    """
    # Build/get engines (cached)
    hedge_engine, liquidity_engine, sentiment_engine = build_engines(config)
    
    # Build agents (fresh per request)
    hedge_agent, liquidity_agent, sentiment_agent = build_agents(
        config, hedge_engine, liquidity_engine, sentiment_engine
    )
    
    # Create price getter
    def price_getter() -> float:
        return get_price_from_adapter(symbol)
    
    # Build composer
    composer = ComposerAgent(
        hedge_agent=hedge_agent,
        liquidity_agent=liquidity_agent,
        sentiment_agent=sentiment_agent,
        reference_price_getter=price_getter,
    )
    
    return composer, hedge_agent, liquidity_agent, sentiment_agent


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get(
    "/health",
    response_model=HealthCheckResponse,
    summary="Health check for Composer API",
)
def health_check(config: AppConfig = Depends(get_config)):
    """
    Check if Composer API is healthy and engines are loaded.
    """
    try:
        engines_loaded = bool(_engines_cache)
        
        return HealthCheckResponse(
            status="ok",
            version="1.0.0",
            engines_loaded=engines_loaded,
            message="Composer API operational",
        )
    except Exception as e:
        return HealthCheckResponse(
            status="error",
            version="1.0.0",
            engines_loaded=False,
            message=str(e),
        )


@router.get(
    "/directive",
    response_model=ComposerDirectiveResponse,
    summary="Get composite market directive for a symbol",
    description="""
    Run all three engines (Hedge, Liquidity, Sentiment), compose their outputs,
    and return a unified CompositeMarketDirective.
    
    This is the primary endpoint for trade systems that need actionable signals.
    """,
)
def get_composite_directive(
    symbol: str = Query(..., description="Ticker symbol (e.g., 'SPY', 'AAPL')"),
    composer_stack: Tuple = Depends(get_composer_stack),
):
    """
    Get clean CompositeMarketDirective for a symbol.
    
    Returns:
        - direction: -1 (short), 0 (neutral), 1 (long)
        - strength: 0-100 scaled conviction
        - confidence: 0-1 fusion quality
        - trade_style: momentum, breakout, mean_revert, or no_trade
        - expected_move_cone: Multi-horizon projections
    """
    composer, hedge_agent, liquidity_agent, sentiment_agent = composer_stack
    
    try:
        now = datetime.now(timezone.utc)
        
        # Run engines
        # Note: For real production, you'd pass symbol and now to engines
        # For now with static adapters, engines return fixed data
        hedge_output = hedge_agent._hedge_agent_v3__engine.run(symbol, now) if hasattr(hedge_agent, f"_{hedge_agent.__class__.__name__}__engine") else None
        liquidity_output = liquidity_agent._liquidity_agent_v1__engine.run(symbol, now) if hasattr(liquidity_agent, f"_{liquidity_agent.__class__.__name__}__engine") else None
        sentiment_envelope = sentiment_agent._sentiment_agent_v1__engine.process(symbol, now) if hasattr(sentiment_agent, f"_{sentiment_agent.__class__.__name__}__engine") else None
        
        # For MVP with static adapters, create mock engine outputs
        if hedge_output is None or liquidity_output is None or sentiment_envelope is None:
            raise HTTPException(
                status_code=501,
                detail="Engine execution not fully wired yet. Need real adapters or engine injection.",
            )
        
        # Set agent outputs
        hedge_agent.set_engine_output(hedge_output)
        liquidity_agent.set_engine_output(liquidity_output)
        sentiment_agent.set_sentiment_envelope(sentiment_envelope)
        
        # Compose
        composite = composer.compose()
        
        return ComposerDirectiveResponse(
            symbol=symbol,
            timestamp=now.isoformat(),
            composite=CompositeDirectiveView.from_composite_directive(composite),
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to compose directive: {str(e)}",
        )


@router.get(
    "/snapshot",
    response_model=ComposerSnapshotResponse,
    summary="Get full Composer snapshot with engine breakdown",
    description="""
    Same as /directive, but returns additional detail:
    - Individual engine directives (hedge, liquidity, sentiment)
    - Regime-based engine weights
    - Feature availability status
    
    Use this for debugging, analysis, and dashboard visualization.
    """,
)
def get_composer_snapshot(
    symbol: str = Query(..., description="Ticker symbol (e.g., 'SPY', 'AAPL')"),
    composer_stack: Tuple = Depends(get_composer_stack),
):
    """
    Get full Composer snapshot with transparency into fusion logic.
    
    Returns:
        - composite: Full CompositeMarketDirective
        - engines: Individual EngineDirective from each engine
        - regime_weights: Breakdown of how engines were weighted
        - raw_features_available: Whether raw feature dict is cached
    """
    composer, hedge_agent, liquidity_agent, sentiment_agent = composer_stack
    
    try:
        now = datetime.now(timezone.utc)
        
        # Similar engine execution as above
        # TODO: Wire real engine execution once adapters are production-ready
        raise HTTPException(
            status_code=501,
            detail="Snapshot endpoint requires engine wiring completion. Check back after adapters are configured.",
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate snapshot: {str(e)}",
        )


# ============================================================================
# UTILITY ENDPOINTS
# ============================================================================

@router.get(
    "/supported-symbols",
    summary="List supported ticker symbols",
)
def get_supported_symbols():
    """
    List ticker symbols currently supported by the Composer.
    
    For production, this would query your universe/watchlist.
    """
    return {
        "symbols": ["SPY", "QQQ", "AAPL", "TSLA", "MSFT", "NVDA"],
        "note": "Expand this list by configuring real market data adapters",
    }
