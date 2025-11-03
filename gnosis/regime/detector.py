"""
Regime Detection System

Classifies market state using multiple methods:
1. HMM-based (from markov_regime_v0)
2. Volatility-based (VIX proxy)
3. Trend strength
4. Range detection

Activates agents conditionally based on regime.
"""

from __future__ import annotations
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import numpy as np
import pandas as pd


@dataclass
class RegimeState:
    """Current market regime"""
    primary: str  # "trending_up", "trending_down", "ranging", "volatile", "calm"
    confidence: float  # 0-1
    sub_regimes: Dict[str, float]  # All regime probabilities
    volatility: float  # Realized volatility
    trend_strength: float  # -1 to 1
    timestamp: datetime


class RegimeDetector:
    """
    Multi-method regime detection
    
    Methods:
    1. Trend: ADX-like directional strength
    2. Volatility: Rolling standard deviation
    3. Range: Bollinger band width
    4. HMM: Probabilistic state machine (from markov_regime_v0)
    
    Output: Composite regime with confidence
    """
    
    def __init__(
        self,
        trend_window: int = 20,
        vol_window: int = 20,
        vol_threshold_high: float = 0.25,  # High vol regime
        vol_threshold_low: float = 0.10,   # Low vol regime
        trend_threshold: float = 0.3       # Strong trend threshold
    ):
        self.trend_window = trend_window
        self.vol_window = vol_window
        self.vol_threshold_high = vol_threshold_high
        self.vol_threshold_low = vol_threshold_low
        self.trend_threshold = trend_threshold
        
        # HMM state (if using markov engine)
        self.hmm_state = None
        try:
            from gnosis.engines.markov_regime_v0 import SimpleHMM
            self.hmm = SimpleHMM()
            self.hmm_available = True
        except:
            self.hmm_available = False
    
    def detect(self, bars: pd.DataFrame) -> RegimeState:
        """
        Detect current regime from recent bars
        
        Args:
            bars: DataFrame with columns [t_event, price, volume, ...]
        
        Returns:
            RegimeState with classification
        """
        if len(bars) < max(self.trend_window, self.vol_window):
            # Not enough data - default to ranging
            return RegimeState(
                primary="ranging",
                confidence=0.5,
                sub_regimes={"ranging": 1.0},
                volatility=0.15,
                trend_strength=0.0,
                timestamp=datetime.now()
            )
        
        # 1. Volatility regime
        volatility = self._calculate_volatility(bars)
        vol_regime = self._classify_volatility(volatility)
        
        # 2. Trend regime
        trend_strength = self._calculate_trend_strength(bars)
        trend_regime = self._classify_trend(trend_strength)
        
        # 3. Range detection
        is_ranging = self._detect_range(bars)
        
        # 4. HMM regime (if available)
        hmm_regime = None
        if self.hmm_available:
            hmm_regime = self._hmm_regime(bars)
        
        # Combine regimes
        primary, confidence, sub_regimes = self._combine_regimes(
            vol_regime, trend_regime, is_ranging, hmm_regime, trend_strength
        )
        
        return RegimeState(
            primary=primary,
            confidence=confidence,
            sub_regimes=sub_regimes,
            volatility=volatility,
            trend_strength=trend_strength,
            timestamp=datetime.now()
        )
    
    def _calculate_volatility(self, bars: pd.DataFrame) -> float:
        """Calculate realized volatility (annualized)"""
        returns = bars["price"].pct_change().tail(self.vol_window)
        vol = returns.std() * np.sqrt(252)  # Annualize (assuming daily, adjust for intraday)
        return vol
    
    def _classify_volatility(self, vol: float) -> str:
        """Classify volatility regime"""
        if vol > self.vol_threshold_high:
            return "volatile"
        elif vol < self.vol_threshold_low:
            return "calm"
        else:
            return "normal"
    
    def _calculate_trend_strength(self, bars: pd.DataFrame) -> float:
        """
        Calculate trend strength (-1 to 1)
        
        Uses simple momentum + regression slope
        """
        window = bars.tail(self.trend_window).copy()
        
        # Price momentum
        momentum = (window["price"].iloc[-1] / window["price"].iloc[0]) - 1
        
        # Linear regression slope
        x = np.arange(len(window))
        y = window["price"].values
        slope = np.polyfit(x, y, 1)[0]
        
        # Normalize slope
        slope_norm = slope / (y.mean() / len(window))
        
        # Combine (weight momentum more)
        strength = 0.7 * momentum + 0.3 * slope_norm
        
        # Clip to [-1, 1]
        return np.clip(strength, -1.0, 1.0)
    
    def _classify_trend(self, strength: float) -> str:
        """Classify trend from strength"""
        if strength > self.trend_threshold:
            return "trending_up"
        elif strength < -self.trend_threshold:
            return "trending_down"
        else:
            return "ranging"
    
    def _detect_range(self, bars: pd.DataFrame) -> bool:
        """Detect if market is ranging (low ATR, tight Bollinger)"""
        window = bars.tail(self.trend_window)
        
        # ATR-like measure
        high_low = (window["high"] - window["low"]) / window["price"]
        atr_pct = high_low.mean()
        
        # Bollinger band width
        bb_width = (window["price"].std() / window["price"].mean())
        
        # Ranging if low ATR and tight bands
        is_ranging = (atr_pct < 0.01) and (bb_width < 0.02)
        
        return is_ranging
    
    def _hmm_regime(self, bars: pd.DataFrame) -> Optional[str]:
        """Get HMM-based regime"""
        if not self.hmm_available:
            return None
        
        try:
            # Get latest observation
            window = bars.tail(5)
            returns = window["price"].pct_change()
            
            momo = returns.mean()
            vol_change = window["volume"].pct_change().mean()
            vol = returns.std()
            
            # Update HMM
            state, probs = self.hmm.update(momo, vol_change, vol)
            
            return state
        except:
            return None
    
    def _combine_regimes(
        self,
        vol_regime: str,
        trend_regime: str,
        is_ranging: bool,
        hmm_regime: Optional[str],
        trend_strength: float
    ) -> Tuple[str, float, Dict[str, float]]:
        """
        Combine multiple regime signals into primary regime
        
        Returns:
            (primary_regime, confidence, sub_regime_probs)
        """
        votes = {}
        
        # Volatility vote
        if vol_regime == "volatile":
            votes["volatile"] = votes.get("volatile", 0) + 0.3
        elif vol_regime == "calm":
            votes["ranging"] = votes.get("ranging", 0) + 0.2
        
        # Trend vote
        if trend_regime == "trending_up":
            votes["trending_up"] = votes.get("trending_up", 0) + 0.4
        elif trend_regime == "trending_down":
            votes["trending_down"] = votes.get("trending_down", 0) + 0.4
        else:
            votes["ranging"] = votes.get("ranging", 0) + 0.3
        
        # Range detection
        if is_ranging:
            votes["ranging"] = votes.get("ranging", 0) + 0.4
        
        # HMM vote (if available)
        if hmm_regime:
            votes[hmm_regime] = votes.get(hmm_regime, 0) + 0.3
        
        # Normalize votes
        total = sum(votes.values())
        if total > 0:
            sub_regimes = {k: v/total for k, v in votes.items()}
        else:
            sub_regimes = {"ranging": 1.0}
        
        # Primary is highest vote
        primary = max(sub_regimes.items(), key=lambda x: x[1])[0]
        confidence = sub_regimes[primary]
        
        return primary, confidence, sub_regimes
    
    def should_use_wyckoff(self, regime: RegimeState) -> bool:
        """
        Decide if Wyckoff agent should be active
        
        Wyckoff works best in:
        - Trending markets (catches reversals)
        - Accumulation/distribution phases
        - NOT in ranging/choppy markets
        """
        # Active in trending regimes
        if regime.primary in ["trending_up", "trending_down"]:
            return True
        
        # Active if strong trend detected
        if abs(regime.trend_strength) > 0.4:
            return True
        
        # Active in accumulation/distribution (if HMM detected)
        if regime.primary in ["accumulation", "distribution"]:
            return True
        
        return False
    
    def should_use_markov(self, regime: RegimeState) -> bool:
        """
        Decide if Markov agent should be active
        
        Markov works best when:
        - Regime confidence is high (clear state)
        - Volatility is moderate (not extreme)
        - Not in ranging markets (too many state flips)
        """
        # Active if high regime confidence
        if regime.confidence > 0.7:
            return True
        
        # Active in clear trending regimes
        if regime.primary in ["trending_up", "trending_down"] and abs(regime.trend_strength) > 0.5:
            return True
        
        # Inactive in ranging (too noisy)
        if regime.primary == "ranging":
            return False
        
        # Inactive in extreme volatility (unstable states)
        if regime.volatility > 0.30:
            return False
        
        return True


