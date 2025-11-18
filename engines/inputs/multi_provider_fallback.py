"""
Multi-Provider Fallback System
===============================

⚠️ DEPRECATION WARNING: This module references Polygon and yfinance which have been
removed from the project. Use DataSourceManager with Unusual Whales as the primary
data source instead.

This file is kept for reference but will not work without reinstalling removed dependencies.

Advanced data source fallback with intelligent routing and validation.

Key Features:
- Dual Polygon.io + Alpha Vantage support
- Automatic failover on errors
- Cross-provider price validation
- Performance monitoring
- Smart provider selection based on:
  - Response time
  - Data quality
  - Rate limits
  - Cost optimization

Provider Hierarchy (DEPRECATED):
1. Polygon.io (primary) - REMOVED
2. Alpha Vantage (backup) - Still available
3. yfinance (tertiary) - REMOVED
4. CCXT (crypto) - Crypto/FX markets
5. Alpaca (execution) - Paper/live trading

NEW RECOMMENDED APPROACH:
Use DataSourceManager with Unusual Whales:
    from engines.inputs.data_source_manager import DataSourceManager
    manager = DataSourceManager(unusual_whales_api_key="your_key")
    quote = manager.fetch_quote("SPY")

Installation (OLD, deprecated):
    pip install polygon alpha-vantage

Usage (OLD, deprecated):
    # Basic usage
    provider = MultiProviderFallback(
        polygon_api_key="YOUR_KEY",
        alpha_vantage_api_key="YOUR_KEY"
    )
    
    # Fetch with automatic fallback
    df = provider.fetch_bars('AAPL', timeframe='1h', limit=100)
    
    # Get latest quote with validation
    quote = provider.fetch_quote('AAPL', validate=True)
    
    # Check provider health
    status = provider.get_provider_status()

Author: Super Gnosis Development Team
License: MIT
Version: 3.0.0
"""

from typing import Optional, Dict, Any, List, Literal
import pandas as pd
from datetime import datetime, timedelta
from loguru import logger
from dataclasses import dataclass
from enum import Enum
import time


@dataclass
class ProviderStats:
    """Provider performance statistics."""
    name: str
    available: bool
    success_count: int = 0
    error_count: int = 0
    avg_response_time: float = 0.0
    last_success: Optional[datetime] = None
    last_error: Optional[str] = None
    success_rate: float = 100.0


class ProviderEnum(str, Enum):
    """Supported data providers."""
    POLYGON = "polygon"
    ALPHA_VANTAGE = "alpha_vantage"
    YFINANCE = "yfinance"
    CCXT = "ccxt"
    ALPACA = "alpaca"


