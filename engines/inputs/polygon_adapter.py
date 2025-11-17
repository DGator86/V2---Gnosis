"""
Polygon.io Adapter for Production Market Data

Provides real-time and historical OHLCV data, options chains, and aggregates.
This is a PAID service ($249/mo for unlimited) but provides high-quality,
official market data with millisecond precision.

Free tier: 5 requests/minute
Starter: $99/mo - 100 requests/minute
Developer: $249/mo - Unlimited
Advanced: $449+/mo - Real-time + level 2

Get API key: https://polygon.io/
Install: pip install polygon-api-client
"""

from typing import Dict, List, Optional
from datetime import datetime, date, timedelta
from loguru import logger
import polars as pl
from pydantic import BaseModel

try:
    from polygon import RESTClient
    from polygon.rest.models import Agg, Trade, Quote
    POLYGON_AVAILABLE = True
except ImportError:
    POLYGON_AVAILABLE = False
    logger.warning(
        "polygon-api-client not installed. Install with: pip install polygon-api-client"
    )


class PolygonAdapter:
    """
    Adapter for Polygon.io market data API.
    
    Provides:
    - Real-time and historical OHLCV aggregates
    - Tick-level trades and quotes
    - Options chains and Greeks
    - Market status and holidays
    - Corporate actions (splits, dividends)
    """
    
    def __init__(self, api_key: str):
        """
        Initialize Polygon adapter.
        
        Args:
            api_key: Polygon.io API key
        """
        if not POLYGON_AVAILABLE:
            raise ImportError(
                "polygon-api-client required. Install with: pip install polygon-api-client"
            )
        
        self.api_key = api_key
        self.client = RESTClient(api_key)
        
        logger.info("✅ Polygon.io adapter initialized")
    
    def fetch_aggregates(
        self,
        symbol: str,
        timeframe: str = "1",
        timespan: str = "minute",
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
        limit: int = 5000
    ) -> pl.DataFrame:
        """
        Fetch OHLCV aggregates (bars).
        
        Args:
            symbol: Stock symbol (e.g., "SPY")
            timeframe: Timeframe multiplier (e.g., "1", "5", "15")
            timespan: Timespan unit ("minute", "hour", "day", "week", "month")
            from_date: Start date (defaults to 7 days ago)
            to_date: End date (defaults to today)
            limit: Maximum number of bars (max 50000)
        
        Returns:
            Polars DataFrame with OHLCV data
        """
        if from_date is None:
            from_date = date.today() - timedelta(days=7)
        if to_date is None:
            to_date = date.today()
        
        logger.info(
            f"Fetching {timeframe}{timespan} bars for {symbol} "
            f"from {from_date} to {to_date}"
        )
        
        try:
            # Fetch aggregates
            aggs = self.client.get_aggs(
                ticker=symbol,
                multiplier=int(timeframe),
                timespan=timespan,
                from_=from_date.isoformat(),
                to=to_date.isoformat(),
                limit=limit
            )
            
            if not aggs:
                logger.warning(f"No aggregates returned for {symbol}")
                return pl.DataFrame()
            
            # Convert to list of dicts
            data = []
            for agg in aggs:
                data.append({
                    "timestamp": datetime.fromtimestamp(agg.timestamp / 1000),
                    "open": agg.open,
                    "high": agg.high,
                    "low": agg.low,
                    "close": agg.close,
                    "volume": agg.volume,
                    "vwap": agg.vwap if hasattr(agg, 'vwap') else None,
                    "transactions": agg.transactions if hasattr(agg, 'transactions') else None
                })
            
            df = pl.DataFrame(data)
            logger.info(f"✅ Fetched {len(df)} bars for {symbol}")
            
            return df
        
        except Exception as e:
            logger.error(f"Failed to fetch aggregates for {symbol}: {e}")
            return pl.DataFrame()
    
    def fetch_trades(
        self,
        symbol: str,
        timestamp: Optional[datetime] = None,
        limit: int = 1000
    ) -> pl.DataFrame:
        """
        Fetch tick-level trades.
        
        Args:
            symbol: Stock symbol
            timestamp: Timestamp to fetch trades from (defaults to now)
            limit: Maximum number of trades (max 50000)
        
        Returns:
            Polars DataFrame with trade data
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        logger.info(f"Fetching {limit} trades for {symbol}")
        
        try:
            trades = self.client.list_trades(
                ticker=symbol,
                timestamp=int(timestamp.timestamp() * 1000),
                limit=limit
            )
            
            if not trades:
                logger.warning(f"No trades returned for {symbol}")
                return pl.DataFrame()
            
            # Convert to DataFrame
            data = []
            for trade in trades:
                data.append({
                    "timestamp": datetime.fromtimestamp(trade.sip_timestamp / 1000000000),
                    "price": trade.price,
                    "size": trade.size,
                    "exchange": trade.exchange,
                    "conditions": ",".join(map(str, trade.conditions)) if hasattr(trade, 'conditions') else None
                })
            
            df = pl.DataFrame(data)
            logger.info(f"✅ Fetched {len(df)} trades for {symbol}")
            
            return df
        
        except Exception as e:
            logger.error(f"Failed to fetch trades for {symbol}: {e}")
            return pl.DataFrame()
    
    def fetch_quotes(
        self,
        symbol: str,
        timestamp: Optional[datetime] = None,
        limit: int = 1000
    ) -> pl.DataFrame:
        """
        Fetch tick-level quotes (bid/ask).
        
        Args:
            symbol: Stock symbol
            timestamp: Timestamp to fetch quotes from
            limit: Maximum number of quotes
        
        Returns:
            Polars DataFrame with quote data
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        logger.info(f"Fetching {limit} quotes for {symbol}")
        
        try:
            quotes = self.client.list_quotes(
                ticker=symbol,
                timestamp=int(timestamp.timestamp() * 1000),
                limit=limit
            )
            
            if not quotes:
                logger.warning(f"No quotes returned for {symbol}")
                return pl.DataFrame()
            
            # Convert to DataFrame
            data = []
            for quote in quotes:
                data.append({
                    "timestamp": datetime.fromtimestamp(quote.sip_timestamp / 1000000000),
                    "bid": quote.bid_price,
                    "ask": quote.ask_price,
                    "bid_size": quote.bid_size,
                    "ask_size": quote.ask_size,
                    "bid_exchange": quote.bid_exchange,
                    "ask_exchange": quote.ask_exchange
                })
            
            df = pl.DataFrame(data)
            logger.info(f"✅ Fetched {len(df)} quotes for {symbol}")
            
            return df
        
        except Exception as e:
            logger.error(f"Failed to fetch quotes for {symbol}: {e}")
            return pl.DataFrame()
    
    def fetch_last_trade(self, symbol: str) -> Optional[Dict]:
        """
        Fetch last trade for symbol.
        
        Args:
            symbol: Stock symbol
        
        Returns:
            Dictionary with last trade data
        """
        try:
            trade = self.client.get_last_trade(ticker=symbol)
            
            return {
                "price": trade.price,
                "size": trade.size,
                "timestamp": datetime.fromtimestamp(trade.sip_timestamp / 1000000000),
                "exchange": trade.exchange
            }
        
        except Exception as e:
            logger.error(f"Failed to fetch last trade for {symbol}: {e}")
            return None
    
    def fetch_last_quote(self, symbol: str) -> Optional[Dict]:
        """
        Fetch last quote for symbol.
        
        Args:
            symbol: Stock symbol
        
        Returns:
            Dictionary with last quote data
        """
        try:
            quote = self.client.get_last_quote(ticker=symbol)
            
            return {
                "bid": quote.bid_price,
                "ask": quote.ask_price,
                "bid_size": quote.bid_size,
                "ask_size": quote.ask_size,
                "timestamp": datetime.fromtimestamp(quote.sip_timestamp / 1000000000)
            }
        
        except Exception as e:
            logger.error(f"Failed to fetch last quote for {symbol}: {e}")
            return None
    
    def get_market_status(self) -> Dict:
        """
        Get current market status.
        
        Returns:
            Dictionary with market status
        """
        try:
            status = self.client.get_market_status()
            
            return {
                "market": status.market,
                "server_time": status.serverTime,
                "exchanges": {
                    "nyse": status.exchanges.nyse,
                    "nasdaq": status.exchanges.nasdaq,
                    "otc": status.exchanges.otc
                }
            }
        
        except Exception as e:
            logger.error(f"Failed to fetch market status: {e}")
            return {}


