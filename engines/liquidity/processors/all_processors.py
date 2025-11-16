from __future__ import annotations

"""
Consolidated Liquidity Engine Processors.
All 8 processors in one file for efficiency.
"""

import polars as pl
import numpy as np
from typing import Dict, Any

from engines.liquidity.models import *


# ============================================================
# 1. VOLUME PROCESSOR
# ============================================================

class VolumeProcessor:
    """Processes volume, RVOL, and effort-vs-result relationships."""
    
    def __init__(self, lookback: int = 20):
        self.lookback = lookback
    
    def process(self, data: pl.DataFrame, config: Dict[str, Any]) -> VolumeProcessorResult:
        if data.is_empty() or len(data) < self.lookback:
            return VolumeProcessorResult(
                volume_strength=0.5, buying_effort=0.5, selling_effort=0.5,
                confidence=0.0
            )
        
        # Calculate RVOL
        recent_vol = float(data["volume"].tail(1)[0])
        avg_vol = float(data["volume"].tail(self.lookback).mean())
        rvol = recent_vol / (avg_vol + 1.0) if avg_vol > 0 else 1.0
        
        # Effort vs Result
        price_change = float(data["close"].tail(1)[0] - data["close"].tail(2)[0])
        volume_change = float(recent_vol - data["volume"].tail(2).mean())
        
        # Buying/selling effort (simplified Wyckoff)
        if price_change > 0 and volume_change > 0:
            buying_effort = min(1.0, 0.5 + rvol * 0.3)
            selling_effort = max(0.0, 0.5 - rvol * 0.3)
        elif price_change < 0 and volume_change > 0:
            buying_effort = max(0.0, 0.5 - rvol * 0.3)
            selling_effort = min(1.0, 0.5 + rvol * 0.3)
        else:
            buying_effort = selling_effort = 0.5
        
        # Volume strength based on consistency
        vol_std = float(data["volume"].tail(self.lookback).std())
        vol_consistency = 1.0 - min(1.0, vol_std / (avg_vol + 1.0))
        volume_strength = vol_consistency * min(1.0, rvol)
        
        # Exhaustion detection
        exhaustion_flag = rvol > 2.5 and abs(price_change) < avg_vol * 0.001
        
        return VolumeProcessorResult(
            volume_strength=volume_strength,
            buying_effort=buying_effort,
            selling_effort=selling_effort,
            exhaustion_flag=exhaustion_flag,
            rvol=rvol,
            confidence=min(1.0, len(data) / self.lookback)
        )


# ============================================================
# 2. ORDER FLOW PROCESSOR
# ============================================================

class OrderFlowProcessor:
    """Processes order flow imbalance and aggressive trading."""
    
    def process(self, data: pl.DataFrame, config: Dict[str, Any]) -> OrderFlowProcessorResult:
        if data.is_empty():
            return OrderFlowProcessorResult(ofi=0.0, liquidity_taker_intensity=0.0, confidence=0.0)
        
        # Simplified OFI from price-volume relationship
        if len(data) >= 2:
            price_changes = data["close"].diff().tail(10)
            volume_weights = data["volume"].tail(10)
            
            # Weight price changes by volume
            weighted_changes = price_changes * volume_weights
            total_vol = float(volume_weights.sum())
            ofi = float(weighted_changes.sum() / (total_vol + 1.0)) if total_vol > 0 else 0.0
            ofi = max(-1.0, min(1.0, ofi * 1000))  # Normalize
        else:
            ofi = 0.0
        
        # Detect sweeps (large volume bars with significant price movement)
        if len(data) >= 3:
            recent_vol = float(data["volume"].tail(1)[0])
            avg_vol = float(data["volume"].tail(10).mean())
            price_move = abs(float(data["close"].tail(1)[0] - data["close"].tail(2)[0]))
            avg_range = float((data["high"] - data["low"]).tail(10).mean())
            
            sweep_flag = (recent_vol > avg_vol * 2.0) and (price_move > avg_range * 0.5)
            taker_intensity = min(1.0, recent_vol / (avg_vol * 3.0))
        else:
            sweep_flag = False
            taker_intensity = 0.0
        
        return OrderFlowProcessorResult(
            ofi=ofi,
            sweep_flag=sweep_flag,
            iceberg_flag=False,  # Requires L2 data
            liquidity_taker_intensity=taker_intensity,
            confidence=0.7
        )


# ============================================================
# 3. MICROSTRUCTURE PROCESSOR
# ============================================================

