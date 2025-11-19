"""
Unusual Whales Primary Market Data Adapter
==========================================

This adapter makes Unusual Whales the PRIMARY data source for all market data,
options flow, and sentiment analysis in the Super Gnosis framework.

Features:
- Real-time market quotes
- Options flow with sentiment analysis
- Options chains with Greeks
- Congressional and insider trades
- Market sentiment and tide
- Historical data

All other data sources (Alpaca, Public.com, etc.) become SECONDARY fallbacks.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any, Protocol
import os
from loguru import logger
import pandas as pd
import polars as pl
from dataclasses import dataclass

from .unusual_whales_adapter import UnusualWhalesAdapter
from .market_data_adapter import MarketDataAdapter
from .options_chain_adapter import OptionsChainAdapter
from .news_adapter import NewsAdapter


@dataclass
class UnusualWhalesQuote:
    """Market quote from Unusual Whales."""
    symbol: str
    price: float
    bid: float
    ask: float
    volume: int
    open: float
    high: float
    low: float
    close: float
    timestamp: datetime
    iv: Optional[float] = None
    options_volume: Optional[int] = None
    put_call_ratio: Optional[float] = None


class UnusualWhalesPrimaryAdapter(MarketDataAdapter, OptionsChainAdapter, NewsAdapter):
    """
    Primary adapter that uses Unusual Whales for ALL data needs.
    
    This is the MAIN data source for Super Gnosis. It provides:
    1. Market quotes and OHLCV data
    2. Options chains with full Greeks
    3. Options flow and unusual activity
    4. Market sentiment and tide
    5. Congressional/insider trades
    6. News sentiment (derived from flow)
    
    Usage:
        adapter = UnusualWhalesPrimaryAdapter()
        
        # Get market quote
        quote = adapter.get_quote("SPY")
        
        # Get options flow
        flow = adapter.get_options_flow(ticker="SPY", min_premium=100000)
        
        # Get market sentiment
        sentiment = adapter.get_market_sentiment()
        
        # Get options chain
        chain = adapter.fetch_chain("SPY")
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        use_test_key: bool = False,
        cache_ttl: int = 60,  # Cache TTL in seconds
        fallback_adapter: Optional[Any] = None
    ):
        """
        Initialize the primary Unusual Whales adapter.
        
        Args:
            api_key: Unusual Whales API key
            use_test_key: Use test key for development
            cache_ttl: Cache time-to-live in seconds
            fallback_adapter: Secondary adapter for fallback (optional)
        """
        # Initialize base Unusual Whales adapter
        self.uw = UnusualWhalesAdapter(
            api_key=api_key,
            use_test_key=use_test_key
        )
        
        self.cache_ttl = cache_ttl
        self.fallback_adapter = fallback_adapter
        
        # Cache for recent data
        self._quote_cache: Dict[str, Any] = {}
        self._chain_cache: Dict[str, Any] = {}
        self._flow_cache: Dict[str, Any] = {}
        self._sentiment_cache: Optional[Dict] = None
        self._sentiment_cache_time: Optional[datetime] = None
        
        logger.info("🐋 UnusualWhalesPrimaryAdapter initialized as PRIMARY data source")
        
        # Test connection
        if self.uw.test_connection():
            logger.success("✅ Unusual Whales connection verified")
        else:
            logger.warning("⚠️ Unusual Whales connection test failed - will retry on demand")
    
    # ========================================================================
    # MARKET DATA ADAPTER PROTOCOL
    # ========================================================================
    
    def fetch_ohlcv(
        self,
        symbol: str,
        lookback: int,
        now: datetime
    ) -> pd.DataFrame:
        """
        Fetch OHLCV data from Unusual Whales.
        
        Args:
            symbol: Stock symbol
            lookback: Number of days to look back
            now: Current timestamp
        
        Returns:
            DataFrame with columns: open, high, low, close, volume
        """
        logger.debug(f"Fetching OHLCV for {symbol} (lookback={lookback} days)")
        
        try:
            # Calculate date range
            end_date = now.strftime("%Y-%m-%d")
            start_date = (now - timedelta(days=lookback)).strftime("%Y-%m-%d")
            
            # Fetch from Unusual Whales
            data = self.uw.get_ticker_historical(
                ticker=symbol,
                start_date=start_date,
                end_date=end_date
            )
            
            # Convert to DataFrame
            records = data.get("data", [])
            if not records:
                logger.warning(f"No OHLCV data for {symbol}")
                if self.fallback_adapter:
                    logger.info("Using fallback adapter")
                    return self.fallback_adapter.fetch_ohlcv(symbol, lookback, now)
                return pd.DataFrame()
            
            df = pd.DataFrame(records)
            
            # Ensure required columns
            required_cols = ["open", "high", "low", "close", "volume"]
            for col in required_cols:
                if col not in df.columns:
                    df[col] = 0.0
            
            # Add timestamp if missing
            if "timestamp" not in df.columns and "date" in df.columns:
                df["timestamp"] = pd.to_datetime(df["date"])
            
            logger.info(f"Retrieved {len(df)} OHLCV records for {symbol}")
            return df[required_cols]
            
        except Exception as e:
            logger.error(f"Error fetching OHLCV for {symbol}: {e}")
            if self.fallback_adapter:
                logger.info("Using fallback adapter")
                return self.fallback_adapter.fetch_ohlcv(symbol, lookback, now)
            return pd.DataFrame()
    
    def get_quote(self, symbol: str) -> Optional[UnusualWhalesQuote]:
        """
        Get real-time quote from Unusual Whales.
        
        Args:
            symbol: Stock symbol
        
        Returns:
            Quote object with price, bid/ask, volume, etc.
        """
        logger.debug(f"Getting quote for {symbol}")
        
        # Check cache
        cache_key = f"{symbol}_quote"
        if cache_key in self._quote_cache:
            cached_time = self._quote_cache[cache_key]["time"]
            if (datetime.now() - cached_time).total_seconds() < self.cache_ttl:
                logger.debug(f"Using cached quote for {symbol}")
                return self._quote_cache[cache_key]["data"]
        
        try:
            # Get ticker overview from Unusual Whales
            data = self.uw.get_ticker_overview(symbol)
            
            if not data:
                logger.warning(f"No quote data for {symbol}")
                return None
            
            # Parse quote data
            quote = UnusualWhalesQuote(
                symbol=symbol,
                price=data.get("price", 0.0),
                bid=data.get("bid", 0.0),
                ask=data.get("ask", 0.0),
                volume=data.get("volume", 0),
                open=data.get("open", 0.0),
                high=data.get("high", 0.0),
                low=data.get("low", 0.0),
                close=data.get("close", data.get("price", 0.0)),
                timestamp=datetime.now(timezone.utc),
                iv=data.get("iv", None),
                options_volume=data.get("options_volume", None),
                put_call_ratio=data.get("put_call_ratio", None)
            )
            
            # Cache the quote
            self._quote_cache[cache_key] = {
                "data": quote,
                "time": datetime.now()
            }
            
            logger.info(f"Quote for {symbol}: ${quote.price:.2f} (IV: {quote.iv:.2%})")
            return quote
            
        except Exception as e:
            logger.error(f"Error getting quote for {symbol}: {e}")
            return None
    
    # ========================================================================
    # OPTIONS CHAIN ADAPTER PROTOCOL
    # ========================================================================
    
    def fetch_chain(
        self,
        symbol: str,
        expiry: Optional[str] = None
    ) -> pl.DataFrame:
        """
        Fetch options chain from Unusual Whales.
        
        Args:
            symbol: Stock symbol
            expiry: Optional expiration date (YYYY-MM-DD)
        
        Returns:
            Polars DataFrame with options chain data
        """
        logger.debug(f"Fetching options chain for {symbol}")
        
        # Check cache
        cache_key = f"{symbol}_chain_{expiry or 'all'}"
        if cache_key in self._chain_cache:
            cached_time = self._chain_cache[cache_key]["time"]
            if (datetime.now() - cached_time).total_seconds() < self.cache_ttl * 2:  # Longer cache for chains
                logger.debug(f"Using cached chain for {symbol}")
                return self._chain_cache[cache_key]["data"]
        
        try:
            # Fetch from Unusual Whales
            data = self.uw.get_ticker_chain(
                ticker=symbol,
                expiration=expiry
            )
            
            if not data:
                logger.warning(f"No chain data for {symbol}")
                return pl.DataFrame()
            
            # Combine calls and puts
            calls = data.get("calls", [])
            puts = data.get("puts", [])
            
            # Convert to records
            records = []
            
            for call in calls:
                records.append({
                    "symbol": symbol,
                    "expiry": call.get("expiration"),
                    "strike": call.get("strike"),
                    "option_type": "call",
                    "bid": call.get("bid", 0.0),
                    "ask": call.get("ask", 0.0),
                    "last": call.get("last", 0.0),
                    "volume": call.get("volume", 0),
                    "open_interest": call.get("open_interest", 0),
                    "iv": call.get("iv", 0.0),
                    "delta": call.get("delta", 0.0),
                    "gamma": call.get("gamma", 0.0),
                    "theta": call.get("theta", 0.0),
                    "vega": call.get("vega", 0.0),
                    "rho": call.get("rho", 0.0)
                })
            
            for put in puts:
                records.append({
                    "symbol": symbol,
                    "expiry": put.get("expiration"),
                    "strike": put.get("strike"),
                    "option_type": "put",
                    "bid": put.get("bid", 0.0),
                    "ask": put.get("ask", 0.0),
                    "last": put.get("last", 0.0),
                    "volume": put.get("volume", 0),
                    "open_interest": put.get("open_interest", 0),
                    "iv": put.get("iv", 0.0),
                    "delta": put.get("delta", 0.0),
                    "gamma": put.get("gamma", 0.0),
                    "theta": put.get("theta", 0.0),
                    "vega": put.get("vega", 0.0),
                    "rho": put.get("rho", 0.0)
                })
            
            # Create Polars DataFrame
            df = pl.DataFrame(records)
            
            # Cache the chain
            self._chain_cache[cache_key] = {
                "data": df,
                "time": datetime.now()
            }
            
            logger.info(f"Retrieved chain for {symbol}: {len(df)} options")
            return df
            
        except Exception as e:
            logger.error(f"Error fetching chain for {symbol}: {e}")
            if self.fallback_adapter and hasattr(self.fallback_adapter, 'fetch_chain'):
                logger.info("Using fallback adapter")
                return self.fallback_adapter.fetch_chain(symbol, expiry)
            return pl.DataFrame()
    
    # ========================================================================
    # OPTIONS FLOW & SENTIMENT
    # ========================================================================
    
    def get_options_flow(
        self,
        ticker: Optional[str] = None,
        limit: int = 100,
        min_premium: Optional[float] = None,
        sentiment_filter: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get options flow from Unusual Whales.
        
        Args:
            ticker: Optional ticker filter
            limit: Number of records
            min_premium: Minimum premium filter
            sentiment_filter: "bullish", "bearish", or "neutral"
        
        Returns:
            Options flow data
        """
        logger.debug(f"Getting options flow (ticker={ticker}, limit={limit})")
        
        # Check cache
        cache_key = f"flow_{ticker or 'all'}_{limit}"
        if cache_key in self._flow_cache:
            cached_time = self._flow_cache[cache_key]["time"]
            if (datetime.now() - cached_time).total_seconds() < 30:  # Short cache for flow
                logger.debug("Using cached flow data")
                return self._flow_cache[cache_key]["data"]
        
        try:
            # Fetch from Unusual Whales
            if ticker:
                data = self.uw.get_ticker_flow(ticker, limit=limit)
            else:
                data = self.uw.get_options_flow(
                    limit=limit,
                    min_premium=min_premium,
                    sentiment=sentiment_filter
                )
            
            # Cache the flow
            self._flow_cache[cache_key] = {
                "data": data,
                "time": datetime.now()
            }
            
            logger.info(f"Retrieved {len(data.get('data', []))} flow records")
            return data
            
        except Exception as e:
            logger.error(f"Error getting options flow: {e}")
            return {"data": [], "error": str(e)}
    
    def get_flow_alerts(
        self,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get high-urgency flow alerts from Unusual Whales.
        
        Args:
            limit: Number of alerts
        
        Returns:
            List of alert records
        """
        logger.debug(f"Getting flow alerts (limit={limit})")
        
        try:
            data = self.uw.get_flow_alerts(limit=limit)
            alerts = data.get("data", [])
            
            logger.info(f"Retrieved {len(alerts)} flow alerts")
            return alerts
            
        except Exception as e:
            logger.error(f"Error getting flow alerts: {e}")
            return []
    
    def get_market_sentiment(self) -> Dict[str, Any]:
        """
        Get market-wide sentiment from Unusual Whales.
        
        Returns:
            Market sentiment data including tide, put/call ratio, etc.
        """
        logger.debug("Getting market sentiment")
        
        # Check cache
        if self._sentiment_cache_time:
            cache_age = (datetime.now() - self._sentiment_cache_time).total_seconds()
            if cache_age < 60 and self._sentiment_cache:  # 1 minute cache
                logger.debug("Using cached sentiment")
                return self._sentiment_cache
        
        try:
            # Get market tide
            tide_data = self.uw.get_market_tide()
            
            # Get recent flow for sentiment analysis
            flow_data = self.uw.get_options_flow(limit=100)
            flow_records = flow_data.get("data", [])
            
            # Calculate sentiment metrics
            bullish_flow = sum(1 for f in flow_records if f.get("sentiment") == "bullish")
            bearish_flow = sum(1 for f in flow_records if f.get("sentiment") == "bearish")
            total_flow = len(flow_records)
            
            bullish_premium = sum(
                f.get("premium", 0) for f in flow_records 
                if f.get("sentiment") == "bullish"
            )
            bearish_premium = sum(
                f.get("premium", 0) for f in flow_records 
                if f.get("sentiment") == "bearish"
            )
            
            sentiment = {
                "tide": tide_data.get("tide", "neutral"),
                "tide_score": tide_data.get("sentiment", 0),
                "put_call_ratio": tide_data.get("ratio", 1.0),
                "call_premium": tide_data.get("call_premium", 0),
                "put_premium": tide_data.get("put_premium", 0),
                "bullish_flow_count": bullish_flow,
                "bearish_flow_count": bearish_flow,
                "bullish_flow_pct": bullish_flow / max(total_flow, 1),
                "bearish_flow_pct": bearish_flow / max(total_flow, 1),
                "bullish_premium": bullish_premium,
                "bearish_premium": bearish_premium,
                "net_premium": bullish_premium - bearish_premium,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            # Determine overall sentiment
            if sentiment["bullish_flow_pct"] > 0.6:
                sentiment["overall"] = "bullish"
            elif sentiment["bearish_flow_pct"] > 0.6:
                sentiment["overall"] = "bearish"
            else:
                sentiment["overall"] = "neutral"
            
            # Cache the sentiment
            self._sentiment_cache = sentiment
            self._sentiment_cache_time = datetime.now()
            
            logger.info(
                f"Market sentiment: {sentiment['overall']} "
                f"(tide: {sentiment['tide']}, P/C: {sentiment['put_call_ratio']:.2f})"
            )
            return sentiment
            
        except Exception as e:
            logger.error(f"Error getting market sentiment: {e}")
            return {
                "overall": "neutral",
                "tide": "unknown",
                "error": str(e)
            }
    
    # ========================================================================
    # NEWS ADAPTER PROTOCOL (Derived from Flow)
    # ========================================================================
    
    def fetch_news(
        self,
        symbol: Optional[str] = None,
        lookback_hours: int = 24
    ) -> List[Dict[str, Any]]:
        """
        Get news sentiment derived from options flow and congressional trades.
        
        Since Unusual Whales doesn't have a dedicated news endpoint,
        we derive "news" from significant flow events and insider activity.
        
        Args:
            symbol: Optional ticker filter
            lookback_hours: Hours to look back
        
        Returns:
            List of news-like events
        """
        logger.debug(f"Fetching news events for {symbol or 'market'}")
        
        news_items = []
        
        try:
            # Get flow alerts as "news"
            if symbol:
                flow_data = self.uw.get_ticker_flow(symbol, limit=50)
            else:
                flow_data = self.uw.get_flow_alerts(limit=50)
            
            flow_records = flow_data.get("data", [])
            
            # Convert significant flow to news items
            for flow in flow_records:
                if flow.get("premium", 0) > 100000:  # Significant size
                    news_items.append({
                        "headline": f"Unusual Options Activity: {flow.get('ticker', 'Unknown')}",
                        "summary": (
                            f"{flow.get('sentiment', 'Unknown').upper()} "
                            f"{flow.get('trade_type', 'trade')} detected: "
                            f"${flow.get('premium', 0):,.0f} premium"
                        ),
                        "sentiment": flow.get("sentiment", "neutral"),
                        "ticker": flow.get("ticker"),
                        "timestamp": flow.get("timestamp", datetime.now().isoformat()),
                        "source": "unusual_whales_flow",
                        "importance": "high" if flow.get("premium", 0) > 500000 else "medium"
                    })
            
            # Get congressional trades as "news"
            try:
                congress_data = self.uw.get_congress_trades(
                    ticker=symbol,
                    limit=20
                )
                congress_records = congress_data.get("data", [])
                
                for trade in congress_records:
                    news_items.append({
                        "headline": f"Congressional Trade: {trade.get('politician', 'Unknown')}",
                        "summary": (
                            f"{trade.get('politician')} "
                            f"{trade.get('transaction_type', 'traded')} "
                            f"{trade.get('ticker', 'unknown symbol')}"
                        ),
                        "sentiment": (
                            "bullish" if trade.get("transaction_type") == "buy" 
                            else "bearish"
                        ),
                        "ticker": trade.get("ticker"),
                        "timestamp": trade.get("date", datetime.now().isoformat()),
                        "source": "congressional_trades",
                        "importance": "high"
                    })
            except Exception as e:
                logger.debug(f"Could not fetch congressional trades: {e}")
            
            logger.info(f"Generated {len(news_items)} news items from flow and trades")
            return news_items
            
        except Exception as e:
            logger.error(f"Error fetching news: {e}")
            return []
    
    # ========================================================================
    # SPECIALIZED UNUSUAL WHALES FEATURES
    # ========================================================================
    
    def get_gamma_exposure(
        self,
        symbol: str
    ) -> Dict[str, Any]:
        """
        Calculate gamma exposure from options chain.
        
        Args:
            symbol: Stock symbol
        
        Returns:
            Gamma exposure analysis
        """
        logger.debug(f"Calculating gamma exposure for {symbol}")
        
        try:
            # Get options chain
            chain_df = self.fetch_chain(symbol)
            
            if chain_df.is_empty():
                return {"error": "No chain data"}
            
            # Calculate net gamma
            calls_gamma = chain_df.filter(
                pl.col("option_type") == "call"
            )["gamma"].sum()
            
            puts_gamma = chain_df.filter(
                pl.col("option_type") == "put"
            )["gamma"].sum()
            
            net_gamma = calls_gamma - puts_gamma
            
            # Find max gamma strikes
            max_call_gamma = chain_df.filter(
                pl.col("option_type") == "call"
            ).sort("gamma", descending=True).head(1)
            
            max_put_gamma = chain_df.filter(
                pl.col("option_type") == "put"
            ).sort("gamma", descending=True).head(1)
            
            return {
                "net_gamma": net_gamma,
                "calls_gamma": calls_gamma,
                "puts_gamma": puts_gamma,
                "gamma_flip": net_gamma < 0,
                "max_call_gamma_strike": (
                    max_call_gamma["strike"][0] if not max_call_gamma.is_empty() 
                    else None
                ),
                "max_put_gamma_strike": (
                    max_put_gamma["strike"][0] if not max_put_gamma.is_empty() 
                    else None
                )
            }
            
        except Exception as e:
            logger.error(f"Error calculating gamma exposure: {e}")
            return {"error": str(e)}
    
    def get_insider_signals(
        self,
        symbol: Optional[str] = None,
        days_back: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get insider and congressional trading signals.
        
        Args:
            symbol: Optional ticker filter
            days_back: Days to look back
        
        Returns:
            List of insider signals
        """
        logger.debug(f"Getting insider signals for {symbol or 'all'}")
        
        signals = []
        
        try:
            # Get congressional trades
            congress_data = self.uw.get_congress_trades(
                ticker=symbol,
                limit=100
            )
            
            for trade in congress_data.get("data", []):
                signals.append({
                    "type": "congressional",
                    "ticker": trade.get("ticker"),
                    "insider": trade.get("politician"),
                    "action": trade.get("transaction_type"),
                    "date": trade.get("date"),
                    "signal": (
                        "bullish" if trade.get("transaction_type") == "buy" 
                        else "bearish"
                    ),
                    "confidence": 0.7  # Congressional trades have decent predictive value
                })
            
            # Get insider trades
            insider_data = self.uw.get_insider_trades(
                ticker=symbol,
                limit=100
            )
            
            for trade in insider_data.get("data", []):
                signals.append({
                    "type": "insider",
                    "ticker": trade.get("ticker"),
                    "insider": trade.get("insider_name"),
                    "action": trade.get("transaction_type"),
                    "shares": trade.get("shares"),
                    "value": trade.get("value"),
                    "date": trade.get("date"),
                    "signal": (
                        "bullish" if trade.get("transaction_type") in ["buy", "acquire"] 
                        else "bearish"
                    ),
                    "confidence": 0.8  # Insider trades have high predictive value
                })
            
            logger.info(f"Found {len(signals)} insider signals")
            return signals
            
        except Exception as e:
            logger.error(f"Error getting insider signals: {e}")
            return []
    
    # ========================================================================
    # MONITORING & SCANNING
    # ========================================================================
    
    def scan_unusual_activity(
        self,
        min_premium: float = 500000,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Scan for unusual options activity across all symbols.
        
        Args:
            min_premium: Minimum premium threshold
            limit: Number of results
        
        Returns:
            List of unusual activity alerts
        """
        logger.info(f"Scanning for unusual activity (min_premium=${min_premium:,.0f})")
        
        try:
            # Get flow alerts
            data = self.uw.get_flow_alerts(limit=limit)
            alerts = data.get("data", [])
            
            # Filter and enhance
            unusual = []
            for alert in alerts:
                if alert.get("premium", 0) >= min_premium:
                    unusual.append({
                        "ticker": alert.get("ticker"),
                        "type": alert.get("trade_type"),
                        "sentiment": alert.get("sentiment"),
                        "premium": alert.get("premium"),
                        "volume": alert.get("volume"),
                        "strike": alert.get("strike"),
                        "expiry": alert.get("expiry"),
                        "timestamp": alert.get("timestamp"),
                        "urgency": "high" if alert.get("premium", 0) > 1000000 else "medium",
                        "description": (
                            f"{alert.get('sentiment', '').upper()} "
                            f"{alert.get('trade_type', 'activity')}: "
                            f"${alert.get('premium', 0):,.0f}"
                        )
                    })
            
            logger.info(f"Found {len(unusual)} unusual activities")
            return unusual
            
        except Exception as e:
            logger.error(f"Error scanning unusual activity: {e}")
            return []
    
    def get_watchlist_overview(
        self,
        symbols: List[str]
    ) -> Dict[str, Any]:
        """
        Get overview for a list of symbols using Unusual Whales.
        
        Args:
            symbols: List of stock symbols
        
        Returns:
            Overview data for each symbol
        """
        logger.info(f"Getting overview for {len(symbols)} symbols")
        
        overview = {}
        
        for symbol in symbols:
            try:
                # Get quote and flow
                quote = self.get_quote(symbol)
                flow = self.get_options_flow(ticker=symbol, limit=10)
                
                # Calculate flow sentiment
                flow_records = flow.get("data", [])
                bullish = sum(1 for f in flow_records if f.get("sentiment") == "bullish")
                bearish = sum(1 for f in flow_records if f.get("sentiment") == "bearish")
                
                overview[symbol] = {
                    "price": quote.price if quote else 0,
                    "volume": quote.volume if quote else 0,
                    "iv": quote.iv if quote else 0,
                    "options_volume": quote.options_volume if quote else 0,
                    "put_call_ratio": quote.put_call_ratio if quote else 1.0,
                    "flow_sentiment": (
                        "bullish" if bullish > bearish 
                        else "bearish" if bearish > bullish 
                        else "neutral"
                    ),
                    "recent_flow_count": len(flow_records),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                
            except Exception as e:
                logger.error(f"Error getting overview for {symbol}: {e}")
                overview[symbol] = {"error": str(e)}
        
        return overview


# ============================================================================
# FACTORY FUNCTION
# ============================================================================

def create_primary_adapter(
    api_key: Optional[str] = None,
    use_test_key: bool = False
) -> UnusualWhalesPrimaryAdapter:
    """
    Create the primary Unusual Whales adapter for Super Gnosis.
    
    This should be used as the MAIN data source throughout the framework.
    
    Args:
        api_key: Unusual Whales API key
        use_test_key: Use test key for development
    
    Returns:
        Configured primary adapter
    """
    return UnusualWhalesPrimaryAdapter(
        api_key=api_key,
        use_test_key=use_test_key
    )


# ============================================================================
# INTEGRATION HELPERS
# ============================================================================

def replace_all_adapters() -> Dict[str, UnusualWhalesPrimaryAdapter]:
    """
    Replace ALL data adapters with Unusual Whales as primary.
    
    Returns:
        Dictionary of adapter types all pointing to Unusual Whales
    """
    adapter = create_primary_adapter()
    
    return {
        "market": adapter,
        "options": adapter,
        "news": adapter,
        "flow": adapter,
        "sentiment": adapter,
        "insider": adapter
    }


if __name__ == "__main__":
    # Test the primary adapter
    print("="*60)
    print("🐋 UNUSUAL WHALES PRIMARY ADAPTER TEST")
    print("="*60)
    
    # Create adapter
    adapter = create_primary_adapter(use_test_key=True)
    
    # Test market quote
    print("\n1. Market Quote Test")
    quote = adapter.get_quote("SPY")
    if quote:
        print(f"   SPY: ${quote.price:.2f} (IV: {quote.iv:.2%})")
    
    # Test options chain
    print("\n2. Options Chain Test")
    chain = adapter.fetch_chain("SPY")
    print(f"   Chain size: {len(chain)} options")
    
    # Test options flow
    print("\n3. Options Flow Test")
    flow = adapter.get_options_flow(limit=5)
    print(f"   Flow records: {len(flow.get('data', []))}")
    
    # Test market sentiment
    print("\n4. Market Sentiment Test")
    sentiment = adapter.get_market_sentiment()
    print(f"   Market: {sentiment.get('overall')} (tide: {sentiment.get('tide')})")
    
    # Test unusual activity scan
    print("\n5. Unusual Activity Scan")
    unusual = adapter.scan_unusual_activity(min_premium=100000, limit=5)
    print(f"   Found {len(unusual)} unusual activities")
    for u in unusual[:3]:
        print(f"   - {u['ticker']}: {u['description']}")
    
    print("\n" + "="*60)
    print("✅ Unusual Whales is now the PRIMARY data source!")
    print("="*60)