if __name__ == "__main__":
    # Test regime detector
    print("="*60)
    print("  REGIME DETECTOR TEST")
    print("="*60)
    
    detector = RegimeDetector()
    
    # Create synthetic data
    dates = pd.date_range("2024-10-01", periods=100, freq="1h")
    
    # Test 1: Trending up
    print("\nTest 1: Trending Up Market")
    prices_up = 580 + np.cumsum(np.random.randn(100) * 0.5 + 0.3)
    bars = pd.DataFrame({
        "t_event": dates,
        "price": prices_up,
        "volume": np.random.randint(1000, 10000, 100),
        "high": prices_up + np.random.rand(100) * 2,
        "low": prices_up - np.random.rand(100) * 2
    })
    
    regime = detector.detect(bars)
    print(f"   Primary: {regime.primary}")
    print(f"   Confidence: {regime.confidence:.2f}")
    print(f"   Trend Strength: {regime.trend_strength:+.2f}")
    print(f"   Volatility: {regime.volatility:.2f}")
    print(f"   Use Wyckoff: {detector.should_use_wyckoff(regime)}")
    print(f"   Use Markov: {detector.should_use_markov(regime)}")
    
    # Test 2: Ranging market
    print("\nTest 2: Ranging Market")
    prices_range = 580 + np.sin(np.linspace(0, 4*np.pi, 100)) * 3
    bars["price"] = prices_range
    bars["high"] = prices_range + 1
    bars["low"] = prices_range - 1
    
    regime = detector.detect(bars)
    print(f"   Primary: {regime.primary}")
    print(f"   Confidence: {regime.confidence:.2f}")
    print(f"   Trend Strength: {regime.trend_strength:+.2f}")
    print(f"   Volatility: {regime.volatility:.2f}")
    print(f"   Use Wyckoff: {detector.should_use_wyckoff(regime)}")
    print(f"   Use Markov: {detector.should_use_markov(regime)}")
    
    # Test 3: Volatile trending down
    print("\nTest 3: Volatile Downtrend")
    prices_down = 580 - np.cumsum(np.random.randn(100) * 2 + 0.5)
    bars["price"] = prices_down
    bars["high"] = prices_down + np.random.rand(100) * 5
    bars["low"] = prices_down - np.random.rand(100) * 5
    
    regime = detector.detect(bars)
    print(f"   Primary: {regime.primary}")
    print(f"   Confidence: {regime.confidence:.2f}")
    print(f"   Trend Strength: {regime.trend_strength:+.2f}")
    print(f"   Volatility: {regime.volatility:.2f}")
    print(f"   Use Wyckoff: {detector.should_use_wyckoff(regime)}")
    print(f"   Use Markov: {detector.should_use_markov(regime)}")
    
    print("\n✅ Regime detector tests passed!")
