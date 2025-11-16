"""
Hedge Agent FastAPI Service

Microservice endpoint for the Hedge Agent interpreter.
Exposes POST /hedge-agent/interpret for stateless interpretation.
"""

from fastapi import APIRouter, Depends

from .agent import HedgeAgent
from .schemas import HedgeAgentInput, HedgeAgentOutput

router = APIRouter(prefix="/hedge-agent", tags=["hedge-agent"])


def get_hedge_agent() -> HedgeAgent:
    """
    Dependency injection factory for HedgeAgent.
    
    In the future, you can inject config, logging, or telemetry here.
    For now, returns a default-configured agent.
    
    Returns:
        Configured HedgeAgent instance
    """
    return HedgeAgent()


@router.post("/interpret", response_model=HedgeAgentOutput)
def interpret_hedge_fields(
    payload: HedgeAgentInput,
    agent: HedgeAgent = Depends(get_hedge_agent),
) -> HedgeAgentOutput:
    """
    Interpret Hedge Engine pressure fields into normalized directional signal.
    
    This is a pure function from HedgeAgentInput → HedgeAgentOutput, exposed
    as an HTTP endpoint for consumption by the Composer.
    
    Args:
        payload: HedgeAgentInput with all pre-computed pressure fields
        agent: Injected HedgeAgent instance
        
    Returns:
        HedgeAgentOutput with direction, strength, confidence
    
    Example:
        ```python
        import requests
        
        response = requests.post(
            "http://localhost:8000/hedge-agent/interpret",
            json={
                "net_pressure": 0.5,
                "pressure_mtf": {},
                "gamma_curvature": 0.8,
                "vanna_drift": 0.2,
                "charm_decay": 0.1,
                "cross_gamma": 0.4,
                "volatility_drag": 0.3,
                "regime": "quadratic",
                "energy": 150.0,
                "confidence": 0.85,
                "realized_move_score": 0.2,
                "cross_asset_pressure": 0.1,
            }
        )
        
        result = response.json()
        print(f"Direction: {result['direction']}")
        print(f"Strength: {result['strength']}")
        print(f"Confidence: {result['confidence']}")
        ```
    """
    return agent.interpret(payload)


@router.get("/health")
def health_check() -> dict:
    """
    Health check endpoint.
    
    Returns:
        Simple status dict
    """
    return {"status": "healthy", "service": "hedge-agent"}
