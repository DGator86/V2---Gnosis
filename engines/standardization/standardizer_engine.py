"""
Standardization engine
Converts disparate engine outputs into a unified StandardSnapshot
All primary agents consume this standardized format
"""
from datetime import datetime
from typing import Dict, Any, Optional
from schemas import EngineOutput, StandardSnapshot
from ..orchestration.logger import get_logger

logger = get_logger(__name__)


class StandardizerEngine:
    """
    Engine for standardizing disparate engine outputs
    Creates the unified snapshot consumed by all primary agents
    """
    
    def __init__(self):
        logger.info("Standardizer engine initialized")
    
    def _validate_engine_output(self, output: EngineOutput, expected_kind: str) -> bool:
        """Validate engine output"""
        if output.kind != expected_kind:
            logger.warning(f"Expected kind '{expected_kind}', got '{output.kind}'")
            return False
        
        if not output.features:
            logger.warning(f"Empty features for {output.kind} engine")
            return False
        
        return True
    
    def _detect_regime(self, 
                      hedge_features: Dict[str, float],
                      volume_features: Dict[str, float],
                      sentiment_features: Dict[str, float]) -> str:
        """
        Detect market regime from features
        Simple rule-based approach - can be upgraded to ML
        """
        gamma = hedge_features.get("gamma_pressure", 0.0)
        imbalance = volume_features.get("trade_imbalance", 0.0)
        sentiment = sentiment_features.get("sentiment_score", 0.0)
        
        # High gamma = gamma squeeze regime
        if abs(gamma) > 10.0:
            return "gamma_squeeze"
        
        # Strong imbalance + sentiment alignment = trending
        if abs(imbalance) > 0.3 and abs(sentiment) > 0.4:
            if (imbalance > 0 and sentiment > 0) or (imbalance < 0 and sentiment < 0):
                return "trending"
        
        # Low volume + low sentiment = range-bound
        flow = volume_features.get("flow_volume", 0.0)
        if flow < 1e6 and abs(sentiment) < 0.2:
            return "range_bound"
        
        # High volatility regime
        liquidity = volume_features.get("liquidity_score", 1.0)
        if liquidity < 0.3:
            return "high_volatility"
        
        return "normal"
    
    def standardize(self,
                   symbol: str,
                   hedge: EngineOutput,
                   volume: EngineOutput,
                   sentiment: EngineOutput) -> StandardSnapshot:
        """
        Main entry point: standardize three engine outputs
        
        Args:
            symbol: Trading symbol
            hedge: HedgeEngine output
            volume: VolumeEngine output
            sentiment: SentimentEngine output
        
        Returns:
            StandardSnapshot for agent consumption
        """
        # Validate inputs
        self._validate_engine_output(hedge, "hedge")
        self._validate_engine_output(volume, "volume")
        self._validate_engine_output(sentiment, "sentiment")
        
        # Detect regime
        regime = self._detect_regime(
            hedge.features,
            volume.features,
            sentiment.features
        )
        
        # Create unified snapshot
        snapshot = StandardSnapshot(
            timestamp=datetime.now(),
            symbol=symbol,
            hedge=hedge.features,
            volume=volume.features,
            sentiment=sentiment.features,
            regime=regime,
            metadata={
                "hedge_metadata": hedge.metadata,
                "volume_metadata": volume.metadata,
                "sentiment_metadata": sentiment.metadata,
                "hedge_confidence": hedge.confidence,
                "volume_confidence": volume.confidence,
                "sentiment_confidence": sentiment.confidence
            }
        )
        
        logger.info(f"Standardized snapshot for {symbol} | regime={regime}")
        
        return snapshot
    
    def validate_snapshot(self, snapshot: StandardSnapshot) -> Dict[str, Any]:
        """
        Validate snapshot quality
        Returns dict with validation results
        """
        issues = []
        
        # Check for missing features
        required_hedge = ["gamma_pressure", "vanna_pressure", "charm_pressure"]
        for feat in required_hedge:
            if feat not in snapshot.hedge:
                issues.append(f"Missing hedge feature: {feat}")
        
        required_volume = ["flow_volume", "vwap", "trade_imbalance"]
        for feat in required_volume:
            if feat not in snapshot.volume:
                issues.append(f"Missing volume feature: {feat}")
        
        required_sentiment = ["sentiment_score"]
        for feat in required_sentiment:
            if feat not in snapshot.sentiment:
                issues.append(f"Missing sentiment feature: {feat}")
        
        # Check confidence levels
        hedge_conf = snapshot.metadata.get("hedge_confidence", 0.0)
        volume_conf = snapshot.metadata.get("volume_confidence", 0.0)
        sentiment_conf = snapshot.metadata.get("sentiment_confidence", 0.0)
        
        if hedge_conf < 0.3:
            issues.append(f"Low hedge confidence: {hedge_conf:.2f}")
        if volume_conf < 0.3:
            issues.append(f"Low volume confidence: {volume_conf:.2f}")
        if sentiment_conf < 0.3:
            issues.append(f"Low sentiment confidence: {sentiment_conf:.2f}")
        
        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "overall_confidence": (hedge_conf + volume_conf + sentiment_conf) / 3
        }
