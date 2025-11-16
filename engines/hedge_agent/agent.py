"""
Hedge Agent - Pure Interpretation Layer

Canonical v3.0 implementation following the complete specification.

The Hedge Agent performs ONE job only:
    Convert Hedge Engine pressure fields → Normalized directional signals

It does NOT:
- Compute Greeks
- Perform PDE modeling
- Generate trades
- Size positions

It ONLY:
- Reads pre-computed pressure fields
- Normalizes and classifies field state
- Assigns direction, strength, and confidence
- Passes clean typed output to Composer
"""

from typing import Dict, Optional

from .schemas import HedgeAgentInput, HedgeAgentOutput


class HedgeAgent:
    """
    Canonical Hedge Agent v3.0 - Pure Interpreter.
    
    Converts Hedge Engine pressure fields into:
    - Direction classification (strong/weak bull/bear, neutral, chaotic)
    - Strength [0-1] (energy cost to move price)
    - Confidence [0-1] (with regime-based haircuts)
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize Hedge Agent with optional configuration.
        
        Args:
            config: Optional configuration dict with thresholds
        """
        self.config = config or {}
        
        # Direction thresholds
        self.neutral_threshold = self.config.get("neutral_net_pressure_abs_max", 0.05)
        self.weak_strength_max = self.config.get("weak_strength_max", 0.25)
        self.strong_strength_min = self.config.get("strong_strength_min", 0.65)
        
        # Confidence haircuts
        self.jump_haircut = self.config.get("jump_regime_haircut", 0.35)
        self.double_well_haircut = self.config.get("double_well_regime_haircut", 0.50)
        self.realized_mismatch_haircut = self.config.get("realized_mismatch_haircut", 0.55)
        
        # Realized move threshold
        self.realized_mismatch_threshold = self.config.get(
            "realized_mismatch_threshold", -0.5
        )
    
    def interpret(self, x: HedgeAgentInput) -> HedgeAgentOutput:
        """
        Pure interpretation function.
        
        Converts Hedge Engine output into normalized directional signal.
        
        Args:
            x: HedgeAgentInput with all pre-computed fields
            
        Returns:
            HedgeAgentOutput with direction, strength, confidence
        """
        notes = []
        
        # ================================================================
        # 1) DIRECTION CLASSIFICATION
        # ================================================================
        # Based purely on net pressure magnitude and sign
        
        if abs(x.net_pressure) < self.neutral_threshold:
            direction = "neutral"
        else:
            # Determine bull/bear from sign
            if x.net_pressure > 0:
                base_direction = "bull"
            else:
                base_direction = "bear"
            
            # Strength descriptor added after strength calculation
            direction = base_direction
        
        # ================================================================
        # 2) STRENGTH CALCULATION
        # ================================================================
        # Strength = normalized energy cost to move price
        # Higher strength = harder to move (high elasticity/friction)
        
        # Components of strength (all from pre-computed fields)
        curvature_term = abs(x.gamma_curvature)
        friction_term = abs(x.cross_gamma)
        vol_term = abs(x.volatility_drag)
        
        # Weighted combination
        raw_strength = (
            curvature_term +
            0.5 * friction_term +
            0.25 * vol_term
        )
        
        # Normalize to [0, 1] with soft cap
        strength = min(1.0, raw_strength)
        
        # ================================================================
        # 3) CONFIDENCE MODIFIERS
        # ================================================================
        # Start with Hedge Engine's base confidence
        confidence = x.confidence
        
        # Apply regime-based haircuts
        
        # Jump-risk regime → severe confidence haircut
        if x.regime == "jump":
            confidence *= self.jump_haircut
            notes.append("jump-risk haircut")
        
        # Double-well regime → ambiguity haircut
        if x.regime == "double_well":
            confidence *= self.double_well_haircut
            notes.append("double-well ambiguity")
        
        # Realized move mismatch → prediction vs reality divergence
        if x.realized_move_score < self.realized_mismatch_threshold:
            confidence *= self.realized_mismatch_haircut
            notes.append("realized move mismatch")
        
        # Clamp confidence to valid range
        confidence = max(0.0, min(1.0, confidence))
        
        # ================================================================
        # 4) QUALITATIVE DIRECTION TAGS
        # ================================================================
        # Add strength qualifiers to bull/bear directions
        
        if direction in ("bull", "bear"):
            if strength < self.weak_strength_max:
                direction = f"weak {direction}"
            elif strength > self.strong_strength_min:
                direction = f"strong {direction}"
            # else: just "bull" or "bear" (moderate strength)
        
        # ================================================================
        # 5) CHAOTIC DETECTION
        # ================================================================
        # If confidence is very low and regime is unstable, mark as chaotic
        
        if confidence < 0.2 and x.regime in ("double_well", "jump"):
            direction = "chaotic"
            notes.append("low confidence + unstable regime")
        
        # ================================================================
        # 6) ADDITIONAL NOTES
        # ================================================================
        # Provide context for downstream Composer
        
        if abs(x.vanna_drift) > 0.5:
            notes.append("high vanna drift")
        
        if abs(x.charm_decay) > 0.5:
            notes.append("significant charm decay")
        
        if abs(x.cross_asset_pressure) > 0.3:
            notes.append("cross-asset influence")
        
        # ================================================================
        # RETURN TYPED OUTPUT
        # ================================================================
        return HedgeAgentOutput(
            direction=direction,
            strength=strength,
            confidence=confidence,
            regime=x.regime,
            notes=notes,
        )
