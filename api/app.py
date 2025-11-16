"""
Super Gnosis FastAPI Application.

Production-ready API for real-time market directive composition.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from api import composer_service, trade_agent_service

# Create FastAPI app
app = FastAPI(
    title="Super Gnosis API",
    description="""
    Real-time market reasoning system powered by regime-aware, energy-conscious fusion.
    
    **Architecture**:
    - 3 independent engines (Hedge, Liquidity, Sentiment)
    - 3 agent wrappers (normalize outputs to EngineDirective)
    - 1 Composer (fuses signals with regime-based weighting)
    
    **Key Features**:
    - Regime-aware weighting (jump/vacuum/trend regimes favor different engines)
    - Energy-conscious (models resistance to price movement)
    - Conflict resolution (weighted voting when engines disagree)
    - Multi-horizon projections (15m/1h/1d expected move cones)
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware for browser access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(composer_service.router)
app.include_router(trade_agent_service.router)

@app.get("/", include_in_schema=False)
def root():
    """Redirect root to API docs."""
    return RedirectResponse(url="/docs")


@app.get("/health", tags=["system"])
def system_health():
    """System-level health check."""
    return {
        "status": "ok",
        "service": "Super Gnosis API",
        "version": "1.0.0",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
