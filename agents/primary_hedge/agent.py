"""
Primary Hedge Agent
Analyzes dealer positioning and greek exposures
Emits suggestions based on gamma pins, vanna flows, charm decay
"""
from typing import Dict, Any, List
from datetime import datetime
from schemas import StandardSnapshot, Suggestion, Forecast
from engines.lookahead.lookahead_engine import LookaheadEngine
from engines.orchestration.logger import get_logger

logger = get_logger(__name__)


class PrimaryHedgeAgent:
    """
    Primary agent for hedge/dealer positioning analysis
    Focus: gamma pressure, vanna flows, charm decay
    """
    
    def __init__(self, 
                 confidence_threshold: float = 0.5,
                 lookahead_engine: LookaheadEngine = None):
        self.confidence_threshold = confidence_threshold
        self.lookahead = lookahead_engine or LookaheadEngine()
        
        logger.info(f"Primary Hedge Agent initialized (threshold={confidence_threshold})")
    
    def _analyze_gamma_pin(self, snapshot: StandardSnapshot) -> Dict[str, Any]:
        """Detect gamma pin conditions"""
        gamma = snapshot.hedge.get("gamma_pressure", 0.0)
        max_strike_gamma = snapshot.hedge.get("max_strike_gamma", 0.0)
        
        # High gamma concentration at specific strike = pin
        if abs(gamma) > 8.0 and max_strike_gamma > 3.0:
            return {
                "detected": True,
                "strength": min(1.0, abs(gamma) / 15.0),
                "action": "neutral",  # Expect price to pin near strike
                "reasoning": f"Gamma pin detected: total={gamma:.2f}, max_strike={max_strike_gamma:.2f}"
            }
        
        return {"detected": False}
    
    def _analyze_vanna_flow(self, snapshot: StandardSnapshot) -> Dict[str, Any]:
        """Detect vanna-driven flows"""
        vanna = snapshot.hedge.get("vanna_pressure", 0.0)
        sentiment = snapshot.sentiment.get("sentiment_score", 0.0)
        
        # Vanna can amplify moves when vol and spot move together
        if abs(vanna) > 2.0 and abs(sentiment) > 0.3:
            aligned = (vanna > 0 and sentiment > 0) or (vanna < 0 and sentiment < 0)
            
            if aligned:
                return {
                    "detected": True,
                    "action": "long" if vanna > 0 else "short",
                    "confidence": 0.6,
                    "reasoning": f"Vanna flow aligned with sentiment: vanna={vanna:.2f}, sent={sentiment:.2f}"
                }
        
        return {"detected": False}
    
    def _analyze_charm_decay(self, snapshot: StandardSnapshot) -> Dict[str, Any]:
        """Analyze charm (gamma decay over time)"""
        charm = snapshot.hedge.get("charm_pressure", 0.0)
        gamma = snapshot.hedge.get("gamma_pressure", 0.0)
        
        # High charm means gamma exposure decaying rapidly
        # This can create forced rehedging
        if abs(charm) > 1.0 and abs(gamma) > 5.0:
            return {
                "detected": True,
                "action": "long" if charm > 0 else "short",
                "confidence": 0.55,
                "reasoning": f"Charm decay forcing rehedge: charm={charm:.2f}, gamma={gamma:.2f}"
            }
        
        return {"detected": False}
    
    def step(self, 
             snapshot: StandardSnapshot,
             horizons: List[int] = None) -> Suggestion:
        """
        Main decision function
        
        Args:
            snapshot: Standardized snapshot
            horizons: Forecast horizons for look-ahead
        
        Returns:
            Suggestion with action and forecast
        """
        horizons = horizons or [1, 5, 20]
        
        # Run detection rules
        gamma_pin = self._analyze_gamma_pin(snapshot)
        vanna_flow = self._analyze_vanna_flow(snapshot)
        charm_decay = self._analyze_charm_decay(snapshot)
        
        # Decision logic (priority: gamma pin > vanna flow > charm decay)
        action = "hold"
        confidence = 0.4
        reasoning = "No strong hedge signals"
        
        if gamma_pin.get("detected"):
            action = gamma_pin["action"]
            confidence = gamma_pin["strength"] * 0.7
            reasoning = gamma_pin["reasoning"]
        
        elif vanna_flow.get("detected"):
            action = vanna_flow["action"]
            confidence = vanna_flow["confidence"]
            reasoning = vanna_flow["reasoning"]
        
        elif charm_decay.get("detected"):
            action = charm_decay["action"]
            confidence = charm_decay["confidence"]
            reasoning = charm_decay["reasoning"]
        
        # Run look-ahead forecast
        forecasts = self.lookahead.forecast(snapshot, horizons)
        primary_forecast = forecasts[max(horizons)]
        
        # Adjust confidence based on regime
        if snapshot.regime == "gamma_squeeze" and gamma_pin.get("detected"):
            confidence *= 1.2  # More confident in gamma squeezes
        
        # Create suggestion
        suggestion = Suggestion.create(
            layer="primary_hedge",
            symbol=snapshot.symbol,
            action=action,
            params={
                "gamma_pin": gamma_pin.get("detected", False),
                "vanna_flow": vanna_flow.get("detected", False),
                "charm_decay": charm_decay.get("detected", False),
                "threshold": self.confidence_threshold
            },
            confidence=min(0.95, confidence),
            forecast=primary_forecast,
            reasoning=reasoning
        )
        
        logger.info(f"Hedge agent: {action} | conf={confidence:.2f} | {reasoning}")
        
        return suggestion
