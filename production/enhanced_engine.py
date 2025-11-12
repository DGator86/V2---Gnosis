"""
Production-Optimized Enhanced Sentiment Engine
Combines sentiment analysis with advanced quantitative features for live trading.
"""

import time
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict
import json

import pandas as pd
import numpy as np

from sentiment.engine import SentimentEngine
from sentiment.schemas import TickerSentimentSnapshot
from integrations.engine_integration import EnhancedSentimentMetrics


logger = logging.getLogger(__name__)


@dataclass
class TradingSignal:
    """Complete trading signal with all features."""
    
    ticker: str
    timestamp: datetime
    signal_type: str  # 'BUY', 'SELL', 'HOLD'
    confidence: float  # 0-1
    
    # Sentiment features
    sentiment_mean: float
    sentiment_std: float
    sentiment_entropy: float
    is_contrarian_market: bool
    is_contrarian_sector: bool
    
    # Technical features
    vsa_score: Optional[float] = None
    hawkes_branching: Optional[float] = None
    hurst_exponent: Optional[float] = None
    is_trending: Optional[bool] = None
    perm_entropy: Optional[float] = None
    
    # Meta features
    is_high_conviction: bool = False
    risk_level: str = "MEDIUM"  # LOW, MEDIUM, HIGH
    suggested_position_size: float = 0.0
    
    # Supporting data
    features: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return asdict(self)
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        data = self.to_dict()
        # Convert datetime to ISO format
        data['timestamp'] = data['timestamp'].isoformat()
        return json.dumps(data)


