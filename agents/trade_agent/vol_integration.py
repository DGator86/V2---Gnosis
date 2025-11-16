# agents/trade_agent/vol_integration.py

"""
Volatility Intelligence Integration for Trade Agent v2.5

Enhances strategy selection with surface-based volatility analytics.
This module bridges the vol_surface module with the existing Trade Agent architecture.
"""

from __future__ import annotations

from typing import Optional

from .schemas import ComposerTradeContext, VolatilityRegime
from .vol_surface import (
    VolSurface,
    IVRankPercentile,
    SkewMetrics,
    VolatilitySignals,
    compute_iv_rank,
    compute_skew_metrics,
    generate_volatility_signals,
)


class VolatilityIntelligence:
    """
    Volatility intelligence layer for Trade Agent v2.5.
    
    Provides surface-based analytics to enhance strategy selection beyond
    basic volatility regime classification.
    """
    
    def __init__(self, default_lookback_days: int = 252):
        """
        Initialize volatility intelligence layer.
        
        Args:
            default_lookback_days: Default lookback for IV rank calculation (252 = 1 year)
        """
        self.default_lookback_days = default_lookback_days
        self._surface_cache: dict[str, VolSurface] = {}
    
    def analyze_surface(
        self,
        surface: VolSurface,
        target_dte: int = 30,
    ) -> tuple[IVRankPercentile, SkewMetrics, VolatilitySignals]:
        """
        Complete surface analysis pipeline.
        
        Args:
            surface: VolSurface object
            target_dte: Target DTE for skew analysis
        
        Returns:
            Tuple of (IV rank, skew metrics, volatility signals)
        """
        iv_rank = compute_iv_rank(surface, self.default_lookback_days)
        skew_metrics = compute_skew_metrics(surface, target_dte)
        vol_signals = generate_volatility_signals(surface, iv_rank, skew_metrics)
        
        return iv_rank, skew_metrics, vol_signals
    
    def enhance_context_with_vol_intel(
        self,
        ctx: ComposerTradeContext,
        surface: Optional[VolSurface] = None,
    ) -> tuple[ComposerTradeContext, Optional[VolatilitySignals]]:
        """
        Enhance ComposerTradeContext with volatility intelligence.
        
        This method refines the volatility_regime field using surface analytics
        and returns actionable volatility signals for strategy selection.
        
        Args:
            ctx: Original ComposerTradeContext from Composer
            surface: Optional VolSurface for the asset
        
        Returns:
            Tuple of (enhanced context, volatility signals)
        """
        if surface is None:
            # No surface data - return original context
            return ctx, None
        
        # Perform full surface analysis
        iv_rank, skew_metrics, vol_signals = self.analyze_surface(surface)
        
        # Refine volatility_regime based on surface analytics
        refined_regime = self._map_signals_to_regime(vol_signals, ctx.volatility_regime)
        
        # Create enhanced context (immutable, so create new instance)
        enhanced_ctx = ctx.model_copy(update={"volatility_regime": refined_regime})
        
        return enhanced_ctx, vol_signals
    
    def _map_signals_to_regime(
        self,
        signals: VolatilitySignals,
        original_regime: VolatilityRegime,
    ) -> VolatilityRegime:
        """
        Map volatility signals to VolatilityRegime enum.
        
        This method refines the Composer's volatility_regime classification
        using surface-based intelligence.
        
        Args:
            signals: VolatilitySignals from surface analysis
            original_regime: Original regime from Composer
        
        Returns:
            Refined VolatilityRegime
        """
        # Priority: expansion/crush signals override other classifications
        if signals.expansion_probability > 0.7:
            return VolatilityRegime.VOL_EXPANSION
        
        if signals.crush_risk > 0.7:
            return VolatilityRegime.VOL_CRUSH
        
        # Map iv_regime string to VolatilityRegime enum
        regime_map = {
            "low": VolatilityRegime.LOW,
            "mid": VolatilityRegime.MID,
            "high": VolatilityRegime.HIGH,
            "expansion": VolatilityRegime.VOL_EXPANSION,
            "crush": VolatilityRegime.VOL_CRUSH,
        }
        
        surface_regime = regime_map.get(signals.iv_regime, original_regime)
        
        # If surface analysis conflicts with original, prefer surface (more granular)
        if surface_regime != original_regime:
            return surface_regime
        
        return original_regime
    
    def get_strategy_preferences(
        self,
        signals: VolatilitySignals,
    ) -> dict[str, float]:
        """
        Generate strategy preference scores based on volatility signals.
        
        Returns a dictionary mapping strategy types to preference scores (0-1).
        Higher scores indicate more favorable conditions for that strategy.
        
        Args:
            signals: VolatilitySignals from surface analysis
        
        Returns:
            Dictionary of strategy_type -> preference_score
        """
        preferences = {}
        
        # Calendar spreads: favorable when IV is low and slight backwardation
        if signals.skew_favorable_for_calendars:
            preferences["calendar_spread"] = 0.9
            preferences["diagonal_spread"] = 0.8
        else:
            preferences["calendar_spread"] = 0.3
            preferences["diagonal_spread"] = 0.4
        
        # Butterflies and condors: favorable when wings are rich
        if signals.rich_wings:
            preferences["iron_condor"] = 0.9
            preferences["broken_wing_butterfly"] = 0.85
        else:
            preferences["iron_condor"] = 0.5
            preferences["broken_wing_butterfly"] = 0.4
        
        # Straddles/strangles: favorable for expansion, unfavorable for crush
        if signals.expansion_probability > 0.6:
            preferences["straddle"] = 0.9
            preferences["strangle"] = 0.85
            preferences["reverse_iron_condor"] = 0.8
        elif signals.crush_risk > 0.6:
            preferences["straddle"] = 0.2
            preferences["strangle"] = 0.2
            preferences["reverse_iron_condor"] = 0.3
        else:
            preferences["straddle"] = 0.5
            preferences["strangle"] = 0.5
            preferences["reverse_iron_condor"] = 0.5
        
        # Directional spreads: neutral to vol profile
        preferences["call_debit_spread"] = 0.6
        preferences["put_debit_spread"] = 0.6
        
        # Synthetics: slightly favor low IV environments
        if signals.iv_regime == "low":
            preferences["synthetic_long"] = 0.7
            preferences["synthetic_short"] = 0.7
        else:
            preferences["synthetic_long"] = 0.5
            preferences["synthetic_short"] = 0.5
        
        return preferences
    
    def cache_surface(self, symbol: str, surface: VolSurface) -> None:
        """Cache a volatility surface for later retrieval."""
        self._surface_cache[symbol] = surface
    
    def get_cached_surface(self, symbol: str) -> Optional[VolSurface]:
        """Retrieve a cached volatility surface."""
        return self._surface_cache.get(symbol)
    
    def clear_cache(self) -> None:
        """Clear the surface cache."""
        self._surface_cache.clear()


def create_vol_intelligence_layer(lookback_days: int = 252) -> VolatilityIntelligence:
    """
    Factory function to create a VolatilityIntelligence instance.
    
    Args:
        lookback_days: Lookback period for IV rank calculation
    
    Returns:
        VolatilityIntelligence instance
    """
    return VolatilityIntelligence(default_lookback_days=lookback_days)
