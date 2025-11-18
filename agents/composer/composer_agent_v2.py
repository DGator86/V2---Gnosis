"""
Composer Agent V2.0 - The Brain
================================

Probabilistic Multi-Timeframe Range Forecasting

This is THE critical missing piece that fuses:
- Hedge Engine: Dealer positioning & energy barriers
- Liquidity Engine: Support/resistance & orderflow  
- Sentiment Engine: News sentiment & technical signals

Into unified probabilistic forecasts across multiple timeframes.

Theory:
-------
1. Each engine provides directional bias + confidence
2. Composer weighs by:
   - Hedge (40%): Energy barriers dominate price action
   - Liquidity (35%): Orderflow & support/resistance critical
   - Sentiment (25%): Catalysts & momentum important but secondary

3. Output: Probabilistic ranges for each timeframe
   - 1m: Scalp range (±0.1-0.3%)
   - 5m: Swing range (±0.3-0.8%)  
   - 1h: Intraday range (±0.8-2.0%)
   - 1d: Daily range (±2.0-5.0%)

4. Confidence calibration:
   - All engines agree: 0.8-0.95 confidence
   - 2/3 agree: 0.5-0.7 confidence
   - Conflict: 0.2-0.4 confidence

Author: Super Gnosis Development Team
Version: 2.0.0
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple
from uuid import uuid4
from datetime import datetime
import numpy as np

from agents.base import ComposerAgent
from schemas.core_schemas import StandardSnapshot, Suggestion


class ComposerAgentV2(ComposerAgent):
    """
    The Brain - Fuses all engine signals into probabilistic multi-TF forecasts.
    
    Key Innovations:
    - Probabilistic range forecasts (not binary up/down)
    - Multi-timeframe coordination
    - Confidence calibration based on agreement
    - Energy-aware weighting
    """
    
    def __init__(
        self,
        weights: Dict[str, float] = None,
        config: Dict[str, Any] = None
    ) -> None:
        """
        Initialize Composer V2.
        
        Args:
            weights: Engine weights (hedge, liquidity, sentiment)
            config: Configuration dict
        """
        # Default weights (energy-first approach)
        self.weights = weights or {
            'hedge': 0.40,      # Energy barriers dominate
            'liquidity': 0.35,  # Orderflow critical
            'sentiment': 0.25   # Important but secondary
        }
        
        self.config = config or {}
        
        # Timeframe ranges (% move expectations)
        self.timeframe_ranges = {
            '1m': {'base': 0.002, 'multiplier': 1.5},   # ±0.2% base
            '5m': {'base': 0.005, 'multiplier': 2.0},   # ±0.5% base
            '15m': {'base': 0.008, 'multiplier': 2.5},  # ±0.8% base
            '1h': {'base': 0.015, 'multiplier': 3.0},   # ±1.5% base
            '4h': {'base': 0.025, 'multiplier': 3.5},   # ±2.5% base
            '1d': {'base': 0.035, 'multiplier': 4.0},   # ±3.5% base
        }
    
    def compose(
        self,
        snapshot: StandardSnapshot,
        suggestions: List[Suggestion]
    ) -> Suggestion:
        """
        Main composition method - the brain of the system.
        
        Process:
        1. Parse suggestions from each engine
        2. Calculate weighted directional bias
        3. Generate probabilistic ranges per timeframe
        4. Calibrate confidence based on agreement
        5. Generate actionable forecast
        
        Args:
            snapshot: StandardSnapshot with all engine features
            suggestions: List of suggestions from primary agents
        
        Returns:
            Unified Suggestion with probabilistic multi-TF forecast
        """
        # Extract current price from snapshot metadata
        current_price = self._extract_current_price(snapshot)
        
        # Parse suggestions by layer
        hedge_suggestion = self._find_suggestion(suggestions, 'hedge')
        liquidity_suggestion = self._find_suggestion(suggestions, 'liquidity')
        sentiment_suggestion = self._find_suggestion(suggestions, 'sentiment')
        
        # Calculate weighted directional bias
        directional_bias, raw_confidence = self._calculate_directional_bias(
            hedge_suggestion,
            liquidity_suggestion,
            sentiment_suggestion
        )
        
        # Check agreement level (affects confidence)
        agreement_level = self._calculate_agreement(
            hedge_suggestion,
            liquidity_suggestion,
            sentiment_suggestion
        )
        
        # Calibrate final confidence
        calibrated_confidence = self._calibrate_confidence(
            raw_confidence,
            agreement_level,
            snapshot
        )
        
        # Generate multi-TF probabilistic ranges
        forecast = self._generate_multi_tf_forecast(
            current_price=current_price,
            directional_bias=directional_bias,
            confidence=calibrated_confidence,
            snapshot=snapshot
        )
        
        # Determine primary action
        action = self._determine_action(
            directional_bias,
            calibrated_confidence
        )
        
        # Generate detailed reasoning
        reasoning = self._generate_reasoning(
            hedge_suggestion,
            liquidity_suggestion,
            sentiment_suggestion,
            directional_bias,
            agreement_level,
            calibrated_confidence
        )
        
        # Build unified suggestion
        return Suggestion(
            id=f"composer_v2-{uuid4()}",
            layer="composer",
            symbol=snapshot.symbol,
            action=action,
            confidence=calibrated_confidence,
            forecast=forecast,
            reasoning=reasoning,
            tags=["composer_v2", "multi_tf", "probabilistic"]
        )
    
    def _find_suggestion(
        self,
        suggestions: List[Suggestion],
        layer: str
    ) -> Suggestion | None:
        """Find suggestion from specific layer."""
        for suggestion in suggestions:
            if suggestion.layer == layer:
                return suggestion
        return None
    
    def _calculate_directional_bias(
        self,
        hedge: Suggestion | None,
        liquidity: Suggestion | None,
        sentiment: Suggestion | None
    ) -> Tuple[float, float]:
        """
        Calculate weighted directional bias.
        
        Returns:
            (bias, confidence) where:
            - bias: -1.0 (strong short) to +1.0 (strong long)
            - confidence: 0.0 to 1.0
        """
        weighted_bias = 0.0
        total_weight = 0.0
        
        # Map actions to numerical bias
        action_to_bias = {
            'long': 1.0,
            'short': -1.0,
            'flat': 0.0,
            'spread': 0.0,
            'complex': 0.0
        }
        
        # Hedge engine contribution
        if hedge:
            bias = action_to_bias.get(hedge.action, 0.0)
            weight = self.weights['hedge'] * hedge.confidence
            weighted_bias += bias * weight
            total_weight += weight
        
        # Liquidity engine contribution
        if liquidity:
            bias = action_to_bias.get(liquidity.action, 0.0)
            weight = self.weights['liquidity'] * liquidity.confidence
            weighted_bias += bias * weight
            total_weight += weight
        
        # Sentiment engine contribution
        if sentiment:
            bias = action_to_bias.get(sentiment.action, 0.0)
            weight = self.weights['sentiment'] * sentiment.confidence
            weighted_bias += bias * weight
            total_weight += weight
        
        # Normalize
        if total_weight > 0:
            directional_bias = weighted_bias / total_weight
            raw_confidence = min(1.0, total_weight)
        else:
            directional_bias = 0.0
            raw_confidence = 0.0
        
        return directional_bias, raw_confidence
    
    def _calculate_agreement(
        self,
        hedge: Suggestion | None,
        liquidity: Suggestion | None,
        sentiment: Suggestion | None
    ) -> str:
        """
        Calculate agreement level between engines.
        
        Returns:
            'full' = all agree
            'majority' = 2/3 agree
            'conflict' = no agreement
        """
        actions = []
        
        if hedge and hedge.action in ['long', 'short']:
            actions.append(hedge.action)
        if liquidity and liquidity.action in ['long', 'short']:
            actions.append(liquidity.action)
        if sentiment and sentiment.action in ['long', 'short']:
            actions.append(sentiment.action)
        
        if not actions:
            return 'neutral'
        
        # Count occurrences
        from collections import Counter
        counts = Counter(actions)
        most_common = counts.most_common(1)[0][1]
        
        if most_common == len(actions):
            return 'full'  # All agree
        elif most_common >= 2:
            return 'majority'  # 2/3 agree
        else:
            return 'conflict'  # No agreement
    
    def _calibrate_confidence(
        self,
        raw_confidence: float,
        agreement_level: str,
        snapshot: StandardSnapshot
    ) -> float:
        """
        Calibrate confidence based on agreement and market conditions.
        
        Theory:
        - Full agreement + high individual confidence = very high (0.8-0.95)
        - Majority agreement = moderate (0.5-0.7)
        - Conflict = low (0.2-0.4)
        """
        # Base confidence from weighted calculation
        confidence = raw_confidence
        
        # Agreement multipliers
        agreement_multipliers = {
            'full': 1.2,        # Boost when all agree
            'majority': 1.0,    # No change
            'conflict': 0.5,    # Reduce when conflicting
            'neutral': 0.7      # Slightly reduce when neutral
        }
        
        confidence *= agreement_multipliers.get(agreement_level, 1.0)
        
        # Market regime modifiers
        regime = snapshot.regime or 'neutral'
        
        # In high volatility, reduce confidence (less predictable)
        if 'volatile' in regime.lower() or 'toxic' in regime.lower():
            confidence *= 0.8
        
        # In stable regimes, slight boost
        if 'stable' in regime.lower() or 'liquid' in regime.lower():
            confidence *= 1.1
        
        # Clamp to [0, 1]
        return max(0.0, min(1.0, confidence))
    
    def _generate_multi_tf_forecast(
        self,
        current_price: float,
        directional_bias: float,
        confidence: float,
        snapshot: StandardSnapshot
    ) -> Dict[str, float]:
        """
        Generate probabilistic ranges for each timeframe.
        
        Returns dict with:
        - {tf}_low: Lower bound for timeframe
        - {tf}_mid: Expected mid point
        - {tf}_high: Upper bound for timeframe
        - {tf}_prob: Probability of being in range
        """
        forecast = {}
        
        # Get volatility multiplier from hedge engine
        elasticity = snapshot.hedge.get('elasticity', 1.0)
        
        # Higher elasticity = wider ranges (harder to move = more uncertainty)
        vol_multiplier = 1.0 + (elasticity - 1.0) * 0.5
        
        for tf, params in self.timeframe_ranges.items():
            base_range = params['base']
            multiplier = params['multiplier']
            
            # Adjust range by volatility
            adjusted_range = base_range * vol_multiplier * multiplier
            
            # Skew range based on directional bias
            # Positive bias = higher expected value
            # Negative bias = lower expected value
            range_skew = directional_bias * adjusted_range * 0.5
            
            # Calculate bounds
            mid_price = current_price * (1.0 + range_skew)
            low_price = mid_price * (1.0 - adjusted_range)
            high_price = mid_price * (1.0 + adjusted_range)
            
            # Probability of being in range (higher confidence = tighter range, higher prob)
            in_range_prob = 0.5 + confidence * 0.4  # 0.5 to 0.9
            
            forecast[f'{tf}_low'] = round(low_price, 2)
            forecast[f'{tf}_mid'] = round(mid_price, 2)
            forecast[f'{tf}_high'] = round(high_price, 2)
            forecast[f'{tf}_prob'] = round(in_range_prob, 3)
        
        # Add directional expectation
        forecast['directional_bias'] = round(directional_bias, 3)
        forecast['current_price'] = round(current_price, 2)
        
        return forecast
    
    def _determine_action(
        self,
        directional_bias: float,
        confidence: float
    ) -> str:
        """
        Determine primary action from directional bias and confidence.
        
        Theory:
        - Strong bias + high confidence = long/short
        - Weak bias or low confidence = flat/spread
        """
        action_threshold = 0.3
        confidence_threshold = 0.5
        
        if confidence < confidence_threshold:
            # Low confidence = stay flat
            return 'flat'
        
        if directional_bias > action_threshold:
            return 'long'
        elif directional_bias < -action_threshold:
            return 'short'
        else:
            # Neutral with decent confidence = spreads work
            return 'spread'
    
    def _generate_reasoning(
        self,
        hedge: Suggestion | None,
        liquidity: Suggestion | None,
        sentiment: Suggestion | None,
        directional_bias: float,
        agreement_level: str,
        confidence: float
    ) -> str:
        """Generate human-readable reasoning."""
        
        parts = []
        
        # Agreement summary
        agreement_desc = {
            'full': '✅ All engines agree',
            'majority': '⚠️ Majority agreement (2/3)',
            'conflict': '❌ Conflicting signals',
            'neutral': '⚪ Neutral positioning'
        }
        parts.append(agreement_desc.get(agreement_level, 'Unknown agreement'))
        
        # Engine summaries
        if hedge:
            parts.append(f"Hedge: {hedge.action} ({hedge.confidence:.2f})")
        if liquidity:
            parts.append(f"Liquidity: {liquidity.action} ({liquidity.confidence:.2f})")
        if sentiment:
            parts.append(f"Sentiment: {sentiment.action} ({sentiment.confidence:.2f})")
        
        # Directional summary
        if abs(directional_bias) > 0.3:
            direction = "bullish" if directional_bias > 0 else "bearish"
            strength = "strong" if abs(directional_bias) > 0.6 else "moderate"
            parts.append(f"Consensus: {strength} {direction} bias ({directional_bias:+.2f})")
        else:
            parts.append(f"Consensus: neutral/rangebound ({directional_bias:+.2f})")
        
        # Confidence summary
        conf_desc = "very high" if confidence > 0.8 else "high" if confidence > 0.6 else "moderate" if confidence > 0.4 else "low"
        parts.append(f"Confidence: {conf_desc} ({confidence:.2f})")
        
        return " | ".join(parts)
    
    def _extract_current_price(self, snapshot: StandardSnapshot) -> float:
        """Extract current price from snapshot."""
        # Try metadata first
        if 'current_price' in snapshot.metadata:
            try:
                return float(snapshot.metadata['current_price'])
            except (ValueError, TypeError):
                pass
        
        # Try hedge features (often has spot price)
        if 'spot' in snapshot.hedge:
            return snapshot.hedge['spot']
        
        # Fallback to liquidity (mid price)
        if 'mid_price' in snapshot.liquidity:
            return snapshot.liquidity['mid_price']
        
        # Last resort: return placeholder
        return 100.0  # Will be overridden by actual data