class ProductionEnhancedEngine:
    """
    Production-ready enhanced sentiment engine with:
    - Parallel feature computation
    - Intelligent caching
    - Performance monitoring
    - Error handling
    - Trading signal generation
    """
    
    def __init__(
        self,
        sentiment_config: Optional[Dict] = None,
        features_config_path: Optional[str] = None,
        enable_caching: bool = True,
        max_workers: int = 4,
        cache_ttl: int = 300,
    ):
        """
        Initialize production engine.
        
        Args:
            sentiment_config: Sentiment engine configuration
            features_config_path: Path to features.yaml
            enable_caching: Whether to enable caching
            max_workers: Max parallel workers
            cache_ttl: Cache TTL in seconds
        """
        logger.info("Initializing ProductionEnhancedEngine...")
        
        # Initialize sentiment engine
        self.sentiment_engine = SentimentEngine(**(sentiment_config or {}))
        
        # Initialize enhanced metrics calculator
        self.enhanced_metrics = EnhancedSentimentMetrics(features_config_path)
        
        # Thread pool for parallel computation
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        
        # Performance tracking
        self.perf_stats = {
            'total_signals': 0,
            'avg_computation_time': 0.0,
            'cache_hits': 0,
            'cache_misses': 0,
        }
        
        # Configuration
        self.enable_caching = enable_caching
        self.cache_ttl = cache_ttl
        
        logger.info("ProductionEnhancedEngine initialized successfully")
    
    def generate_signal(
        self,
        ticker: str,
        ohlcv: pd.DataFrame,
        window: str = "1h",
        min_confidence: float = 0.6,
    ) -> Optional[TradingSignal]:
        """
        Generate complete trading signal for a ticker.
        
        Args:
            ticker: Ticker symbol
            ohlcv: OHLCV DataFrame
            window: Time window for sentiment
            min_confidence: Minimum confidence threshold
        
        Returns:
            TradingSignal or None if below confidence threshold
        """
        start_time = time.time()
        
        try:
            # 1. Get sentiment snapshot
            sentiment_snapshot = self.sentiment_engine.snapshot(ticker, window)
            
            # 2. Get enhanced technical metrics (parallel if possible)
            tech_metrics = self.enhanced_metrics.get_all_metrics(ticker, ohlcv)
            
            # 3. Combine into trading decision
            signal = self._create_trading_signal(
                ticker, sentiment_snapshot, tech_metrics
            )
            
            # 4. Apply confidence threshold
            if signal and signal.confidence >= min_confidence:
                # Update performance stats
                elapsed = time.time() - start_time
                self._update_perf_stats(elapsed)
                
                logger.info(
                    f"Signal generated for {ticker}: {signal.signal_type} "
                    f"(confidence: {signal.confidence:.2f}) in {elapsed:.3f}s"
                )
                
                return signal
            else:
                logger.debug(
                    f"Signal for {ticker} below confidence threshold: "
                    f"{signal.confidence if signal else 0:.2f} < {min_confidence}"
                )
                return None
        
        except Exception as e:
            logger.error(f"Error generating signal for {ticker}: {e}", exc_info=True)
            return None
    
    def generate_signals_batch(
        self,
        tickers: List[str],
        ohlcv_data: Dict[str, pd.DataFrame],
        window: str = "1h",
        min_confidence: float = 0.6,
    ) -> Dict[str, Optional[TradingSignal]]:
        """
        Generate signals for multiple tickers in parallel.
        
        Args:
            tickers: List of ticker symbols
            ohlcv_data: Dict of {ticker: ohlcv_dataframe}
            window: Time window
            min_confidence: Minimum confidence
        
        Returns:
            Dict of {ticker: signal}
        """
        logger.info(f"Generating signals for {len(tickers)} tickers...")
        
        # Submit all tasks to thread pool
        futures = {
            self.executor.submit(
                self.generate_signal,
                ticker,
                ohlcv_data.get(ticker),
                window,
                min_confidence,
            ): ticker
            for ticker in tickers if ticker in ohlcv_data
        }
        
        # Collect results
        signals = {}
        for future in as_completed(futures):
            ticker = futures[future]
            try:
                signal = future.result()
                signals[ticker] = signal
            except Exception as e:
                logger.error(f"Error processing {ticker}: {e}")
                signals[ticker] = None
        
        successful = sum(1 for s in signals.values() if s is not None)
        logger.info(
            f"Batch complete: {successful}/{len(tickers)} signals generated"
        )
        
        return signals
    
    def _create_trading_signal(
        self,
        ticker: str,
        sentiment: TickerSentimentSnapshot,
        tech_metrics: Dict[str, Any],
    ) -> TradingSignal:
        """
        Create trading signal from sentiment and technical metrics.
        
        Strategy logic:
        - Strong BUY: Contrarian + no supply + trending + high sentiment
        - BUY: Positive sentiment + trending or low volatility clustering
        - SELL: Negative sentiment + mean reverting + high clustering
        - HOLD: Everything else
        """
        # Extract key metrics
        vsa_score = tech_metrics.get('vsa_vsa_score')
        vsa_no_supply = tech_metrics.get('vsa_is_no_supply', False)
        vsa_climax = tech_metrics.get('vsa_is_climax', False)
        
        hawkes_branching = tech_metrics.get('hawkes_hawkes_branching_ratio')
        hawkes_clustering = tech_metrics.get('hawkes_hawkes_is_clustering', False)
        
        hurst = tech_metrics.get('regime_hurst_exponent')
        is_trending = tech_metrics.get('regime_is_trending', False)
        is_mean_reverting = tech_metrics.get('regime_is_mean_reverting', False)
        
        perm_entropy = tech_metrics.get('complexity_perm_entropy')
        is_complex = tech_metrics.get('complexity_is_complex', False)
        
        # Initialize signal
        signal_type = "HOLD"
        confidence = 0.5
        risk_level = "MEDIUM"
        
        # Decision logic
        if (sentiment.is_strong_contrarian and 
            vsa_no_supply and 
            is_trending and 
            sentiment.mean > 0.3):
            # Strong contrarian + VSA no supply + trending = Strong BUY
            signal_type = "BUY"
            confidence = 0.9
            risk_level = "LOW"
        
        elif (sentiment.mean > 0.5 and 
              is_trending and 
              not hawkes_clustering):
            # Positive sentiment + trending + low volatility = BUY
            signal_type = "BUY"
            confidence = 0.75
            risk_level = "MEDIUM"
        
        elif (sentiment.is_contrarian_market and 
              vsa_no_supply and 
              sentiment.sharpe_like > 1.5):
            # Contrarian + technical support = BUY
            signal_type = "BUY"
            confidence = 0.8
            risk_level = "MEDIUM"
        
        elif (sentiment.mean < -0.5 and 
              is_mean_reverting and 
              hawkes_clustering):
            # Negative sentiment + mean reversion + high vol = SELL
            signal_type = "SELL"
            confidence = 0.75
            risk_level = "HIGH"
        
        elif vsa_climax and sentiment.mean < -0.3:
            # Climax selling = potential bottom, but risky
            signal_type = "BUY"
            confidence = 0.65
            risk_level = "HIGH"
        
        else:
            # Default: HOLD
            signal_type = "HOLD"
            confidence = 0.5
            risk_level = "MEDIUM"
        
        # Adjust confidence based on additional factors
        if sentiment.entropy < 0.3:  # Low entropy = high agreement
            confidence += 0.05
        
        if sentiment.novelty > 0.8:  # High novelty = new information
            confidence += 0.05
        
        if is_complex:  # High complexity = unpredictable
            confidence -= 0.1
            risk_level = "HIGH"
        
        # Cap confidence
        confidence = np.clip(confidence, 0.0, 1.0)
        
        # Suggested position size (Kelly criterion approximation)
        if signal_type == "BUY":
            suggested_size = confidence * 0.25  # Max 25% position
        elif signal_type == "SELL":
            suggested_size = -confidence * 0.25
        else:
            suggested_size = 0.0
        
        return TradingSignal(
            ticker=ticker,
            timestamp=datetime.now(timezone.utc),
            signal_type=signal_type,
            confidence=confidence,
            sentiment_mean=sentiment.mean,
            sentiment_std=sentiment.std,
            sentiment_entropy=sentiment.entropy,
            is_contrarian_market=sentiment.is_contrarian_market or False,
            is_contrarian_sector=sentiment.is_contrarian_sector or False,
            vsa_score=vsa_score,
            hawkes_branching=hawkes_branching,
            hurst_exponent=hurst,
            is_trending=is_trending,
            perm_entropy=perm_entropy,
            is_high_conviction=(confidence > 0.8),
            risk_level=risk_level,
            suggested_position_size=suggested_size,
            features=tech_metrics,
        )
    
    def _update_perf_stats(self, elapsed_time: float):
        """Update performance statistics."""
        self.perf_stats['total_signals'] += 1
        n = self.perf_stats['total_signals']
        
        # Running average of computation time
        old_avg = self.perf_stats['avg_computation_time']
        self.perf_stats['avg_computation_time'] = (
            (old_avg * (n - 1) + elapsed_time) / n
        )
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics."""
        return {
            **self.perf_stats,
            'cache_hit_rate': (
                self.perf_stats['cache_hits'] / 
                max(self.perf_stats['cache_hits'] + self.perf_stats['cache_misses'], 1)
            ),
        }
    
    def clear_cache(self):
        """Clear all caches."""
        self.enhanced_metrics.clear_cache()
        logger.info("All caches cleared")
    
    def shutdown(self):
        """Shutdown executor and cleanup."""
        logger.info("Shutting down ProductionEnhancedEngine...")
        self.executor.shutdown(wait=True)
        logger.info("Shutdown complete")


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Initialize engine
    engine = ProductionEnhancedEngine(max_workers=4)
    
    # Generate sample data
    np.random.seed(42)
    n = 300
    dates = pd.date_range('2024-01-01', periods=n, freq='1h')
    
    price = 100 + np.cumsum(np.random.randn(n) * 0.5)
    ohlcv = pd.DataFrame({
        'open': price,
        'high': price * 1.01,
        'low': price * 0.99,
        'close': price,
        'volume': np.abs(np.random.randn(n) * 1000000 + 5000000),
    }, index=dates)
    
    # Generate signal
    signal = engine.generate_signal('AAPL', ohlcv, window='1h')
    
    if signal:
        print("\n" + "="*60)
        print("TRADING SIGNAL GENERATED")
        print("="*60)
        print(f"Ticker: {signal.ticker}")
        print(f"Signal: {signal.signal_type}")
        print(f"Confidence: {signal.confidence:.2%}")
        print(f"Risk Level: {signal.risk_level}")
        print(f"Position Size: {signal.suggested_position_size:.2%}")
        print(f"\nSentiment: {signal.sentiment_mean:.3f} ± {signal.sentiment_std:.3f}")
        print(f"VSA Score: {signal.vsa_score:.3f}" if signal.vsa_score else "VSA: N/A")
        print(f"Hurst: {signal.hurst_exponent:.3f}" if signal.hurst_exponent else "Hurst: N/A")
        print(f"Trending: {signal.is_trending}")
        print("="*60)
    
    # Performance stats
    stats = engine.get_performance_stats()
    print(f"\nPerformance Stats:")
    print(f"  Avg computation time: {stats['avg_computation_time']:.3f}s")
    print(f"  Total signals: {stats['total_signals']}")
    
    engine.shutdown()