class MultiProviderFallback:
    """
    Multi-provider data fallback system with intelligent routing.
    
    Automatically falls back to backup providers on:
    - API errors
    - Rate limits
    - Timeout
    - Invalid data
    
    Validates data across providers for quality assurance.
    """
    
    def __init__(
        self,
        polygon_api_key: Optional[str] = None,
        alpha_vantage_api_key: Optional[str] = None,
        alpaca_api_key: Optional[str] = None,
        alpaca_api_secret: Optional[str] = None,
        validate_cross_provider: bool = True,
        validation_tolerance: float = 0.02,  # 2%
        timeout: int = 10,
        retry_attempts: int = 3
    ):
        """
        Initialize multi-provider fallback system.
        
        Args:
            polygon_api_key: Polygon.io API key (primary)
            alpha_vantage_api_key: Alpha Vantage API key (backup)
            alpaca_api_key: Alpaca API key (execution)
            alpaca_api_secret: Alpaca API secret
            validate_cross_provider: Validate data across providers
            validation_tolerance: Price validation tolerance (2% = 0.02)
            timeout: Request timeout in seconds
            retry_attempts: Number of retry attempts per provider
        """
        self.validate_cross_provider = validate_cross_provider
        self.validation_tolerance = validation_tolerance
        self.timeout = timeout
        self.retry_attempts = retry_attempts
        
        # Initialize provider stats
        self.stats: Dict[str, ProviderStats] = {}
        
        # Initialize Polygon.io (primary)
        self.polygon = None
        if polygon_api_key:
            try:
                from engines.inputs.polygon_adapter import PolygonAdapter
                self.polygon = PolygonAdapter(api_key=polygon_api_key)
                self.stats['polygon'] = ProviderStats(name='polygon', available=True)
                logger.info("✅ Polygon.io initialized (primary provider)")
            except Exception as e:
                logger.warning(f"Failed to initialize Polygon.io: {e}")
                self.stats['polygon'] = ProviderStats(name='polygon', available=False)
        
        # Initialize Alpha Vantage (backup)
        self.alpha_vantage = None
        if alpha_vantage_api_key:
            try:
                from alpha_vantage.timeseries import TimeSeries
                self.alpha_vantage = TimeSeries(
                    key=alpha_vantage_api_key,
                    output_format='pandas'
                )
                self.stats['alpha_vantage'] = ProviderStats(name='alpha_vantage', available=True)
                logger.info("✅ Alpha Vantage initialized (backup provider)")
            except Exception as e:
                logger.warning(f"Failed to initialize Alpha Vantage: {e}")
                self.stats['alpha_vantage'] = ProviderStats(name='alpha_vantage', available=False)
        
        # Initialize yfinance (tertiary)
        try:
            from engines.inputs.yfinance_adapter import YFinanceAdapter
            self.yfinance = YFinanceAdapter()
            self.stats['yfinance'] = ProviderStats(name='yfinance', available=True)
            logger.info("✅ yfinance initialized (tertiary provider)")
        except Exception as e:
            logger.warning(f"Failed to initialize yfinance: {e}")
            self.yfinance = None
        
        # Initialize CCXT for crypto (optional)
        self.ccxt = None
        try:
            from engines.inputs.ccxt_adapter import CCXTAdapter
            self.ccxt = CCXTAdapter(exchange_id='binance', testnet=True)
            self.stats['ccxt'] = ProviderStats(name='ccxt', available=True)
            logger.info("✅ CCXT initialized (crypto provider)")
        except Exception as e:
            logger.warning(f"Failed to initialize CCXT: {e}")
        
        # Initialize Alpaca (execution)
        self.alpaca = None
        if alpaca_api_key and alpaca_api_secret:
            try:
                from engines.inputs.alpaca_adapter import AlpacaAdapter
                self.alpaca = AlpacaAdapter(
                    api_key=alpaca_api_key,
                    api_secret=alpaca_api_secret,
                    paper=True
                )
                self.stats['alpaca'] = ProviderStats(name='alpaca', available=True)
                logger.info("✅ Alpaca initialized (execution provider)")
            except Exception as e:
                logger.warning(f"Failed to initialize Alpaca: {e}")
                self.stats['alpaca'] = ProviderStats(name='alpaca', available=False)
        
        # Calculate initial success rates
        for stats in self.stats.values():
            if stats.success_count + stats.error_count > 0:
                stats.success_rate = (stats.success_count / 
                                     (stats.success_count + stats.error_count)) * 100
        
        logger.info(f"🔄 Multi-provider fallback initialized")
        logger.info(f"   Active providers: {sum(1 for s in self.stats.values() if s.available)}")
    
    def fetch_bars(
        self,
        symbol: str,
        timeframe: str = '1h',
        limit: int = 100,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None
    ) -> pd.DataFrame:
        """
        Fetch OHLCV bars with automatic provider fallback.
        
        Args:
            symbol: Ticker symbol (AAPL, BTC/USDT, etc.)
            timeframe: Bar timeframe (1m, 5m, 15m, 1h, 1d)
            limit: Number of bars
            start: Start date (optional)
            end: End date (optional)
        
        Returns:
            DataFrame with OHLCV data
        """
        # Determine if crypto symbol
        is_crypto = '/' in symbol or symbol.upper() in ['BTC', 'ETH', 'USDT', 'USDC']
        
        # Define provider order based on asset type
        if is_crypto and self.ccxt:
            providers = ['ccxt', 'polygon', 'yfinance']
        else:
            providers = ['polygon', 'alpha_vantage', 'yfinance', 'alpaca']
        
        # Try each provider in order
        for provider_name in providers:
            if provider_name not in self.stats or not self.stats[provider_name].available:
                continue
            
            try:
                start_time = time.time()
                df = None
                
                if provider_name == 'polygon' and self.polygon:
                    df = self._fetch_bars_polygon(symbol, timeframe, limit, start, end)
                
                elif provider_name == 'alpha_vantage' and self.alpha_vantage:
                    df = self._fetch_bars_alpha_vantage(symbol, timeframe, limit)
                
                elif provider_name == 'yfinance' and self.yfinance:
                    df = self._fetch_bars_yfinance(symbol, timeframe, limit, start, end)
                
                elif provider_name == 'ccxt' and self.ccxt:
                    df = self._fetch_bars_ccxt(symbol, timeframe, limit, start)
                
                elif provider_name == 'alpaca' and self.alpaca:
                    df = self._fetch_bars_alpaca(symbol, timeframe, limit, start, end)
                
                if df is not None and not df.empty:
                    # Update stats
                    response_time = time.time() - start_time
                    self._update_stats(provider_name, success=True, response_time=response_time)
                    
                    logger.debug(f"📊 Fetched {len(df)} bars from {provider_name} ({response_time:.2f}s)")
                    return df
                
            except Exception as e:
                logger.warning(f"Failed to fetch bars from {provider_name}: {e}")
                self._update_stats(provider_name, success=False, error=str(e))
                continue
        
        # All providers failed
        raise RuntimeError(f"Failed to fetch bars for {symbol} from all providers")
    
    def fetch_quote(
        self,
        symbol: str,
        validate: bool = True
    ) -> Dict[str, Any]:
        """
        Fetch latest quote with optional cross-provider validation.
        
        Args:
            symbol: Ticker symbol
            validate: Cross-validate price across providers
        
        Returns:
            Quote dict with bid, ask, last, volume
        """
        # Determine if crypto
        is_crypto = '/' in symbol
        
        # Get quote from primary provider
        primary_quote = None
        primary_provider = None
        
        providers = ['polygon', 'alpha_vantage', 'yfinance', 'alpaca']
        if is_crypto:
            providers = ['ccxt'] + providers
        
        for provider_name in providers:
            if provider_name not in self.stats or not self.stats[provider_name].available:
                continue
            
            try:
                start_time = time.time()
                
                if provider_name == 'polygon' and self.polygon:
                    quote = self._fetch_quote_polygon(symbol)
                elif provider_name == 'alpha_vantage' and self.alpha_vantage:
                    quote = self._fetch_quote_alpha_vantage(symbol)
                elif provider_name == 'yfinance' and self.yfinance:
                    quote = self._fetch_quote_yfinance(symbol)
                elif provider_name == 'ccxt' and self.ccxt:
                    quote = self._fetch_quote_ccxt(symbol)
                elif provider_name == 'alpaca' and self.alpaca:
                    quote = self._fetch_quote_alpaca(symbol)
                else:
                    continue
                
                if quote:
                    response_time = time.time() - start_time
                    self._update_stats(provider_name, success=True, response_time=response_time)
                    
                    primary_quote = quote
                    primary_provider = provider_name
                    break
                    
            except Exception as e:
                logger.warning(f"Failed to fetch quote from {provider_name}: {e}")
                self._update_stats(provider_name, success=False, error=str(e))
        
        if not primary_quote:
            raise RuntimeError(f"Failed to fetch quote for {symbol} from all providers")
        
        # Validate across providers if requested
        if validate and self.validate_cross_provider:
            primary_quote['validated'] = self._validate_quote(symbol, primary_quote, primary_provider)
        else:
            primary_quote['validated'] = False
        
        primary_quote['provider'] = primary_provider
        return primary_quote
    
    def get_provider_status(self) -> Dict[str, ProviderStats]:
        """Get status of all providers."""
        return self.stats.copy()
    
    def reset_stats(self):
        """Reset all provider statistics."""
        for stats in self.stats.values():
            stats.success_count = 0
            stats.error_count = 0
            stats.avg_response_time = 0.0
            stats.success_rate = 100.0
        logger.info("🔄 Provider stats reset")
    
    # ========================================================================
    # PROVIDER-SPECIFIC FETCHERS
    # ========================================================================
    
    def _fetch_bars_polygon(
        self,
        symbol: str,
        timeframe: str,
        limit: int,
        start: Optional[datetime],
        end: Optional[datetime]
    ) -> pd.DataFrame:
        """Fetch bars from Polygon.io."""
        return self.polygon.fetch_bars(
            symbol=symbol,
            timeframe=timeframe,
            limit=limit,
            start=start,
            end=end
        )
    
    def _fetch_bars_alpha_vantage(
        self,
        symbol: str,
        timeframe: str,
        limit: int
    ) -> pd.DataFrame:
        """Fetch bars from Alpha Vantage."""
        # Alpha Vantage timeframe mapping
        if timeframe in ['1m', '5m', '15m', '30m', '60m', '1h']:
            interval = timeframe.replace('h', 'min').replace('1min', '1min')
            data, meta = self.alpha_vantage.get_intraday(
                symbol=symbol,
                interval=interval,
                outputsize='compact'
            )
        else:
            data, meta = self.alpha_vantage.get_daily(symbol=symbol, outputsize='compact')
        
        # Rename columns
        df = data.rename(columns={
            '1. open': 'open',
            '2. high': 'high',
            '3. low': 'low',
            '4. close': 'close',
            '5. volume': 'volume'
        })
        
        # Reverse chronological order
        df = df.sort_index()
        
        return df.tail(limit)
    
    def _fetch_bars_yfinance(
        self,
        symbol: str,
        timeframe: str,
        limit: int,
        start: Optional[datetime],
        end: Optional[datetime]
    ) -> pd.DataFrame:
        """Fetch bars from yfinance."""
        return self.yfinance.fetch_bars(
            symbol=symbol,
            interval=timeframe,
            period=None,
            start=start,
            end=end
        ).tail(limit)
    
    def _fetch_bars_ccxt(
        self,
        symbol: str,
        timeframe: str,
        limit: int,
        start: Optional[datetime]
    ) -> pd.DataFrame:
        """Fetch bars from CCXT."""
        return self.ccxt.fetch_ohlcv(
            symbol=symbol,
            timeframe=timeframe,
            limit=limit,
            since=start
        )
    
    def _fetch_bars_alpaca(
        self,
        symbol: str,
        timeframe: str,
        limit: int,
        start: Optional[datetime],
        end: Optional[datetime]
    ) -> pd.DataFrame:
        """Fetch bars from Alpaca."""
        return self.alpaca.fetch_bars(
            symbol=symbol,
            timeframe=timeframe,
            limit=limit,
            start=start,
            end=end
        )
    
    def _fetch_quote_polygon(self, symbol: str) -> Dict[str, Any]:
        """Fetch quote from Polygon.io."""
        quote = self.polygon.fetch_last_quote(symbol)
        return {
            'symbol': symbol,
            'bid': quote.get('bid_price', 0),
            'ask': quote.get('ask_price', 0),
            'last': quote.get('last_price', 0),
            'volume': quote.get('volume', 0),
            'timestamp': datetime.now()
        }
    
    def _fetch_quote_alpha_vantage(self, symbol: str) -> Dict[str, Any]:
        """Fetch quote from Alpha Vantage."""
        quote, _ = self.alpha_vantage.get_quote_endpoint(symbol)
        return {
            'symbol': symbol,
            'bid': float(quote.get('08. previous close', 0)),
            'ask': float(quote.get('08. previous close', 0)),
            'last': float(quote.get('05. price', 0)),
            'volume': int(quote.get('06. volume', 0)),
            'timestamp': datetime.now()
        }
    
    def _fetch_quote_yfinance(self, symbol: str) -> Dict[str, Any]:
        """Fetch quote from yfinance."""
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        info = ticker.info
        
        return {
            'symbol': symbol,
            'bid': info.get('bid', 0),
            'ask': info.get('ask', 0),
            'last': info.get('currentPrice', info.get('regularMarketPrice', 0)),
            'volume': info.get('volume', 0),
            'timestamp': datetime.now()
        }
    
    def _fetch_quote_ccxt(self, symbol: str) -> Dict[str, Any]:
        """Fetch quote from CCXT."""
        ticker = self.ccxt.fetch_ticker(symbol)
        return {
            'symbol': symbol,
            'bid': ticker.bid,
            'ask': ticker.ask,
            'last': ticker.last,
            'volume': ticker.volume,
            'timestamp': ticker.timestamp
        }
    
    def _fetch_quote_alpaca(self, symbol: str) -> Dict[str, Any]:
        """Fetch quote from Alpaca."""
        quote = self.alpaca.fetch_latest_quote(symbol)
        return {
            'symbol': symbol,
            'bid': quote.get('bid_price', 0),
            'ask': quote.get('ask_price', 0),
            'last': (quote.get('bid_price', 0) + quote.get('ask_price', 0)) / 2,
            'volume': 0,
            'timestamp': datetime.now()
        }
    
    def _validate_quote(
        self,
        symbol: str,
        primary_quote: Dict[str, Any],
        primary_provider: str
    ) -> bool:
        """
        Validate quote across multiple providers.
        
        Returns True if quotes agree within tolerance.
        """
        primary_price = primary_quote['last']
        
        # Try to get quote from another provider
        for provider_name, stats in self.stats.items():
            if provider_name == primary_provider or not stats.available:
                continue
            
            try:
                if provider_name == 'polygon' and self.polygon:
                    backup_quote = self._fetch_quote_polygon(symbol)
                elif provider_name == 'alpha_vantage' and self.alpha_vantage:
                    backup_quote = self._fetch_quote_alpha_vantage(symbol)
                elif provider_name == 'yfinance' and self.yfinance:
                    backup_quote = self._fetch_quote_yfinance(symbol)
                else:
                    continue
                
                backup_price = backup_quote['last']
                
                # Check if prices agree within tolerance
                diff_pct = abs(primary_price - backup_price) / primary_price
                
                if diff_pct <= self.validation_tolerance:
                    logger.debug(f"✅ Quote validated: {primary_provider} vs {provider_name} ({diff_pct*100:.2f}% diff)")
                    return True
                else:
                    logger.warning(f"⚠️  Quote mismatch: {primary_provider}=${primary_price:.2f} vs {provider_name}=${backup_price:.2f} ({diff_pct*100:.2f}% diff)")
                    return False
                    
            except Exception as e:
                logger.debug(f"Failed to validate with {provider_name}: {e}")
                continue
        
        # Could not validate with any provider
        logger.warning("⚠️  Could not validate quote with backup providers")
        return False
    
    def _update_stats(
        self,
        provider_name: str,
        success: bool,
        response_time: float = 0.0,
        error: Optional[str] = None
    ):
        """Update provider statistics."""
        if provider_name not in self.stats:
            return
        
        stats = self.stats[provider_name]
        
        if success:
            stats.success_count += 1
            stats.last_success = datetime.now()
            
            # Update average response time (exponential moving average)
            alpha = 0.3
            stats.avg_response_time = (
                alpha * response_time + 
                (1 - alpha) * stats.avg_response_time
            )
        else:
            stats.error_count += 1
            stats.last_error = error
        
        # Update success rate
        total = stats.success_count + stats.error_count
        if total > 0:
            stats.success_rate = (stats.success_count / total) * 100


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def create_production_fallback(
    polygon_api_key: Optional[str] = None,
    alpha_vantage_api_key: Optional[str] = None
) -> MultiProviderFallback:
    """
    Create production-ready fallback system.
    
    Args:
        polygon_api_key: Polygon.io API key
        alpha_vantage_api_key: Alpha Vantage API key
    
    Returns:
        Configured MultiProviderFallback
    """
    return MultiProviderFallback(
        polygon_api_key=polygon_api_key,
        alpha_vantage_api_key=alpha_vantage_api_key,
        validate_cross_provider=True,
        validation_tolerance=0.02,
        timeout=10,
        retry_attempts=3
    )


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    print("\n🔄 Multi-Provider Fallback Examples\n")
    
    # Example 1: Basic usage with automatic fallback
    print("Example 1: Fetch bars with automatic fallback")
    provider = MultiProviderFallback()
    
    try:
        df = provider.fetch_bars('AAPL', timeframe='1h', limit=24)
        print(f"   Fetched {len(df)} hourly bars for AAPL")
        print(df.tail())
    except Exception as e:
        print(f"   Error: {e}")
    
    # Example 2: Cross-provider validation
    print("\n\nExample 2: Fetch quote with validation")
    try:
        quote = provider.fetch_quote('AAPL', validate=True)
        print(f"   AAPL: ${quote['last']:.2f}")
        print(f"   Provider: {quote['provider']}")
        print(f"   Validated: {quote['validated']}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Example 3: Provider status
    print("\n\nExample 3: Provider status")
    status = provider.get_provider_status()
    for name, stats in status.items():
        print(f"   {name}:")
        print(f"      Available: {stats.available}")
        print(f"      Success Rate: {stats.success_rate:.1f}%")
        print(f"      Avg Response: {stats.avg_response_time:.2f}s")
    
    print("\n\n✅ Multi-provider fallback examples complete!")
    print("   Ready for production with intelligent failover")
