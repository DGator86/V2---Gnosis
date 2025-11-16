# engines/liquidity_agent/service.py

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger

from .schemas import LiquidityAgentInput, LiquidityAgentOutput
from .agent import LiquidityAgent

router = APIRouter(
    prefix="/liquidity-agent",
    tags=["liquidity-agent"],
)


def get_liquidity_agent() -> LiquidityAgent:
    """
    Dependency injection factory for LiquidityAgent.

    Extend this later to inject:
    - config (from YAML or env)
    - structured logging
    - telemetry / tracing
    - feature flags
    """
    return LiquidityAgent()


@router.post(
    "/interpret",
    response_model=LiquidityAgentOutput,
    summary="Interpret Liquidity Engine metrics into a normalized liquidity signal",
)
def interpret_liquidity(
    payload: LiquidityAgentInput,
    agent: LiquidityAgent = Depends(get_liquidity_agent),
) -> LiquidityAgentOutput:
    """
    Liquidity Agent v1.0 – Pure Interpreter Endpoint

    This endpoint:
    - Accepts pre-computed liquidity metrics from the Liquidity Engine
    - Returns a normalized LiquidityAgentOutput:
        - direction
        - strength
        - confidence
        - regime
        - notes

    It does NOT:
    - Fetch market data
    - Compute Amihud/Kyle/OFI/etc.
    - Make trading decisions
    """
    try:
        logger.debug("Received LiquidityAgentInput: {}", payload.json())
        result = agent.interpret(payload)
        logger.debug("LiquidityAgentOutput: {}", result.json())
        return result
    except Exception as exc:
        logger.exception("LiquidityAgent interpretation failed")
        raise HTTPException(status_code=500, detail="LiquidityAgent interpretation error") from exc