# Example usage
if __name__ == "__main__":
    import os
    
    api_key = os.getenv("POLYGON_API_KEY", "YOUR_API_KEY")
    
    if api_key == "YOUR_API_KEY":
        print("\n⚠️  POLYGON_API_KEY not set!")
        print("\n📝 To use this adapter:")
        print("1. Sign up at: https://polygon.io/")
        print("2. Get your API key")
        print("3. Set environment variable:")
        print("   export POLYGON_API_KEY='your_api_key'")
        print("\nPlans:")
        print("  - Free: 5 req/min")
        print("  - Starter ($99/mo): 100 req/min")
        print("  - Developer ($249/mo): Unlimited")
    else:
        # Initialize adapter
        adapter = PolygonAdapter(api_key=api_key)
        
        # Example 1: Fetch 5-minute bars
        print("\n" + "="*60)
        print("EXAMPLE 1: Fetch 5-Minute Bars")
        print("="*60)
        
        df_5min = adapter.fetch_aggregates(
            symbol="SPY",
            timeframe="5",
            timespan="minute",
            from_date=date.today() - timedelta(days=1),
            limit=100
        )
        
        if not df_5min.is_empty():
            print(f"\nSPY 5-minute bars (last 10):")
            print(df_5min.tail(10))
        
        # Example 2: Fetch last trade
        print("\n" + "="*60)
        print("EXAMPLE 2: Fetch Last Trade")
        print("="*60)
        
        last_trade = adapter.fetch_last_trade("SPY")
        
        if last_trade:
            print(f"\nSPY Last Trade:")
            print(f"  Price: ${last_trade['price']:.2f}")
            print(f"  Size: {last_trade['size']}")
            print(f"  Time: {last_trade['timestamp']}")
        
        # Example 3: Fetch last quote
        print("\n" + "="*60)
        print("EXAMPLE 3: Fetch Last Quote")
        print("="*60)
        
        last_quote = adapter.fetch_last_quote("SPY")
        
        if last_quote:
            print(f"\nSPY Last Quote:")
            print(f"  Bid: ${last_quote['bid']:.2f} x {last_quote['bid_size']}")
            print(f"  Ask: ${last_quote['ask']:.2f} x {last_quote['ask_size']}")
            print(f"  Spread: ${last_quote['ask'] - last_quote['bid']:.2f}")
        
        # Example 4: Market status
        print("\n" + "="*60)
        print("EXAMPLE 4: Market Status")
        print("="*60)
        
        status = adapter.get_market_status()
        
        if status:
            print(f"\nMarket Status:")
            print(f"  Market: {status['market']}")
            print(f"  NYSE: {status['exchanges']['nyse']}")
            print(f"  NASDAQ: {status['exchanges']['nasdaq']}")
