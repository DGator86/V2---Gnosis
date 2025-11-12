"""
Primary Sentiment Agent
Analyzes news sentiment and catalyst detection
"""
from typing import List
from schemas import StandardSnapshot, Suggestion
from engines.lookahead.lookahead_engine import LookaheadEngine
from engines.orchestration.logger import get_logger

logger = get_logger(__name__)


class PrimarySentimentAgent:
    """Primary agent for sentiment analysis"""
    
    def __init__(self, confidence_threshold: float = 0.5,
                 lookahead_engine: LookaheadEngine = None):
        self.confidence_threshold = confidence_threshold
        self.lookahead = lookahead_engine or LookaheadEngine()
        logger.info(f"Primary Sentiment Agent initialized")
    
    def step(self, snapshot: StandardSnapshot, horizons: List[int] = None) -> Suggestion:
        horizons = horizons or [1, 5, 20]
        
        sentiment = snapshot.sentiment.get("sentiment_score", 0.0)
        magnitude = snapshot.sentiment.get("sentiment_magnitude", 0.0)
        consistency = snapshot.sentiment.get("sentiment_consistency", 0.5)
        num_catalysts = snapshot.sentiment.get("num_catalysts", 0)
        
        action = "hold"
        confidence = 0.45
        reasoning = "Neutral sentiment"
        
        # Catalyst-driven signal
        if num_catalysts > 0 and abs(sentiment) > 0.4:
            action = "long" if sentiment > 0 else "short"
            confidence = 0.65 * consistency
            reasoning = f"Catalyst detected: {num_catalysts} events, sentiment={sentiment:.2f}"
        
        # Strong consistent sentiment
        elif abs(sentiment) > 0.5 and consistency > 0.7:
            action = "long" if sentiment > 0 else "short"
            confidence = 0.6 * magnitude
            reasoning = f"Strong consistent sentiment: {sentiment:.2f}, consistency={consistency:.2f}"
        
        forecasts = self.lookahead.forecast(snapshot, horizons)
        
        suggestion = Suggestion.create(
            layer="primary_sentiment",
            symbol=snapshot.symbol,
            action=action,
            params={"sentiment_threshold": 0.4, "consistency_threshold": 0.7},
            confidence=min(0.95, confidence),
            forecast=forecasts[max(horizons)],
            reasoning=reasoning
        )
        
        logger.info(f"Sentiment agent: {action} | conf={confidence:.2f}")
        return suggestion
