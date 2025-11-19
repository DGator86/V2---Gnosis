"""
Multi-Timeframe Scanner with Unusual Whales Integration

Scans 25+ stocks across 7 timeframes with 100-bar lookback.
Integrates Unusual Whales for options flow and market sentiment.
"""

import asyncio
import yaml
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import pandas as pd
import os
from dotenv import load_dotenv
from loguru import logger
from dataclasses import dataclass, field
from collections import defaultdict

# Load environment
load_dotenv()

# Import adapters
try:
    from engines.inputs.unusual_whales_adapter import UnusualWhalesAdapter
    UW_AVAILABLE = True
except ImportError:
    UW_AVAILABLE = False
    logger.warning("Unusual Whales adapter not available")

try:
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
    ALPACA_AVAILABLE = True
except ImportError:
    ALPACA_AVAILABLE = False
    logger.warning("Alpaca not available")

# Import engines - use what's available
try:
    from gnosis.regime import RegimeDetector
except ImportError:
    RegimeDetector = None
    logger.warning("RegimeDetector not available")


@dataclass
class ScanResult:
    """Result from scanning a symbol on a specific timeframe"""
    symbol: str
    timeframe: str
    timestamp: datetime
    price: float
    volume: float
    regime: str
    regime_confidence: float
    signals: Dict[str, float] = field(default_factory=dict)
    unusual_activity: Dict = field(default_factory=dict)
    alert_triggered: bool = False
    alert_reasons: List[str] = field(default_factory=list)


