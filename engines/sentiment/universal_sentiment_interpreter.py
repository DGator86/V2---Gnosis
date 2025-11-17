"""
Universal Sentiment Interpreter - Market Psychology Physics Engine
===================================================================

Core framework that translates multi-source sentiment into actionable signals.

This module implements the sentiment physics framework:
1. Raw Sentiment → Sentiment Field (crowd positioning)
2. Sentiment Field → Momentum/Reversion Signal (directional bias)
3. Momentum → Sentiment Energy (crowd conviction)
4. Energy → Contrarian Opportunities (fade the crowd)

Physics Analogy:
- Sentiment = Second-order gamma field (acceleration of price)
- Extreme sentiment = Potential energy (ready to reverse)
- Sentiment momentum = Kinetic energy (trend strength)
- Contrarian signal = Energy release (mean reversion)

Author: Super Gnosis Development Team
License: MIT
Version: 3.0.0
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import numpy as np
from datetime import datetime, timedelta
from loguru import logger
from enum import Enum


class SentimentSource(str, Enum):
    """Sentiment data sources."""
    NEWS = "news"
    TWITTER = "twitter"
    REDDIT = "reddit"
    STOCKTWITS = "stocktwits"
    ANALYST = "analyst"
    INSIDER = "insider"
    OPTIONS = "options"
    VOLUME = "volume"


@dataclass
class SentimentReading:
    """Single sentiment reading from a source."""
    
    source: SentimentSource
    score: float  # -1 (bearish) to +1 (bullish)
    confidence: float  # 0 to 1
    volume: int  # Number of mentions/articles/posts
    timestamp: datetime
    metadata: Optional[Dict] = None


@dataclass
class SentimentState:
    """Complete sentiment state of the market."""
    
    # Aggregate sentiment
    sentiment_score: float  # -1 (bearish) to +1 (bullish)
    sentiment_magnitude: float  # 0 to 1 (strength of sentiment)
    
    # Sentiment momentum
    sentiment_momentum: float  # Rate of change
    sentiment_acceleration: float  # Second derivative
    
    # Source breakdown
    news_sentiment: float  # News sentiment
    social_sentiment: float  # Social media sentiment
    analyst_sentiment: float  # Analyst ratings sentiment
    insider_sentiment: float  # Insider trading sentiment
    options_sentiment: float  # Options positioning sentiment
    
    # Crowd positioning
    crowd_positioning: float  # -1 (max bearish) to +1 (max bullish)
    crowd_conviction: float  # 0 to 1 (how convinced the crowd is)
    
    # Contrarian signals
    contrarian_signal: float  # -1 to +1 (fade opportunity)
    contrarian_strength: float  # 0 to 1 (signal strength)
    
    # Sentiment energy
    sentiment_energy: float  # Potential for reversal
    momentum_energy: float  # Trend continuation strength
    
    # Regime classification
    regime: str  # extreme_bullish, bullish, neutral, bearish, extreme_bearish
    stability: float  # Regime stability (0-1)
    
    # Metadata
    timestamp: datetime
    confidence: float  # Overall confidence (0-1)
    sources_count: int  # Number of sources used


class UniversalSentimentInterpreter:
    """
    Universal sentiment interpreter for translating multi-source sentiment into actionable signals.
    
    This is the core sentiment physics engine that:
    1. Ingests sentiment from multiple sources
    2. Constructs sentiment fields
    3. Calculates momentum and acceleration
    4. Identifies contrarian opportunities
    5. Measures crowd positioning
    6. Classifies sentiment regimes
    
    Treats sentiment as a second-order field (acceleration of price).
    """
    
    def __init__(
        self,
        contrarian_threshold: float = 0.7,  # Threshold for contrarian signals
        momentum_lookback: int = 5,  # Periods for momentum calculation
        extreme_threshold: float = 0.8,  # Threshold for extreme sentiment
        source_weights: Optional[Dict[SentimentSource, float]] = None
    ):
        """
        Initialize universal sentiment interpreter.
        
        Args:
            contrarian_threshold: Sentiment level for contrarian signals
            momentum_lookback: Number of periods for momentum
            extreme_threshold: Threshold for extreme sentiment classification
            source_weights: Custom weights for different sources
        """
        self.contrarian_threshold = contrarian_threshold
        self.momentum_lookback = momentum_lookback
        self.extreme_threshold = extreme_threshold
        
        # Default source weights (can be customized)
        self.source_weights = source_weights or {
            SentimentSource.NEWS: 0.25,
            SentimentSource.TWITTER: 0.15,
            SentimentSource.REDDIT: 0.15,
            SentimentSource.STOCKTWITS: 0.10,
            SentimentSource.ANALYST: 0.15,
            SentimentSource.INSIDER: 0.10,
            SentimentSource.OPTIONS: 0.10,
        }
        
        # Historical sentiment for momentum calculation
        self.sentiment_history: List[float] = []
        
        logger.info("✅ Universal Sentiment Interpreter initialized")
    
    def interpret(
        self,
        readings: List[SentimentReading],
        historical_sentiment: Optional[List[float]] = None
    ) -> SentimentState:
        """
        Interpret sentiment readings into complete sentiment state.
        
        Args:
            readings: List of sentiment readings from various sources
            historical_sentiment: Historical sentiment scores for momentum
        
        Returns:
            Complete SentimentState
        """
        if not readings:
            return self._neutral_state()
        
        # Update historical sentiment
        if historical_sentiment:
            self.sentiment_history = historical_sentiment[-self.momentum_lookback:]
        
        # Calculate aggregate sentiment
        sentiment_score = self._calculate_aggregate_sentiment(readings)
        sentiment_magnitude = abs(sentiment_score)
        
        # Calculate sentiment breakdown by category
        news_sentiment = self._calculate_category_sentiment(readings, [
            SentimentSource.NEWS
        ])
        social_sentiment = self._calculate_category_sentiment(readings, [
            SentimentSource.TWITTER, SentimentSource.REDDIT, SentimentSource.STOCKTWITS
        ])
        analyst_sentiment = self._calculate_category_sentiment(readings, [
            SentimentSource.ANALYST
        ])
        insider_sentiment = self._calculate_category_sentiment(readings, [
            SentimentSource.INSIDER
        ])
        options_sentiment = self._calculate_category_sentiment(readings, [
            SentimentSource.OPTIONS
        ])
        
        # Calculate momentum and acceleration
        sentiment_momentum = self._calculate_momentum(sentiment_score)
        sentiment_acceleration = self._calculate_acceleration()
        
        # Calculate crowd positioning
        crowd_positioning = sentiment_score
        crowd_conviction = self._calculate_crowd_conviction(readings, sentiment_magnitude)
        
        # Calculate contrarian signals
        contrarian_signal = self._calculate_contrarian_signal(
            sentiment_score, crowd_conviction
        )
        contrarian_strength = self._calculate_contrarian_strength(
            sentiment_score, crowd_conviction, sentiment_momentum
        )
        
        # Calculate sentiment energy
        sentiment_energy = self._calculate_sentiment_energy(
            sentiment_magnitude, crowd_conviction
        )
        momentum_energy = self._calculate_momentum_energy(
            sentiment_momentum, sentiment_magnitude
        )
        
        # Classify regime
        regime, stability = self._classify_regime(
            sentiment_score, sentiment_momentum, crowd_conviction
        )
        
        # Calculate confidence
        confidence = self._calculate_confidence(readings)
        
        return SentimentState(
            sentiment_score=sentiment_score,
            sentiment_magnitude=sentiment_magnitude,
            sentiment_momentum=sentiment_momentum,
            sentiment_acceleration=sentiment_acceleration,
            news_sentiment=news_sentiment,
            social_sentiment=social_sentiment,
            analyst_sentiment=analyst_sentiment,
            insider_sentiment=insider_sentiment,
            options_sentiment=options_sentiment,
            crowd_positioning=crowd_positioning,
            crowd_conviction=crowd_conviction,
            contrarian_signal=contrarian_signal,
            contrarian_strength=contrarian_strength,
            sentiment_energy=sentiment_energy,
            momentum_energy=momentum_energy,
            regime=regime,
            stability=stability,
            timestamp=datetime.now(),
            confidence=confidence,
            sources_count=len(readings)
        )
    
    def _calculate_aggregate_sentiment(
        self,
        readings: List[SentimentReading]
    ) -> float:
        """
        Calculate weighted aggregate sentiment from all sources.
        
        Returns score between -1 (bearish) and +1 (bullish).
        """
        weighted_sum = 0.0
        weight_sum = 0.0
        
        for reading in readings:
            weight = self.source_weights.get(reading.source, 0.1) * reading.confidence
            weighted_sum += reading.score * weight
            weight_sum += weight
        
        if weight_sum > 0:
            aggregate = weighted_sum / weight_sum
        else:
            aggregate = 0.0
        
        return np.clip(aggregate, -1.0, 1.0)
    
    def _calculate_category_sentiment(
        self,
        readings: List[SentimentReading],
        sources: List[SentimentSource]
    ) -> float:
        """Calculate sentiment for a specific category of sources."""
        category_readings = [r for r in readings if r.source in sources]
        
        if not category_readings:
            return 0.0
        
        weighted_sum = sum(r.score * r.confidence for r in category_readings)
        weight_sum = sum(r.confidence for r in category_readings)
        
        if weight_sum > 0:
            return weighted_sum / weight_sum
        return 0.0
    
    def _calculate_momentum(self, current_sentiment: float) -> float:
        """
        Calculate sentiment momentum (rate of change).
        
        Positive momentum = sentiment becoming more positive
        Negative momentum = sentiment becoming more negative
        """
        # Add current to history
        self.sentiment_history.append(current_sentiment)
        
        # Keep only recent history
        if len(self.sentiment_history) > self.momentum_lookback:
            self.sentiment_history = self.sentiment_history[-self.momentum_lookback:]
        
        if len(self.sentiment_history) < 2:
            return 0.0
        
        # Calculate linear regression slope
        x = np.arange(len(self.sentiment_history))
        y = np.array(self.sentiment_history)
        
        if len(x) > 1:
            slope = np.polyfit(x, y, 1)[0]
            return float(slope)
        
        return 0.0
    
    def _calculate_acceleration(self) -> float:
        """
        Calculate sentiment acceleration (second derivative).
        
        Measures how quickly momentum is changing.
        """
        if len(self.sentiment_history) < 3:
            return 0.0
        
        # Calculate second differences
        recent = self.sentiment_history[-3:]
        first_diff = [recent[i+1] - recent[i] for i in range(len(recent)-1)]
        
        if len(first_diff) < 2:
            return 0.0
        
        acceleration = first_diff[1] - first_diff[0]
        return float(acceleration)
    
    def _calculate_crowd_conviction(
        self,
        readings: List[SentimentReading],
        magnitude: float
    ) -> float:
        """
        Calculate how convinced the crowd is (0-1).
        
        High conviction when:
        - Multiple sources agree
        - High confidence readings
        - High sentiment magnitude
        """
        if not readings:
            return 0.0
        
        # Agreement factor (how much sources agree)
        scores = [r.score for r in readings]
        score_std = np.std(scores) if len(scores) > 1 else 0.0
        agreement = 1.0 - min(1.0, score_std)  # Lower std = higher agreement
        
        # Confidence factor
        avg_confidence = np.mean([r.confidence for r in readings])
        
        # Volume factor (more mentions = more conviction)
        total_volume = sum(r.volume for r in readings)
        volume_factor = min(1.0, total_volume / 1000)  # Normalize by 1000 mentions
        
        # Magnitude factor
        magnitude_factor = magnitude
        
        # Combined conviction
        conviction = (
            agreement * 0.3 +
            avg_confidence * 0.3 +
            volume_factor * 0.2 +
            magnitude_factor * 0.2
        )
        
        return min(1.0, conviction)
    
    def _calculate_contrarian_signal(
        self,
        sentiment_score: float,
        crowd_conviction: float
    ) -> float:
        """
        Calculate contrarian signal strength (-1 to +1).
        
        Strong contrarian signals when:
        - Sentiment is extreme
        - Crowd conviction is high
        - Signal suggests fading the crowd
        
        Positive = fade bearish sentiment (go long)
        Negative = fade bullish sentiment (go short)
        """
        # Only generate signal if sentiment is extreme
        if abs(sentiment_score) < self.contrarian_threshold:
            return 0.0
        
        # Signal strength increases with conviction
        signal_magnitude = crowd_conviction * (abs(sentiment_score) - self.contrarian_threshold)
        
        # Contrarian signal opposes current sentiment
        contrarian = -np.sign(sentiment_score) * signal_magnitude
        
        return np.clip(contrarian, -1.0, 1.0)
    
    def _calculate_contrarian_strength(
        self,
        sentiment_score: float,
        crowd_conviction: float,
        momentum: float
    ) -> float:
        """
        Calculate overall contrarian opportunity strength (0-1).
        
        Stronger when:
        - Extreme sentiment
        - High conviction
        - Momentum slowing (exhaustion)
        """
        # Extremity factor
        extremity = abs(sentiment_score)
        
        # Conviction factor
        conviction_factor = crowd_conviction
        
        # Exhaustion factor (momentum opposing sentiment)
        if abs(sentiment_score) > 0.01:
            exhaustion = max(0, -np.sign(sentiment_score) * momentum)
        else:
            exhaustion = 0
        
        # Combined strength
        strength = (
            extremity * 0.4 +
            conviction_factor * 0.4 +
            exhaustion * 0.2
        )
        
        return min(1.0, strength)
    
    def _calculate_sentiment_energy(
        self,
        magnitude: float,
        conviction: float
    ) -> float:
        """
        Calculate sentiment energy (potential for reversal).
        
        Higher energy = more potential for mean reversion.
        """
        # Energy increases with extreme sentiment and high conviction
        energy = magnitude * conviction
        
        # Non-linear scaling (extreme sentiment has disproportionate energy)
        energy = energy ** 1.5
        
        return min(1.0, energy)
    
    def _calculate_momentum_energy(
        self,
        momentum: float,
        magnitude: float
    ) -> float:
        """
        Calculate momentum energy (trend continuation strength).
        
        Higher energy = stronger trend likely to continue.
        """
        # Energy when momentum and sentiment align
        if abs(magnitude) > 0.01:
            alignment = abs(momentum) * magnitude
        else:
            alignment = 0.0
        
        # Non-linear scaling
        energy = abs(alignment) ** 1.2
        
        return min(1.0, energy)
    
    def _classify_regime(
        self,
        sentiment_score: float,
        momentum: float,
        conviction: float
    ) -> Tuple[str, float]:
        """
        Classify sentiment regime.
        
        Returns:
            (regime_name, stability_score)
        """
        # Classify based on sentiment score
        if sentiment_score > self.extreme_threshold:
            regime = "extreme_bullish"
            stability = 0.3  # Unstable (likely to reverse)
        elif sentiment_score > 0.3:
            regime = "bullish"
            stability = 0.6
        elif sentiment_score > -0.3:
            regime = "neutral"
            stability = 0.8
        elif sentiment_score > -self.extreme_threshold:
            regime = "bearish"
            stability = 0.6
        else:
            regime = "extreme_bearish"
            stability = 0.3  # Unstable (likely to reverse)
        
        # Adjust stability based on momentum and conviction
        if abs(momentum) > 0.2:
            # High momentum makes regime less stable
            stability *= 0.8
        
        if conviction > 0.8:
            # High conviction makes extreme regimes less stable (crowded)
            if "extreme" in regime:
                stability *= 0.7
        
        return regime, max(0.0, min(1.0, stability))
    
    def _calculate_confidence(self, readings: List[SentimentReading]) -> float:
        """
        Calculate confidence in sentiment state.
        
        Higher confidence with:
        - More sources
        - Higher confidence readings
        - More recent data
        """
        if not readings:
            return 0.0
        
        # Source count factor
        unique_sources = len(set(r.source for r in readings))
        source_factor = min(1.0, unique_sources / 5)  # 5 sources ideal
        
        # Average confidence
        avg_confidence = np.mean([r.confidence for r in readings])
        
        # Recency factor (assume all readings are recent for now)
        recency_factor = 1.0
        
        # Combined confidence
        confidence = (
            source_factor * 0.4 +
            avg_confidence * 0.4 +
            recency_factor * 0.2
        )
        
        return min(1.0, confidence)
    
    def _neutral_state(self) -> SentimentState:
        """Return neutral sentiment state when no data available."""
        return SentimentState(
            sentiment_score=0.0,
            sentiment_magnitude=0.0,
            sentiment_momentum=0.0,
            sentiment_acceleration=0.0,
            news_sentiment=0.0,
            social_sentiment=0.0,
            analyst_sentiment=0.0,
            insider_sentiment=0.0,
            options_sentiment=0.0,
            crowd_positioning=0.0,
            crowd_conviction=0.0,
            contrarian_signal=0.0,
            contrarian_strength=0.0,
            sentiment_energy=0.0,
            momentum_energy=0.0,
            regime="neutral",
            stability=1.0,
            timestamp=datetime.now(),
            confidence=0.0,
            sources_count=0
        )


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def create_interpreter(
    contrarian_threshold: float = 0.7,
    extreme_threshold: float = 0.8
) -> UniversalSentimentInterpreter:
    """
    Create universal sentiment interpreter with default settings.
    
    Args:
        contrarian_threshold: Threshold for contrarian signals
        extreme_threshold: Threshold for extreme sentiment
    
    Returns:
        Configured UniversalSentimentInterpreter
    """
    return UniversalSentimentInterpreter(
        contrarian_threshold=contrarian_threshold,
        extreme_threshold=extreme_threshold
    )


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    print("\n💭 Universal Sentiment Interpreter Example\n")
    
    # Create interpreter
    interpreter = create_interpreter()
    
    # Sample sentiment readings (AAPL example)
    readings = [
        SentimentReading(
            source=SentimentSource.NEWS,
            score=0.65,  # Bullish news
            confidence=0.85,
            volume=25,
            timestamp=datetime.now()
        ),
        SentimentReading(
            source=SentimentSource.TWITTER,
            score=0.75,  # Very bullish social
            confidence=0.70,
            volume=1500,
            timestamp=datetime.now()
        ),
        SentimentReading(
            source=SentimentSource.REDDIT,
            score=0.80,  # Extremely bullish Reddit
            confidence=0.75,
            volume=850,
            timestamp=datetime.now()
        ),
        SentimentReading(
            source=SentimentSource.ANALYST,
            score=0.45,  # Moderately bullish analysts
            confidence=0.90,
            volume=12,
            timestamp=datetime.now()
        ),
        SentimentReading(
            source=SentimentSource.OPTIONS,
            score=0.55,  # Bullish options positioning
            confidence=0.80,
            volume=5000,
            timestamp=datetime.now()
        ),
    ]
    
    # Historical sentiment for momentum
    historical = [0.3, 0.4, 0.5, 0.6, 0.65]
    
    # Interpret sentiment state
    sentiment_state = interpreter.interpret(readings, historical)
    
    # Display results
    print(f"Sources: {sentiment_state.sources_count} readings")
    print(f"\n💭 AGGREGATE SENTIMENT:")
    print(f"   Sentiment Score: {sentiment_state.sentiment_score:+.2f}")
    print(f"   Magnitude: {sentiment_state.sentiment_magnitude:.2%}")
    print(f"   Momentum: {sentiment_state.sentiment_momentum:+.3f}")
    print(f"   Acceleration: {sentiment_state.sentiment_acceleration:+.3f}")
    print(f"\n📊 SOURCE BREAKDOWN:")
    print(f"   News: {sentiment_state.news_sentiment:+.2f}")
    print(f"   Social: {sentiment_state.social_sentiment:+.2f}")
    print(f"   Analyst: {sentiment_state.analyst_sentiment:+.2f}")
    print(f"   Options: {sentiment_state.options_sentiment:+.2f}")
    print(f"\n👥 CROWD POSITIONING:")
    print(f"   Positioning: {sentiment_state.crowd_positioning:+.2f}")
    print(f"   Conviction: {sentiment_state.crowd_conviction:.2%}")
    print(f"\n🔄 CONTRARIAN SIGNALS:")
    print(f"   Signal: {sentiment_state.contrarian_signal:+.2f}")
    print(f"   Strength: {sentiment_state.contrarian_strength:.2%}")
    print(f"\n⚡ ENERGY:")
    print(f"   Sentiment Energy: {sentiment_state.sentiment_energy:.2%}")
    print(f"   Momentum Energy: {sentiment_state.momentum_energy:.2%}")
    print(f"\n🎯 REGIME:")
    print(f"   Classification: {sentiment_state.regime}")
    print(f"   Stability: {sentiment_state.stability:.2%}")
    print(f"   Confidence: {sentiment_state.confidence:.2%}")
    
    print("\n✅ Universal Sentiment Interpreter ready for production!")
