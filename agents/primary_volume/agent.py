"""
Primary Volume Agent
Analyzes order flow and liquidity dynamics
"""
from typing import List
from schemas import StandardSnapshot, Suggestion
from engines.lookahead.lookahead_engine import LookaheadEngine
from engines.orchestration.logger import get_logger

logger = get_logger(__name__)


class PrimaryVolumeAgent:
    """Primary agent for volume/liquidity analysis"""
    
    def __init__(self, confidence_threshold: float = 0.5,
                 lookahead_engine: LookaheadEngine = None):
        self.confidence_threshold = confidence_threshold
        self.lookahead = lookahead_engine or LookaheadEngine()
        logger.info(f"Primary Volume Agent initialized")
    
    def step(self, snapshot: StandardSnapshot, horizons: List[int] = None) -> Suggestion:
        horizons = horizons or [1, 5, 20]
        
        flow = snapshot.volume.get("flow_volume", 0.0)
        imbalance = snapshot.volume.get("trade_imbalance", 0.0)
        liquidity = snapshot.volume.get("liquidity_score", 0.5)
        
        # Flow surge detection
        action = "hold"
        confidence = 0.45
        reasoning = "No significant flow signals"
        
        if flow > 5e6 and abs(imbalance) > 0.3:
            action = "long" if imbalance > 0 else "short"
            confidence = 0.6
            reasoning = f"Flow surge: {flow:.0f} with {imbalance:.2f} imbalance"
        
        elif liquidity < 0.3:
            action = "hold"
            confidence = 0.7
            reasoning = f"Low liquidity: {liquidity:.2f}, avoiding entry"
        
        forecasts = self.lookahead.forecast(snapshot, horizons)
        
        suggestion = Suggestion.create(
            layer="primary_volume",
            symbol=snapshot.symbol,
            action=action,
            params={"flow_threshold": 5e6, "imbalance_threshold": 0.3},
            confidence=confidence,
            forecast=forecasts[max(horizons)],
            reasoning=reasoning
        )
        
        logger.info(f"Volume agent: {action} | conf={confidence:.2f}")
        return suggestion
