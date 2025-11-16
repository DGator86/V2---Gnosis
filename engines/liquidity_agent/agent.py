"""  
Liquidity Agent - Pure Interpretation Layer

Canonical v1.0 implementation following the complete specification.

The Liquidity Agent performs ONE job only:
    Convert Liquidity Engine metrics → Normalized liquidity signals

It does NOT:
- Compute liquidity metrics
- Fetch market data
- Generate trades
- Size positions

It ONLY:
- Reads pre-computed liquidity metrics
- Classifies liquidity environment
- Assigns direction, strength, and confidence
- Passes clean typed output to Composer
"""

from typing import Dict, List, Optional

from .schemas import LiquidityAgentInput, LiquidityAgentOutput


class LiquidityAgent:
    """
    Canonical Liquidity Agent v1.0 - Pure Interpreter.
    
    Converts Liquidity Engine metrics into:
    - Direction classification (supportive/fragile/vacuum/balanced/chaotic)
    - Strength [0-1] (fragility / cost to move size)
    - Confidence [0-1] (with regime-based haircuts)
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize Liquidity Agent with optional configuration.
        
        Args:
            config: Optional configuration dict with thresholds
        """
        self.config = config or {}
        
        # Direction thresholds
        self.neutral_threshold = self.config.get("neutral_net_liquidity_abs_max", 0.05)
        
        # Strength weights
        self.impact_weight = self.config.get("impact_weight", 0.5)
        self.gaps_weight = self.config.get("gaps_weight", 0.5)
        self.vol_of_liquidity_weight = self.config.get("vol_of_liquidity_weight", 0.25)
        
        # Confidence haircuts
        self.vacuum_haircut = self.config.get("vacuum_regime_haircut", 0.6)
        self.transition_haircut = self.config.get("transition_regime_haircut", 0.7)
        self.bad_slippage_haircut = self.config.get("bad_slippage_haircut", 0.6)
        self.high_vol_liq_haircut = self.config.get("high_vol_of_liquidity_haircut", 0.7)
        
        # Thresholds
        self.realized_slippage_threshold = self.config.get("realized_slippage_threshold", 0.3)
        self.high_vol_liq_threshold = self.config.get("high_vol_of_liquidity_threshold", 0.4)
        self.dark_pool_bias_threshold = self.config.get("dark_pool_bias_threshold", 0.5)
        self.volume_profile_cliff_threshold = self.config.get("volume_profile_cliff_threshold", 0.7)
        self.liquidity_gaps_threshold = self.config.get("liquidity_gaps_threshold", 0.5)
        self.ofi_threshold = self.config.get("ofi_threshold", 0.5)
    
    def interpret(self, x: LiquidityAgentInput) -> LiquidityAgentOutput:
        """
        Pure interpretation function.
        
        Converts Liquidity Engine output into normalized liquidity signal.
        
        Args:
            x: LiquidityAgentInput with all pre-computed metrics
            
        Returns:
            LiquidityAgentOutput with direction, strength, confidence
        """
        notes: List[str] = []
        
        # ================================================================
        # 1) BASE DIRECTION FROM NET_LIQUIDITY_PRESSURE
        # ================================================================
        abs_net = abs(x.net_liquidity_pressure)
        
        if abs_net < self.neutral_threshold:
            direction = "balanced"
        else:
            if x.net_liquidity_pressure > 0:
                direction = "supportive"  # Absorption / supportive book
            else:
                direction = "fragile"  # Distributive / rejecting
        
        # ================================================================
        # 2) STRENGTH CALCULATION (FRAGILITY / COST TO MOVE SIZE)
        # ================================================================
        # Intuition:
        #   - High Amihud/Kyle → high impact → high fragility
        #   - High gaps → fragile
        #   - High depth → less fragile
        
        # Impact term (Amihud + Kyle lambda)
        impact_term = max(0.0, x.amihud_lambda) + max(0.0, x.kyle_lambda)
        
        # Gaps term
        gaps_term = max(0.0, x.liquidity_gaps_score)
        
        # Depth reducer (more depth = less fragile)
        depth_term = max(0.0, x.book_depth_score)
        depth_reducer = 1.0 / (1.0 + depth_term)  # More depth → smaller reducer
        
        # Raw strength calculation
        raw_strength = (
            impact_term * self.impact_weight +
            gaps_term * self.gaps_weight
        ) * depth_reducer
        
        # Add contribution from volatility of liquidity (unstable book)
        raw_strength += max(0.0, x.vol_of_liquidity) * self.vol_of_liquidity_weight
        
        # Normalize and clamp to [0, 1]
        strength = max(0.0, min(raw_strength, 1.0))
        
        # ================================================================
        # 3) CONFIDENCE ADJUSTMENTS
        # ================================================================
        confidence = x.confidence
        
        # Liquidity vacuum regime → higher fragility but lower confidence
        if x.regime == "vacuum":
            confidence *= self.vacuum_haircut
            notes.append("liquidity vacuum regime")
        
        # Transition regime → noisy, apply haircut
        if x.regime == "transition":
            confidence *= self.transition_haircut
            notes.append("transition liquidity regime")
        
        # Realized slippage much worse than expected
        if x.realized_slippage_score > self.realized_slippage_threshold:
            confidence *= self.bad_slippage_haircut
            notes.append("worse-than-expected realized slippage")
        
        # Very high volatility of liquidity → unstable microstructure
        if x.vol_of_liquidity > self.high_vol_liq_threshold:
            confidence *= self.high_vol_liq_haircut
            notes.append("high volatility of liquidity (unstable book)")
        
        # Clamp confidence to [0, 1]
        confidence = max(0.0, min(confidence, 1.0))
        
        # ================================================================
        # 4) ENRICH DIRECTION BASED ON REGIME AND KEY METRICS
        # ================================================================
        
        # Liquidity vacuum: specify directional risk
        if x.regime == "vacuum":
            if x.net_liquidity_pressure > 0:
                direction = "liquidity vacuum up"
            elif x.net_liquidity_pressure < 0:
                direction = "liquidity vacuum down"
            else:
                direction = "liquidity vacuum"
        
        # Strong dark pool bias can tilt direction semantics
        if x.dark_pool_bias > self.dark_pool_bias_threshold:
            notes.append("dark-pool accumulation")
        elif x.dark_pool_bias < -self.dark_pool_bias_threshold:
            notes.append("dark-pool distribution")
        
        # Volume profile cliffs: large |slope| suggests structural hazard
        if abs(x.volume_profile_slope) > self.volume_profile_cliff_threshold:
            notes.append("volume profile cliff")
        
        # Liquidity gaps
        if x.liquidity_gaps_score > self.liquidity_gaps_threshold:
            notes.append("significant liquidity gaps")
        
        # Order flow imbalance annotation
        if x.orderflow_imbalance > self.ofi_threshold:
            notes.append("aggressive buy imbalance")
        elif x.orderflow_imbalance < -self.ofi_threshold:
            notes.append("aggressive sell imbalance")
        
        # ================================================================
        # 5) CHAOTIC DETECTION
        # ================================================================
        # If confidence is very low, mark environment as chaotic
        if confidence < 0.2:
            direction = "chaotic"
        
        # ================================================================
        # RETURN TYPED OUTPUT
        # ================================================================
        return LiquidityAgentOutput(
            direction=direction,
            strength=strength,
            confidence=confidence,
            regime=x.regime,
            notes=notes,
        )