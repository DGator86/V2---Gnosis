"""
Volume/Liquidity engine
Analyzes order flow, tape dynamics, and microstructure
"""
from typing import Dict, Any, List
from datetime import datetime
from schemas import EngineOutput
from ..orchestration.logger import get_logger

logger = get_logger(__name__)


class VolumeEngine:
    """
    Engine for volume and liquidity analysis
    Computes flow metrics, VWAP, imbalances, support/resistance
    """
    
    def __init__(self, window_bars: int = 20):
        self.window_bars = window_bars
        logger.info(f"Volume engine initialized (window={window_bars})")
    
    def _compute_vwap(self, trades: List[Dict[str, Any]]) -> float:
        """Compute volume-weighted average price"""
        if not trades:
            return 0.0
        
        total_pv = sum(t.get("price", 0) * t.get("size", 0) for t in trades)
        total_v = sum(t.get("size", 0) for t in trades)
        
        return total_pv / total_v if total_v > 0 else 0.0
    
    def _compute_imbalance(self, trades: List[Dict[str, Any]]) -> float:
        """Compute buy/sell imbalance"""
        buy_volume = sum(t.get("size", 0) for t in trades if t.get("side") == "buy")
        sell_volume = sum(t.get("size", 0) for t in trades if t.get("side") == "sell")
        total_volume = buy_volume + sell_volume
        
        if total_volume == 0:
            return 0.0
        
        return (buy_volume - sell_volume) / total_volume
    
    def _find_support_resistance(self, trades: List[Dict[str, Any]]) -> Dict[str, List[float]]:
        """Find support and resistance levels from price clustering"""
        if not trades:
            return {"support": [], "resistance": []}
        
        # Create price histogram
        prices = [t.get("price", 0) for t in trades]
        price_volume = {}
        
        for trade in trades:
            price = round(trade.get("price", 0), 2)
            volume = trade.get("size", 0)
            price_volume[price] = price_volume.get(price, 0) + volume
        
        # Find high-volume price levels
        sorted_levels = sorted(price_volume.items(), key=lambda x: x[1], reverse=True)
        top_levels = [price for price, _ in sorted_levels[:5]]
        
        # Current price
        current_price = trades[-1].get("price", 0) if trades else 0
        
        support = [p for p in top_levels if p < current_price]
        resistance = [p for p in top_levels if p > current_price]
        
        return {
            "support": sorted(support, reverse=True)[:3],
            "resistance": sorted(resistance)[:3]
        }
    
    def _compute_liquidity_score(self, trades: List[Dict[str, Any]], 
                                 orderbook: Dict[str, Any] = None) -> float:
        """
        Compute liquidity score
        Based on trade frequency, size distribution, and spread
        """
        if not trades:
            return 0.0
        
        # Trade frequency
        time_range = trades[-1].get("timestamp", 0) - trades[0].get("timestamp", 1)
        trade_freq = len(trades) / max(time_range, 1)
        
        # Volume consistency (lower std = higher score)
        volumes = [t.get("size", 0) for t in trades]
        avg_volume = sum(volumes) / len(volumes) if volumes else 0
        
        # Spread impact (if orderbook available)
        spread_score = 1.0
        if orderbook:
            spread = orderbook.get("spread", 0)
            mid = orderbook.get("mid", 1)
            spread_pct = spread / mid if mid > 0 else 1.0
            spread_score = max(0, 1 - spread_pct * 100)  # Lower spread = higher score
        
        # Combine factors
        liquidity_score = (trade_freq * 0.4 + (avg_volume / 1000) * 0.3 + spread_score * 0.3)
        
        return min(1.0, liquidity_score)
    
    def run(self, trades: List[Dict[str, Any]], orderbook: Dict[str, Any] = None) -> EngineOutput:
        """
        Main entry point: compute volume features from trade tape
        
        Args:
            trades: List of trade dicts
            orderbook: Optional orderbook snapshot
        
        Returns:
            EngineOutput with volume features
        """
        start_time = datetime.now()
        
        # Take most recent window
        recent_trades = trades[-self.window_bars:] if len(trades) > self.window_bars else trades
        
        # Compute features
        flow_volume = sum(t.get("size", 0) for t in recent_trades)
        vwap = self._compute_vwap(recent_trades)
        trade_imbalance = self._compute_imbalance(recent_trades)
        liquidity_score = self._compute_liquidity_score(recent_trades, orderbook)
        sr_levels = self._find_support_resistance(recent_trades)
        
        features = {
            "flow_volume": float(flow_volume),
            "vwap": float(vwap),
            "trade_imbalance": float(trade_imbalance),
            "liquidity_score": float(liquidity_score),
            "num_support_levels": len(sr_levels["support"]),
            "num_resistance_levels": len(sr_levels["resistance"]),
        }
        
        # Add support/resistance levels as features
        for i, level in enumerate(sr_levels["support"][:3]):
            features[f"support_level_{i+1}"] = level
        for i, level in enumerate(sr_levels["resistance"][:3]):
            features[f"resistance_level_{i+1}"] = level
        
        latency_ms = (datetime.now() - start_time).total_seconds() * 1000
        
        logger.debug(f"Volume engine computed {len(features)} features in {latency_ms:.2f}ms")
        
        return EngineOutput(
            kind="volume",
            features=features,
            metadata={
                "n_trades": len(recent_trades),
                "window_bars": self.window_bars,
                "latency_ms": latency_ms,
                "support_resistance": sr_levels
            },
            timestamp=datetime.now(),
            confidence=1.0 if len(recent_trades) > 0 else 0.0
        )
