"""
Universal Liquidity Interpreter - Market Depth Physics Engine
==============================================================

Core framework that translates order book microstructure into liquidity states.

This module implements the liquidity physics framework:
1. Order Book → Depth Profile (liquidity distribution)
2. Depth Profile → Impact Energy (cost to execute)
3. Impact Energy → Slippage Field (price impact)
4. Slippage Field → Liquidity Elasticity (market resistance)

Physics Analogy:
- Order book depth = Potential energy field
- Trade execution = Energy consumption
- Slippage = Friction force
- Liquidity elasticity = Market viscosity

Author: Super Gnosis Development Team
License: MIT
Version: 3.0.0
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import numpy as np
from datetime import datetime
from loguru import logger


@dataclass
class LiquidityState:
    """Complete liquidity state of the market."""
    
    # Impact metrics
    impact_cost: float  # Total cost to execute (bps)
    impact_cost_buy: float  # Cost for buy orders
    impact_cost_sell: float  # Cost for sell orders
    
    # Slippage metrics
    slippage: float  # Expected slippage (bps)
    slippage_buy: float  # Slippage for buy
    slippage_sell: float  # Slippage for sell
    
    # Depth metrics
    depth_score: float  # Order book depth quality (0-1)
    depth_imbalance: float  # Bid/ask depth imbalance (-1 to 1)
    
    # Spread metrics
    spread_bps: float  # Bid-ask spread (bps)
    effective_spread_bps: float  # Effective spread after impact
    
    # Liquidity elasticity
    elasticity: float  # Market resistance to execution
    elasticity_buy: float  # Buy-side elasticity
    elasticity_sell: float  # Sell-side elasticity
    
    # Volume metrics
    volume_profile: float  # Volume distribution score
    volume_imbalance: float  # Buy/sell volume imbalance
    
    # Regime classification
    regime: str  # high_liquidity, medium, low, illiquid
    stability: float  # Regime stability (0-1)
    
    # Metadata
    timestamp: datetime
    confidence: float  # Calculation confidence (0-1)


@dataclass
class OrderBookLevel:
    """Single price level in order book."""
    
    price: float
    size: float  # Volume at this level
    side: str  # 'bid' or 'ask'
    distance_from_mid: float  # Distance in bps
    cumulative_size: float = 0.0  # Cumulative volume


class UniversalLiquidityInterpreter:
    """
    Universal liquidity interpreter for translating order book into liquidity states.
    
    This is the core liquidity physics engine that:
    1. Ingests order book snapshots
    2. Constructs depth profiles
    3. Calculates impact costs
    4. Determines slippage fields
    5. Measures liquidity elasticity
    6. Classifies liquidity regimes
    """
    
    def __init__(
        self,
        impact_scaling: float = 1.0,
        slippage_scaling: float = 1.0,
        min_depth_threshold: float = 1000.0,  # Minimum volume for quality depth
        max_spread_bps: float = 100.0  # Maximum acceptable spread
    ):
        """
        Initialize universal liquidity interpreter.
        
        Args:
            impact_scaling: Scaling factor for impact calculations
            slippage_scaling: Scaling factor for slippage
            min_depth_threshold: Minimum depth for quality scoring
            max_spread_bps: Maximum spread for quality scoring
        """
        self.impact_scaling = impact_scaling
        self.slippage_scaling = slippage_scaling
        self.min_depth_threshold = min_depth_threshold
        self.max_spread_bps = max_spread_bps
        
        logger.info("✅ Universal Liquidity Interpreter initialized")
    
    def interpret(
        self,
        bids: List[Tuple[float, float]],  # [(price, size), ...]
        asks: List[Tuple[float, float]],  # [(price, size), ...]
        mid_price: float,
        volume_24h: float = 0.0,
        execution_size: float = 100.0  # Size to simulate execution
    ) -> LiquidityState:
        """
        Interpret order book into complete liquidity state.
        
        Args:
            bids: List of (price, size) tuples for bid side
            asks: List of (price, size) tuples for ask side
            mid_price: Mid price (best bid + best ask) / 2
            volume_24h: 24-hour volume for context
            execution_size: Size to simulate for impact calculation
        
        Returns:
            Complete LiquidityState
        """
        # Build order book levels
        bid_levels = self._build_levels(bids, mid_price, 'bid')
        ask_levels = self._build_levels(asks, mid_price, 'ask')
        
        # Calculate spread
        if bid_levels and ask_levels:
            best_bid = bid_levels[0].price
            best_ask = ask_levels[0].price
            spread_bps = ((best_ask - best_bid) / mid_price) * 10000
        else:
            spread_bps = self.max_spread_bps
        
        # Calculate depth metrics
        depth_score = self._calculate_depth_score(bid_levels, ask_levels, volume_24h)
        depth_imbalance = self._calculate_depth_imbalance(bid_levels, ask_levels)
        
        # Calculate impact costs
        impact_buy = self._calculate_impact(ask_levels, execution_size, mid_price, 'buy')
        impact_sell = self._calculate_impact(bid_levels, execution_size, mid_price, 'sell')
        impact_cost = (impact_buy + impact_sell) / 2
        
        # Calculate slippage
        slippage_buy = self._calculate_slippage(ask_levels, execution_size, mid_price)
        slippage_sell = self._calculate_slippage(bid_levels, execution_size, mid_price)
        slippage = (slippage_buy + slippage_sell) / 2
        
        # Calculate effective spread
        effective_spread_bps = spread_bps + impact_cost
        
        # Calculate liquidity elasticity
        elasticity_buy = self._calculate_elasticity(ask_levels, mid_price)
        elasticity_sell = self._calculate_elasticity(bid_levels, mid_price)
        elasticity = (elasticity_buy + elasticity_sell) / 2
        
        # Calculate volume metrics
        volume_profile = self._calculate_volume_profile(bid_levels, ask_levels)
        volume_imbalance = self._calculate_volume_imbalance(bid_levels, ask_levels)
        
        # Classify regime
        regime, stability = self._classify_regime(
            spread_bps, depth_score, impact_cost, elasticity
        )
        
        # Calculate confidence
        confidence = self._calculate_confidence(
            bid_levels, ask_levels, spread_bps, volume_24h
        )
        
        return LiquidityState(
            impact_cost=impact_cost,
            impact_cost_buy=impact_buy,
            impact_cost_sell=impact_sell,
            slippage=slippage,
            slippage_buy=slippage_buy,
            slippage_sell=slippage_sell,
            depth_score=depth_score,
            depth_imbalance=depth_imbalance,
            spread_bps=spread_bps,
            effective_spread_bps=effective_spread_bps,
            elasticity=elasticity,
            elasticity_buy=elasticity_buy,
            elasticity_sell=elasticity_sell,
            volume_profile=volume_profile,
            volume_imbalance=volume_imbalance,
            regime=regime,
            stability=stability,
            timestamp=datetime.now(),
            confidence=confidence
        )
    
    def _build_levels(
        self,
        orders: List[Tuple[float, float]],
        mid_price: float,
        side: str
    ) -> List[OrderBookLevel]:
        """Build order book levels with cumulative volumes."""
        levels = []
        cumulative = 0.0
        
        for price, size in orders:
            distance_bps = abs((price - mid_price) / mid_price) * 10000
            cumulative += size
            
            levels.append(OrderBookLevel(
                price=price,
                size=size,
                side=side,
                distance_from_mid=distance_bps,
                cumulative_size=cumulative
            ))
        
        return levels
    
    def _calculate_depth_score(
        self,
        bid_levels: List[OrderBookLevel],
        ask_levels: List[OrderBookLevel],
        volume_24h: float
    ) -> float:
        """
        Calculate order book depth quality score (0-1).
        
        Higher score = better liquidity.
        """
        # Total depth within reasonable distance (50 bps)
        bid_depth = sum(
            level.size for level in bid_levels 
            if level.distance_from_mid < 50
        )
        ask_depth = sum(
            level.size for level in ask_levels 
            if level.distance_from_mid < 50
        )
        
        total_depth = bid_depth + ask_depth
        
        # Normalize by threshold
        depth_factor = min(1.0, total_depth / self.min_depth_threshold)
        
        # Adjust by volume if available
        if volume_24h > 0:
            volume_factor = min(1.0, total_depth / (volume_24h * 0.01))  # 1% of daily volume
            depth_score = (depth_factor + volume_factor) / 2
        else:
            depth_score = depth_factor
        
        return depth_score
    
    def _calculate_depth_imbalance(
        self,
        bid_levels: List[OrderBookLevel],
        ask_levels: List[OrderBookLevel]
    ) -> float:
        """
        Calculate bid/ask depth imbalance (-1 to 1).
        
        Positive = more bid depth (buying pressure)
        Negative = more ask depth (selling pressure)
        """
        bid_depth = sum(level.size for level in bid_levels[:10])  # Top 10 levels
        ask_depth = sum(level.size for level in ask_levels[:10])
        
        if bid_depth + ask_depth == 0:
            return 0.0
        
        imbalance = (bid_depth - ask_depth) / (bid_depth + ask_depth)
        return imbalance
    
    def _calculate_impact(
        self,
        levels: List[OrderBookLevel],
        size: float,
        mid_price: float,
        side: str
    ) -> float:
        """
        Calculate market impact cost in basis points.
        
        Simulates walking the order book to execute size.
        """
        remaining = size
        total_cost = 0.0
        
        for level in levels:
            if remaining <= 0:
                break
            
            executed = min(remaining, level.size)
            impact_bps = level.distance_from_mid
            total_cost += executed * impact_bps
            remaining -= executed
        
        if size > 0:
            avg_impact_bps = total_cost / size
        else:
            avg_impact_bps = 0.0
        
        # If couldn't fill entire order, add penalty
        if remaining > 0:
            avg_impact_bps += remaining / size * 100  # 100 bps penalty per % unfilled
        
        return avg_impact_bps * self.impact_scaling
    
    def _calculate_slippage(
        self,
        levels: List[OrderBookLevel],
        size: float,
        mid_price: float
    ) -> float:
        """
        Calculate expected slippage in basis points.
        
        Slippage = difference between mid price and actual execution price.
        """
        remaining = size
        weighted_price = 0.0
        total_executed = 0.0
        
        for level in levels:
            if remaining <= 0:
                break
            
            executed = min(remaining, level.size)
            weighted_price += level.price * executed
            total_executed += executed
            remaining -= executed
        
        if total_executed > 0:
            avg_price = weighted_price / total_executed
            slippage_bps = abs((avg_price - mid_price) / mid_price) * 10000
        else:
            slippage_bps = 100.0  # Max penalty if no liquidity
        
        return slippage_bps * self.slippage_scaling
    
    def _calculate_elasticity(
        self,
        levels: List[OrderBookLevel],
        mid_price: float
    ) -> float:
        """
        Calculate liquidity elasticity (market resistance).
        
        Elasticity = dPrice/dVolume
        
        Higher elasticity = harder to execute (less liquidity)
        """
        if len(levels) < 2:
            return 1.0
        
        # Calculate price change per unit volume
        price_changes = []
        
        for i in range(min(5, len(levels) - 1)):  # First 5 levels
            price_change = abs(levels[i+1].price - levels[i].price)
            volume_change = levels[i].size
            
            if volume_change > 0:
                elasticity_level = (price_change / mid_price) / volume_change * 10000
                price_changes.append(elasticity_level)
        
        if price_changes:
            # Average elasticity across levels
            elasticity = np.mean(price_changes)
        else:
            elasticity = 1.0
        
        return min(10.0, elasticity)  # Cap at 10
    
    def _calculate_volume_profile(
        self,
        bid_levels: List[OrderBookLevel],
        ask_levels: List[OrderBookLevel]
    ) -> float:
        """
        Calculate volume distribution quality (0-1).
        
        Higher = more evenly distributed liquidity.
        """
        all_sizes = [level.size for level in bid_levels + ask_levels]
        
        if not all_sizes or len(all_sizes) < 2:
            return 0.0
        
        # Calculate coefficient of variation (lower = more uniform)
        cv = np.std(all_sizes) / np.mean(all_sizes) if np.mean(all_sizes) > 0 else 10.0
        
        # Convert to quality score (0-1)
        profile_score = 1.0 / (1.0 + cv)
        
        return profile_score
    
    def _calculate_volume_imbalance(
        self,
        bid_levels: List[OrderBookLevel],
        ask_levels: List[OrderBookLevel]
    ) -> float:
        """
        Calculate buy/sell volume imbalance (-1 to 1).
        
        Based on cumulative volume at different price levels.
        """
        # Weight recent volume more heavily
        bid_volume = sum(
            level.size * np.exp(-level.distance_from_mid / 50)
            for level in bid_levels[:20]
        )
        ask_volume = sum(
            level.size * np.exp(-level.distance_from_mid / 50)
            for level in ask_levels[:20]
        )
        
        if bid_volume + ask_volume == 0:
            return 0.0
        
        imbalance = (bid_volume - ask_volume) / (bid_volume + ask_volume)
        return imbalance
    
    def _classify_regime(
        self,
        spread_bps: float,
        depth_score: float,
        impact_cost: float,
        elasticity: float
    ) -> Tuple[str, float]:
        """
        Classify liquidity regime.
        
        Returns:
            (regime_name, stability_score)
        """
        # Normalize metrics (0-1, lower is better for spread/impact/elasticity)
        spread_norm = min(1.0, spread_bps / self.max_spread_bps)
        impact_norm = min(1.0, impact_cost / 100.0)
        elasticity_norm = min(1.0, elasticity / 10.0)
        
        # Calculate liquidity score (higher = better liquidity)
        liquidity_score = (
            depth_score * 0.4 +
            (1.0 - spread_norm) * 0.3 +
            (1.0 - impact_norm) * 0.2 +
            (1.0 - elasticity_norm) * 0.1
        )
        
        # Classify regime
        if liquidity_score > 0.75:
            regime = "high_liquidity"
            stability = 0.9
        elif liquidity_score > 0.5:
            regime = "medium_liquidity"
            stability = 0.7
        elif liquidity_score > 0.25:
            regime = "low_liquidity"
            stability = 0.5
        else:
            regime = "illiquid"
            stability = 0.3
        
        # Adjust stability based on score consistency
        score_variance = np.var([depth_score, 1-spread_norm, 1-impact_norm, 1-elasticity_norm])
        stability *= (1.0 - min(1.0, score_variance * 2))
        
        return regime, max(0.0, min(1.0, stability))
    
    def _calculate_confidence(
        self,
        bid_levels: List[OrderBookLevel],
        ask_levels: List[OrderBookLevel],
        spread_bps: float,
        volume_24h: float
    ) -> float:
        """
        Calculate confidence in liquidity state calculation.
        
        Higher confidence with:
        - More order book levels
        - Tighter spreads
        - Higher volume
        - More balanced book
        """
        # Level count factor
        level_count = len(bid_levels) + len(ask_levels)
        level_factor = min(1.0, level_count / 40)  # 20 levels each side ideal
        
        # Spread factor (tighter = better)
        spread_factor = 1.0 - min(1.0, spread_bps / self.max_spread_bps)
        
        # Volume factor
        if volume_24h > 0:
            volume_factor = min(1.0, volume_24h / 100000)  # Normalize by 100k volume
        else:
            volume_factor = 0.5
        
        # Balance factor
        bid_count = len(bid_levels)
        ask_count = len(ask_levels)
        if bid_count + ask_count > 0:
            balance_factor = 1.0 - abs(bid_count - ask_count) / (bid_count + ask_count)
        else:
            balance_factor = 0.0
        
        # Combined confidence
        confidence = (
            level_factor * 0.3 +
            spread_factor * 0.3 +
            volume_factor * 0.2 +
            balance_factor * 0.2
        )
        
        return max(0.0, min(1.0, confidence))


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def create_interpreter(
    impact_scaling: float = 1.0,
    slippage_scaling: float = 1.0
) -> UniversalLiquidityInterpreter:
    """
    Create universal liquidity interpreter with default settings.
    
    Args:
        impact_scaling: Impact calculation scaling
        slippage_scaling: Slippage calculation scaling
    
    Returns:
        Configured UniversalLiquidityInterpreter
    """
    return UniversalLiquidityInterpreter(
        impact_scaling=impact_scaling,
        slippage_scaling=slippage_scaling
    )


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    print("\n💧 Universal Liquidity Interpreter Example\n")
    
    # Create interpreter
    interpreter = create_interpreter()
    
    # Sample order book (SPY-like liquidity)
    mid_price = 450.0
    
    bids = [
        (449.99, 100),
        (449.98, 150),
        (449.97, 200),
        (449.96, 180),
        (449.95, 250),
        (449.90, 300),
        (449.85, 400),
        (449.80, 500),
        (449.75, 600),
        (449.70, 700),
    ]
    
    asks = [
        (450.01, 120),
        (450.02, 140),
        (450.03, 190),
        (450.04, 170),
        (450.05, 240),
        (450.10, 320),
        (450.15, 380),
        (450.20, 480),
        (450.25, 580),
        (450.30, 680),
    ]
    
    # Interpret liquidity state
    liquidity_state = interpreter.interpret(
        bids=bids,
        asks=asks,
        mid_price=mid_price,
        volume_24h=10000000,
        execution_size=1000
    )
    
    # Display results
    print(f"Mid Price: ${mid_price:.2f}")
    print(f"\n💰 IMPACT COSTS:")
    print(f"   Total Impact: {liquidity_state.impact_cost:.2f} bps")
    print(f"   Buy Impact: {liquidity_state.impact_cost_buy:.2f} bps")
    print(f"   Sell Impact: {liquidity_state.impact_cost_sell:.2f} bps")
    print(f"\n📉 SLIPPAGE:")
    print(f"   Expected Slippage: {liquidity_state.slippage:.2f} bps")
    print(f"   Buy Slippage: {liquidity_state.slippage_buy:.2f} bps")
    print(f"   Sell Slippage: {liquidity_state.slippage_sell:.2f} bps")
    print(f"\n📊 DEPTH METRICS:")
    print(f"   Depth Score: {liquidity_state.depth_score:.2%}")
    print(f"   Depth Imbalance: {liquidity_state.depth_imbalance:+.2f}")
    print(f"\n📏 SPREAD:")
    print(f"   Bid-Ask Spread: {liquidity_state.spread_bps:.2f} bps")
    print(f"   Effective Spread: {liquidity_state.effective_spread_bps:.2f} bps")
    print(f"\n🔧 ELASTICITY:")
    print(f"   Market Elasticity: {liquidity_state.elasticity:.4f}")
    print(f"   Buy Elasticity: {liquidity_state.elasticity_buy:.4f}")
    print(f"   Sell Elasticity: {liquidity_state.elasticity_sell:.4f}")
    print(f"\n📈 VOLUME:")
    print(f"   Volume Profile: {liquidity_state.volume_profile:.2%}")
    print(f"   Volume Imbalance: {liquidity_state.volume_imbalance:+.2f}")
    print(f"\n🎯 REGIME:")
    print(f"   Classification: {liquidity_state.regime}")
    print(f"   Stability: {liquidity_state.stability:.2%}")
    print(f"   Confidence: {liquidity_state.confidence:.2%}")
    
    print("\n✅ Universal Liquidity Interpreter ready for production!")