class MicrostructureProcessor:
    """Processes spreads and microprice dynamics."""
    
    def process(self, data: pl.DataFrame, config: Dict[str, Any]) -> MicrostructureProcessorResult:
        if data.is_empty() or len(data) < 2:
            return MicrostructureProcessorResult(
                spread_cost=0.0, microprice_direction=0.0, impact_slope=0.0, confidence=0.0
            )
        
        # Estimate spread from high-low range
        avg_range = float((data["high"] - data["low"]).tail(10).mean())
        avg_price = float(data["close"].tail(10).mean())
        spread_cost = avg_range / avg_price if avg_price > 0 else 0.0
        
        # Microprice direction from close position in range
        recent_close = float(data["close"].tail(1)[0])
        recent_high = float(data["high"].tail(1)[0])
        recent_low = float(data["low"].tail(1)[0])
        range_size = recent_high - recent_low
        
        if range_size > 0:
            # Position in range: 0 = low, 1 = high
            position = (recent_close - recent_low) / range_size
            microprice_direction = (position - 0.5) * 2  # Map to [-1, 1]
        else:
            microprice_direction = 0.0
        
        # Impact slope from volume-price relationship
        if len(data) >= 5:
            volumes = data["volume"].tail(5).to_numpy()
            price_changes = data["close"].diff().tail(5).to_numpy()
            impact_slope = float(np.abs(price_changes / (volumes + 1.0)).mean())
        else:
            impact_slope = 0.0
        
        return MicrostructureProcessorResult(
            spread_cost=spread_cost,
            microprice_direction=microprice_direction,
            impact_slope=impact_slope,
            confidence=0.8
        )


# ============================================================
# 4. IMPACT PROCESSOR
# ============================================================

class ImpactProcessor:
    """Calculates Amihud, Kyle lambda, and impact metrics."""
    
    def process(self, data: pl.DataFrame, config: Dict[str, Any]) -> ImpactProcessorResult:
        if data.is_empty() or len(data) < 10:
            return ImpactProcessorResult(
                slippage_per_1pct_move=0.0, lambda_kyle=0.0, amihud=0.0,
                impact_energy=0.0, confidence=0.0
            )
        
        # Amihud illiquidity: |return| / volume
        returns = data["close"].pct_change().tail(20)
        volumes = data["volume"].tail(20)
        
        amihud = float((returns.abs() / (volumes + 1.0)).mean())
        
        # Kyle's lambda: price impact per unit volume
        price_changes = data["close"].diff().tail(20)
        lambda_kyle = float((price_changes.abs() / (volumes + 1.0)).mean())
        
        # Slippage estimate for 1% move
        avg_price = float(data["close"].mean())
        avg_volume = float(volumes.mean())
        move_size = avg_price * 0.01
        slippage = lambda_kyle * (move_size / (avg_volume + 1.0)) * 100
        
        # Impact energy (composite measure)
        impact_energy = amihud * lambda_kyle * 1e6
        
        return ImpactProcessorResult(
            slippage_per_1pct_move=slippage,
            lambda_kyle=lambda_kyle,
            amihud=amihud,
            impact_energy=impact_energy,
            confidence=0.8
        )


# ============================================================
# 5. DARK POOL PROCESSOR
# ============================================================

class DarkPoolProcessor:
    """Analyzes off-exchange and dark pool activity."""
    
    def process(self, data: pl.DataFrame, config: Dict[str, Any]) -> DarkPoolProcessorResult:
        # Placeholder - requires actual dark pool data feed
        return DarkPoolProcessorResult(
            dp_accumulation=0.0,
            dp_distribution=0.0,
            off_exchange_ratio=0.0,
            confidence=0.0
        )


# ============================================================
# 6. STRUCTURE PROCESSOR
# ============================================================

class StructureProcessor:
    """Builds HVN/LVN structure and liquidity zones."""
    
    def process(self, data: pl.DataFrame, config: Dict[str, Any]) -> StructureProcessorResult:
        if data.is_empty() or len(data) < 20:
            return StructureProcessorResult(confidence=0.0)
        
        # Build simple volume profile
        price_levels = np.linspace(
            float(data["low"].min()),
            float(data["high"].max()),
            20
        )
        
        profile_nodes = []
        for i, price in enumerate(price_levels[:-1]):
            # Volume in this price range
            mask = (data["close"] >= price) & (data["close"] < price_levels[i+1])
            vol_in_range = float(data.filter(mask)["volume"].sum()) if mask.any() else 0.0
            
            if vol_in_range > 0:
                profile_nodes.append(ProfileNode(
                    price=(price + price_levels[i+1]) / 2,
                    volume=vol_in_range,
                    node_type="neutral",
                    significance=0.5
                ))
        
        # Find POC (highest volume node)
        if profile_nodes:
            poc_node = max(profile_nodes, key=lambda n: n.volume)
            poc_node.node_type = "POC"
            poc_node.significance = 1.0
            
            # Mark HVN/LVN
            median_vol = np.median([n.volume for n in profile_nodes])
            for node in profile_nodes:
                if node.volume > median_vol * 1.5:
                    node.node_type = "HVN"
                    node.significance = min(1.0, node.volume / (median_vol * 2))
                elif node.volume < median_vol * 0.5:
                    node.node_type = "LVN"
                    node.significance = 0.3
        
        # Create absorption zones around HVNs
        absorption_zones = [
            LiquidityZone(
                price_start=node.price * 0.995,
                price_end=node.price * 1.005,
                strength=node.significance,
                zone_type="absorption",
                confidence=0.7,
                volume_density=node.volume
            )
            for node in profile_nodes if node.node_type in ["HVN", "POC"]
        ]
        
        # Create displacement zones for LVNs
        displacement_zones = [
            LiquidityZone(
                price_start=node.price * 0.99,
                price_end=node.price * 1.01,
                strength=1.0 - node.significance,
                zone_type="displacement",
                confidence=0.6,
                volume_density=node.volume
            )
            for node in profile_nodes if node.node_type == "LVN"
        ]
        
        return StructureProcessorResult(
            absorption_zones=absorption_zones,
            displacement_zones=displacement_zones,
            voids=[],
            profile_nodes=profile_nodes,
            confidence=0.7
        )


