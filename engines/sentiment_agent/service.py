# engines/sentiment_agent/service.py

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger

from .schemas import SentimentAgentInput, SentimentAgentOutput
from .agent import SentimentAgent

router = APIRouter(
    prefix="/sentiment-agent",
    tags=["sentiment-agent"],
)


def get_sentiment_agent() -> SentimentAgent:
    """
    Dependency injection factory for SentimentAgent.
    Extend with config/logging/telemetry injection as needed.
    """
    return SentimentAgent()


@router.post(
    "/interpret",
    response_model=SentimentAgentOutput,
    summary="Interpret Sentiment Engine metrics into a normalized sentiment signal",
)
def interpret_sentiment(
    payload: SentimentAgentInput,
    agent: SentimentAgent = Depends(get_sentiment_agent),
) -> SentimentAgentOutput:
    """
    Sentiment Agent v1.0 – Pure Interpreter Endpoint.

    It:
    - Accepts SentimentEngine-derived metrics
    - Returns qualitative direction, strength, confidence, regime, and notes

    It does NOT:
    - Fetch market data
    - Fit models
    - Produce trades
    """
    try:
        logger.debug("Received SentimentAgentInput: {}", payload.json())
        result = agent.interpret(payload)
        logger.debug("SentimentAgentOutput: {}", result.json())
        return result
    except Exception as exc:
        logger.exception("SentimentAgent interpretation failed")
        raise HTTPException(status_code=500, detail="SentimentAgent interpretation error") from exc