class MultiTimeframeScanner:
    """
    Scans multiple symbols across multiple timeframes.
    Primary data from Unusual Whales, market data from Alpaca.
    """
    
    # Map config intervals to Alpaca TimeFrame
    TIMEFRAME_MAP = {
        "1Min": TimeFrame(1, TimeFrameUnit.Minute),
        "5Min": TimeFrame(5, TimeFrameUnit.Minute),
        "15Min": TimeFrame(15, TimeFrameUnit.Minute),
        "30Min": TimeFrame(30, TimeFrameUnit.Minute),
        "1Hour": TimeFrame(1, TimeFrameUnit.Hour),
        "4Hour": TimeFrame(4, TimeFrameUnit.Hour),
        "1Day": TimeFrame(1, TimeFrameUnit.Day)
    }
    
    def __init__(self, config_path: str = None):
        """Initialize scanner with configuration"""
        
        # Load config
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config" / "watchlist.yaml"
        
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        # Initialize data clients
        self._init_data_clients()
        
        # Initialize components
        self.regime_detector = RegimeDetector()
        
        # Build symbol list
        self.symbols = self._build_symbol_list()
        
        # Cache for recent data
        self.data_cache = defaultdict(dict)
        
        # Track alerts
        self.recent_alerts = []
        
        logger.info(f"📊 Multi-Timeframe Scanner initialized")
        logger.info(f"   Symbols: {len(self.symbols)}")
        logger.info(f"   Timeframes: {len(self.config['timeframes'])}")
        logger.info(f"   Primary source: {self.config['data_sources']['primary']}")
    
    def _init_data_clients(self):
        """Initialize data source clients"""
        
        # Unusual Whales (primary)
        if UW_AVAILABLE:
            uw_key = os.getenv("UNUSUAL_WHALES_API_KEY")
            if uw_key and uw_key != "your_unusual_whales_key_here":
                self.uw_client = UnusualWhalesAdapter(api_key=uw_key)
            else:
                logger.warning("Using test key for Unusual Whales (limited rate)")
                self.uw_client = UnusualWhalesAdapter(use_test_key=True)
        else:
            self.uw_client = None
            logger.warning("Unusual Whales not available")
        
        # Alpaca (market data)
        if ALPACA_AVAILABLE:
            api_key = os.getenv("ALPACA_API_KEY")
            secret_key = os.getenv("ALPACA_SECRET_KEY")
            self.alpaca_client = StockHistoricalDataClient(api_key, secret_key)
        else:
            self.alpaca_client = None
            logger.error("Alpaca not available - cannot fetch market data")
    
    def _build_symbol_list(self) -> List[str]:
        """Build list of symbols from config"""
        symbols = []
        
        watchlist = self.config['watchlist']
        for category in ['indices', 'mega_tech', 'financials', 'high_volume', 'strategic']:
            if category in watchlist:
                for item in watchlist[category]:
                    symbols.append(item['symbol'])
        
        return symbols
    
    async def scan_symbol_timeframe(
        self, 
        symbol: str, 
        timeframe: str,
        bars: int = 100
    ) -> Optional[ScanResult]:
        """
        Scan a single symbol on a specific timeframe.
        
        Args:
            symbol: Stock symbol to scan
            timeframe: Timeframe string (e.g., "5Min")
            bars: Number of bars to fetch (default 100)
        
        Returns:
            ScanResult or None if error
        """
        try:
            # Fetch market data from Alpaca
            market_data = await self._fetch_market_data(symbol, timeframe, bars)
            if market_data is None or market_data.empty:
                return None
            
            # Fetch Unusual Whales data
            uw_data = await self._fetch_unusual_whales_data(symbol)
            
            # Compute technical features
            features = self._compute_features(market_data)
            
            # Detect regime
            regime_state = self._detect_regime(market_data, features)
            
            # Evaluate signals
            signals = self._evaluate_signals(market_data, features, regime_state)
            
            # Check for alerts
            alert_triggered, alert_reasons = self._check_alerts(
                symbol, timeframe, market_data, uw_data, signals
            )
            
            # Create result
            latest = market_data.iloc[-1]
            result = ScanResult(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=datetime.now(),
                price=latest['close'],
                volume=latest['volume'],
                regime=regime_state.primary_regime,
                regime_confidence=regime_state.confidence,
                signals=signals,
                unusual_activity=uw_data,
                alert_triggered=alert_triggered,
                alert_reasons=alert_reasons
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error scanning {symbol}/{timeframe}: {e}")
            return None
    
    async def _fetch_market_data(
        self, 
        symbol: str, 
        timeframe: str, 
        bars: int
    ) -> Optional[pd.DataFrame]:
        """Fetch market data from Alpaca"""
        
        if not self.alpaca_client:
            return None
        
        try:
            # Get Alpaca timeframe
            tf = self.TIMEFRAME_MAP.get(timeframe)
            if not tf:
                logger.error(f"Unknown timeframe: {timeframe}")
                return None
            
            # Calculate start time based on timeframe
            end = datetime.now()
            
            # Estimate start time (with buffer)
            if timeframe == "1Min":
                start = end - timedelta(minutes=bars * 2)
            elif timeframe == "5Min":
                start = end - timedelta(minutes=bars * 5 * 2)
            elif timeframe == "15Min":
                start = end - timedelta(minutes=bars * 15 * 2)
            elif timeframe == "30Min":
                start = end - timedelta(minutes=bars * 30 * 2)
            elif timeframe == "1Hour":
                start = end - timedelta(hours=bars * 2)
            elif timeframe == "4Hour":
                start = end - timedelta(hours=bars * 4 * 2)
            else:  # 1Day
                start = end - timedelta(days=bars * 2)
            
            # Create request
            request = StockBarsRequest(
                symbol_or_symbols=symbol,
                timeframe=tf,
                start=start,
                end=end,
                limit=bars
            )
            
            # Fetch bars
            bars_response = self.alpaca_client.get_stock_bars(request)
            
            # Convert to dataframe
            if symbol in bars_response:
                df = bars_response[symbol].df
                df = df.tail(bars)  # Ensure we have exactly the requested bars
                return df
            
            return None
            
        except Exception as e:
            logger.error(f"Error fetching Alpaca data for {symbol}/{timeframe}: {e}")
            return None
    
    async def _fetch_unusual_whales_data(self, symbol: str) -> Dict:
        """Fetch Unusual Whales data for symbol"""
        
        if not self.uw_client:
            return {}
        
        try:
            data = {}
            
            # Get recent options flow
            flow = self.uw_client.get_ticker_flow(symbol, limit=20)
            if flow and 'data' in flow:
                data['options_flow'] = flow['data']
            
            # Get market sentiment
            tide = self.uw_client.get_market_tide()
            if tide and 'data' in tide:
                data['market_tide'] = tide['data']
            
            # Get ticker overview (includes Greeks if available)
            overview = self.uw_client.get_ticker_overview(symbol)
            if overview and 'data' in overview:
                data['overview'] = overview['data']
            
            return data
            
        except Exception as e:
            logger.warning(f"Error fetching UW data for {symbol}: {e}")
            return {}
    
    def _compute_features(self, market_data: pd.DataFrame) -> Dict:
        """Compute technical features from market data"""
        
        features = {}
        
        # Price features
        features['returns'] = market_data['close'].pct_change()
        features['log_returns'] = pd.np.log(market_data['close'] / market_data['close'].shift(1))
        
        # Volume features
        features['volume_ma'] = market_data['volume'].rolling(20).mean()
        features['volume_ratio'] = market_data['volume'] / features['volume_ma']
        
        # Volatility
        features['volatility'] = features['returns'].rolling(20).std()
        
        # Simple moving averages
        features['sma_20'] = market_data['close'].rolling(20).mean()
        features['sma_50'] = market_data['close'].rolling(50).mean()
        
        # Price position
        latest_price = market_data['close'].iloc[-1]
        features['price_vs_sma20'] = (latest_price - features['sma_20'].iloc[-1]) / features['sma_20'].iloc[-1]
        
        return features
    
    def _detect_regime(self, market_data: pd.DataFrame, features: Dict) -> object:
        """Detect market regime"""
        
        # Create mock regime state for now
        # In production, use the full regime detector
        from types import SimpleNamespace
        
        volatility = features['volatility'].iloc[-1] if 'volatility' in features else 0.02
        
        # Simple regime classification
        if volatility > 0.03:
            regime = "volatile"
        elif volatility < 0.01:
            regime = "calm"
        else:
            regime = "normal"
        
        # Trend detection
        if len(market_data) >= 20:
            sma_20 = market_data['close'].rolling(20).mean().iloc[-1]
            current = market_data['close'].iloc[-1]
            
            if current > sma_20 * 1.02:
                regime = "trending_up"
            elif current < sma_20 * 0.98:
                regime = "trending_down"
        
        return SimpleNamespace(
            primary_regime=regime,
            confidence=0.7,
            volatility_regime="normal",
            trend_strength=0.5
        )
    
    def _evaluate_signals(
        self, 
        market_data: pd.DataFrame, 
        features: Dict,
        regime_state
    ) -> Dict[str, float]:
        """Evaluate trading signals"""
        
        signals = {}
        
        # Momentum signal
        if 'returns' in features:
            recent_return = features['returns'].tail(5).mean()
            signals['momentum'] = 1 if recent_return > 0 else -1
        
        # Volume signal
        if 'volume_ratio' in features:
            vol_ratio = features['volume_ratio'].iloc[-1]
            signals['volume_surge'] = 1 if vol_ratio > 2.0 else 0
        
        # Trend signal
        if 'price_vs_sma20' in features:
            position = features['price_vs_sma20']
            signals['trend'] = 1 if position > 0 else -1
        
        # Regime-based signal
        if regime_state.primary_regime == "trending_up":
            signals['regime'] = 1
        elif regime_state.primary_regime == "trending_down":
            signals['regime'] = -1
        else:
            signals['regime'] = 0
        
        return signals
    
    def _check_alerts(
        self,
        symbol: str,
        timeframe: str,
        market_data: pd.DataFrame,
        uw_data: Dict,
        signals: Dict
    ) -> Tuple[bool, List[str]]:
        """Check if any alert conditions are met"""
        
        alert_triggered = False
        alert_reasons = []
        
        alerts_config = self.config['scanning']['alerts']
        
        # Check unusual options activity
        if alerts_config['unusual_options_activity']['enabled']:
            if 'options_flow' in uw_data and uw_data['options_flow']:
                for flow in uw_data['options_flow'][:5]:  # Check recent flows
                    if 'premium' in flow and flow['premium'] > alerts_config['unusual_options_activity']['min_premium']:
                        alert_triggered = True
                        alert_reasons.append(f"Unusual options: ${flow['premium']:,.0f} premium")
        
        # Check breakout
        if alerts_config['breakout_detection']['enabled']:
            if timeframe in alerts_config['breakout_detection']['timeframes']:
                if 'volume_surge' in signals and signals['volume_surge'] > 0:
                    alert_triggered = True
                    alert_reasons.append(f"Volume breakout on {timeframe}")
        
        # Check regime change
        if alerts_config['regime_change']['enabled']:
            # Would need historical regime to detect change
            pass
        
        return alert_triggered, alert_reasons
    
    async def scan_all(self, priority_only: bool = False) -> List[ScanResult]:
        """
        Scan all symbols across all timeframes.
        
        Args:
            priority_only: Only scan high-priority combinations
        
        Returns:
            List of scan results
        """
        results = []
        tasks = []
        
        # Build scan tasks
        for symbol in self.symbols:
            for tf_config in self.config['timeframes']:
                timeframe = tf_config['interval']
                bars = tf_config['bars']
                priority = tf_config['priority']
                
                # Skip low priority if requested
                if priority_only and priority == "low":
                    continue
                
                # Create scan task
                task = self.scan_symbol_timeframe(symbol, timeframe, bars)
                tasks.append(task)
                
                # Limit concurrent tasks
                if len(tasks) >= self.config['scanning']['max_concurrent']:
                    # Execute batch
                    batch_results = await asyncio.gather(*tasks)
                    results.extend([r for r in batch_results if r is not None])
                    tasks = []
        
        # Execute remaining tasks
        if tasks:
            batch_results = await asyncio.gather(*tasks)
            results.extend([r for r in batch_results if r is not None])
        
        # Filter and sort results
        results = self._process_results(results)
        
        return results
    
    def _process_results(self, results: List[ScanResult]) -> List[ScanResult]:
        """Process and prioritize scan results"""
        
        # Filter alerts
        alerts = [r for r in results if r.alert_triggered]
        
        # Store recent alerts
        self.recent_alerts = alerts[:20]  # Keep last 20 alerts
        
        # Sort by importance
        def importance_score(result):
            score = 0
            if result.alert_triggered:
                score += 100
            if result.regime in ["trending_up", "trending_down"]:
                score += 50
            if result.regime_confidence > 0.8:
                score += 30
            if 'volume_surge' in result.signals and result.signals['volume_surge'] > 0:
                score += 20
            return score
        
        results.sort(key=importance_score, reverse=True)
        
        return results
    
    def print_summary(self, results: List[ScanResult], top_n: int = 10):
        """Print summary of scan results"""
        
        print("\n" + "="*80)
        print("📊 MULTI-TIMEFRAME SCAN SUMMARY")
        print("="*80)
        
        # Alerts
        alerts = [r for r in results if r.alert_triggered]
        if alerts:
            print(f"\n🚨 ALERTS ({len(alerts)} triggered):")
            for alert in alerts[:5]:
                print(f"   {alert.symbol:6} ({alert.timeframe:5}) - {', '.join(alert.alert_reasons)}")
        
        # Top opportunities
        print(f"\n🎯 TOP {top_n} OPPORTUNITIES:")
        print(f"{'Symbol':8} {'TF':6} {'Price':10} {'Regime':15} {'Conf':6} {'Signals'}")
        print("-"*70)
        
        for r in results[:top_n]:
            signal_str = f"M:{r.signals.get('momentum', 0):+.0f} T:{r.signals.get('trend', 0):+.0f}"
            print(f"{r.symbol:8} {r.timeframe:6} ${r.price:9.2f} {r.regime:15} {r.regime_confidence:5.2f} {signal_str}")
        
        # Statistics
        print(f"\n📈 STATISTICS:")
        print(f"   Total scans: {len(results)}")
        print(f"   Alerts: {len(alerts)}")
        
        # Regime distribution
        regimes = defaultdict(int)
        for r in results:
            regimes[r.regime] += 1
        
        print(f"\n   Regime distribution:")
        for regime, count in sorted(regimes.items(), key=lambda x: x[1], reverse=True):
            print(f"      {regime:15}: {count:3} ({count/len(results)*100:.1f}%)")


async def main():
    """Test the multi-timeframe scanner"""
    
    print("🚀 Starting Multi-Timeframe Scanner Test")
    print("-"*80)
    
    # Initialize scanner
    scanner = MultiTimeframeScanner()
    
    # Quick test - scan SPY on multiple timeframes
    print("\n📊 Testing SPY across timeframes...")
    test_results = []
    
    for timeframe in ["1Min", "5Min", "15Min", "1Hour"]:
        print(f"   Scanning SPY/{timeframe}...")
        result = await scanner.scan_symbol_timeframe("SPY", timeframe, 100)
        if result:
            test_results.append(result)
            print(f"      ✅ Price: ${result.price:.2f}, Regime: {result.regime}")
        else:
            print(f"      ❌ Failed")
    
    # Full scan (priority only for speed)
    print("\n📊 Running full scan (high priority only)...")
    results = await scanner.scan_all(priority_only=True)
    
    # Print summary
    scanner.print_summary(results, top_n=15)
    
    print("\n✅ Scanner test complete!")
    
    return results


if __name__ == "__main__":
    asyncio.run(main())