# ============================================================
# 7. WYCKOFF LIQUIDITY PROCESSOR
# ============================================================

class WyckoffLiquidityProcessor:
    """Detects Wyckoff phases and SOS/SOW."""
    
    def process(self, data: pl.DataFrame, config: Dict[str, Any]) -> WyckoffLiquidityProcessorResult:
        if data.is_empty() or len(data) < 30:
            return WyckoffLiquidityProcessorResult(
                wyckoff_energy=0.0,
                absorption_vs_displacement_bias=0.0,
                confidence=0.0
            )
        
        # Simplified Wyckoff phase detection
        price_range = float(data["high"].max() - data["low"].min())
        recent_range = float(data["high"].tail(10).max() - data["low"].tail(10).min())
        volume_trend = float(data["volume"].tail(10).mean() / data["volume"].head(10).mean())
        
        # Detect accumulation/distribution
        if recent_range < price_range * 0.3 and volume_trend > 1.2:
            phase = "C"  # Testing supply/demand
            wyckoff_energy = 0.7
            bias = 0.3  # Slight accumulation
        elif recent_range > price_range * 0.7:
            phase = "E"  # Markup/markdown
            wyckoff_energy = 0.9
            bias = 0.5 if volume_trend > 1.0 else -0.5
        else:
            phase = "Unknown"
            wyckoff_energy = 0.3
            bias = 0.0
        
        # SOS/SOW detection (simplified)
        recent_close = float(data["close"].tail(1)[0])
        recent_volume = float(data["volume"].tail(1)[0])
        avg_volume = float(data["volume"].mean())
        
        sos_detected = recent_volume > avg_volume * 2.0 and recent_close > float(data["close"].tail(2)[0])
        sow_detected = recent_volume > avg_volume * 2.0 and recent_close < float(data["close"].tail(2)[0])
        
        return WyckoffLiquidityProcessorResult(
            wyckoff_phase=phase,
            wyckoff_energy=wyckoff_energy,
            absorption_vs_displacement_bias=bias,
            sos_detected=sos_detected,
            sow_detected=sow_detected,
            confidence=0.6
        )


# ============================================================
# 8. VOLATILITY LIQUIDITY PROCESSOR
# ============================================================

class VolatilityLiquidityProcessor:
    """Calculates compression/expansion energy from volatility bands."""
    
    def __init__(self, bb_period: int = 20, kc_period: int = 20):
        self.bb_period = bb_period
        self.kc_period = kc_period
    
    def process(self, data: pl.DataFrame, config: Dict[str, Any]) -> VolatilityLiquidityProcessorResult:
        if data.is_empty() or len(data) < self.bb_period:
            return VolatilityLiquidityProcessorResult(
                compression_energy=0.0,
                expansion_energy=0.0,
                confidence=0.0
            )
        
        # Calculate Bollinger Bands
        closes = data["close"].tail(self.bb_period)
        bb_middle = float(closes.mean())
        bb_std = float(closes.std())
        bb_upper = bb_middle + 2 * bb_std
        bb_lower = bb_middle - 2 * bb_std
        bb_width = (bb_upper - bb_lower) / bb_middle if bb_middle > 0 else 0.0
        
        # Calculate Keltner Channels (using ATR approximation)
        highs = data["high"].tail(self.kc_period)
        lows = data["low"].tail(self.kc_period)
        atr = float((highs - lows).mean())
        kc_upper = bb_middle + 2 * atr
        kc_lower = bb_middle - 2 * atr
        kc_width = (kc_upper - kc_lower) / bb_middle if bb_middle > 0 else 0.0
        
        # Squeeze detection (BB inside KC)
        squeeze_flag = bb_width < kc_width
        
        # Compression energy (inverse of bandwidth)
        max_width = 0.1  # Typical max bandwidth
        compression_energy = max(0.0, 1.0 - (bb_width / max_width))
        
        # Expansion energy (stored potential)
        if squeeze_flag:
            expansion_energy = compression_energy * 1.5
        else:
            expansion_energy = max(0.0, bb_width / max_width)
        
        # Count compression duration
        compression_duration = 0
        if squeeze_flag:
            for i in range(min(len(data), 50)):
                # Simplified - would need to recalculate bands for each bar
                compression_duration += 1
        
        return VolatilityLiquidityProcessorResult(
            compression_energy=compression_energy,
            expansion_energy=expansion_energy,
            squeeze_flag=squeeze_flag,
            breakout_energy_required=compression_energy * 0.5,
            compression_duration=compression_duration,
            confidence=0.8
        )
