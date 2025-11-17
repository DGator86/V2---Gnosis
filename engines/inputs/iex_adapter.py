"""
IEX Cloud Adapter using pyEX library.

Provides backup/alternative data source for market data.
IEX Cloud offers free tier with limited requests.

Uses pyEX: https://github.com/timkpaine/pyEX
IEX Cloud: https://iexcloud.io/

Free tier: 50,000 messages/month
Paid tiers: $9-499/month

This adapter serves as:
1. Backup when primary sources (Alpaca, yfinance) fail
2. Additional data points for validation
3. Access to IEX-specific datasets
"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta
from loguru import logger
import polars as pl
from pydantic import BaseModel

try:
    import pyEX
    PYEX_AVAILABLE = True
except ImportError:
    PYEX_AVAILABLE = False
    logger.warning(
        "pyEX not installed. Install with: pip install pyEX"
    )


class IEXQuote(BaseModel):
    """Real-time quote from IEX."""
    
    symbol: str
    timestamp: str
    
    # Price data
    last_price: float
    bid: Optional[float] = None
    ask: Optional[float] = None
    bid_size: Optional[int] = None
    ask_size: Optional[int] = None
    
    # OHLC
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    
    # Volume
    volume: Optional[int] = None
    avg_volume: Optional[int] = None
    
    # Change
    change: Optional[float] = None
    change_percent: Optional[float] = None
    
    # Market cap
    market_cap: Optional[int] = None
    pe_ratio: Optional[float] = None


class IEXAdapter:
    """
    Adapter for IEX Cloud data using pyEX library.
    
    Provides:
    - Real-time quotes (15-min delay on free tier)
    - Historical OHLCV data
    - Company fundamentals
    - News and sentiment
    - Market stats
    """
    
    def __init__(
        self,
        api_token: str,
        version: str = "stable",
        use_sandbox: bool = False
    ):
        """
        Initialize IEX adapter.
        
        Args:
            api_token: IEX Cloud API token (get free at iexcloud.io)
            version: API version ("stable" or "beta")
            use_sandbox: Use sandbox environment (test mode)
        """
        if not PYEX_AVAILABLE:
            raise ImportError("pyEX is required. Install with: pip install pyEX")
        
        self.api_token = api_token
        self.version = version
        self.use_sandbox = use_sandbox
        
        # Initialize client
        self.client = pyEX.Client(
            api_token=api_token,
            version=version
        )
        
        if use_sandbox:
            logger.warning("Using IEX Cloud SANDBOX mode (test data)")
        
        logger.info(f"✅ IEX adapter initialized (version={version}, sandbox={use_sandbox})")
    
    def fetch_quote(self, symbol: str) -> IEXQuote:
        """
        Fetch real-time quote for a symbol.
        
        Args:
            symbol: Stock symbol (e.g., "SPY")
        
        Returns:
            IEXQuote object
        """
        try:
            data = self.client.quote(symbol)
            
            quote = IEXQuote(
                symbol=symbol,
                timestamp=datetime.now().isoformat(),
                last_price=data.get("latestPrice", 0.0),
                bid=data.get("iexBidPrice"),
                ask=data.get("iexAskPrice"),
                bid_size=data.get("iexBidSize"),
                ask_size=data.get("iexAskSize"),
                open=data.get("open"),
                high=data.get("high"),
                low=data.get("low"),
                close=data.get("previousClose"),
                volume=data.get("latestVolume"),
                avg_volume=data.get("avgTotalVolume"),
                change=data.get("change"),
                change_percent=data.get("changePercent"),
                market_cap=data.get("marketCap"),
                pe_ratio=data.get("peRatio")
            )
            
            logger.info(f"✅ Fetched quote for {symbol}: ${quote.last_price}")
            return quote
        
        except Exception as e:
            logger.error(f"Failed to fetch quote for {symbol}: {e}")
            raise
    
    def fetch_quotes(self, symbols: List[str]) -> pl.DataFrame:
        """
        Fetch quotes for multiple symbols.
        
        Args:
            symbols: List of stock symbols
        
        Returns:
            Polars DataFrame with quotes
        """
        logger.info(f"Fetching quotes for {len(symbols)} symbols")
        
        quotes = []
        for symbol in symbols:
            try:
                quote = self.fetch_quote(symbol)
                quotes.append(quote.model_dump())
            except Exception as e:
                logger.error(f"Failed to fetch {symbol}: {e}")
                continue
        
        if not quotes:
            logger.warning("No quotes fetched")
            return pl.DataFrame()
        
        df = pl.DataFrame(quotes)
        logger.info(f"✅ Fetched {len(df)} quotes")
        
        return df
    
    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1d",
        limit: int = 100
    ) -> pl.DataFrame:
        """
        Fetch historical OHLCV data.
        
        Args:
            symbol: Stock symbol
            timeframe: Timeframe ("1d", "1m", "5m", etc.)
            limit: Number of bars to fetch
        
        Returns:
            Polars DataFrame with OHLCV data
        """
        logger.info(f"Fetching {limit} {timeframe} bars for {symbol}")
        
        try:
            # Map timeframe to IEX range
            if timeframe == "1d":
                range_param = "3m"  # 3 months of daily data
                chart_data = self.client.chartDF(symbol, range=range_param)
            elif timeframe in ["1m", "5m", "15m"]:
                # Intraday data (max 7 days on free tier)
                chart_data = self.client.intradayDF(symbol, exactDate=None)
            else:
                raise ValueError(f"Unsupported timeframe: {timeframe}")
            
            if chart_data.empty:
                logger.warning(f"No data returned for {symbol}")
                return pl.DataFrame()
            
            # Convert to Polars
            df = pl.from_pandas(chart_data.reset_index())
            
            # Standardize column names
            column_mapping = {
                "date": "timestamp",
                "minute": "timestamp"
            }
            
            for old_col, new_col in column_mapping.items():
                if old_col in df.columns:
                    df = df.rename({old_col: new_col})
            
            # Ensure required columns exist
            required_cols = ["timestamp", "open", "high", "low", "close", "volume"]
            missing_cols = [col for col in required_cols if col not in df.columns]
            
            if missing_cols:
                logger.error(f"Missing columns: {missing_cols}")
                return pl.DataFrame()
            
            # Select and order columns
            df = df.select(required_cols)
            
            # Limit rows
            if len(df) > limit:
                df = df.tail(limit)
            
            logger.info(f"✅ Fetched {len(df)} bars for {symbol}")
            return df
        
        except Exception as e:
            logger.error(f"Failed to fetch OHLCV for {symbol}: {e}")
            return pl.DataFrame()
    
    def fetch_company_info(self, symbol: str) -> Dict:
        """
        Fetch company information.
        
        Args:
            symbol: Stock symbol
        
        Returns:
            Dictionary with company info
        """
        try:
            data = self.client.company(symbol)
            logger.info(f"✅ Fetched company info for {symbol}")
            return data
        except Exception as e:
            logger.error(f"Failed to fetch company info for {symbol}: {e}")
            return {}
    
    def fetch_stats(self, symbol: str) -> Dict:
        """
        Fetch key stats (PE ratio, market cap, etc.).
        
        Args:
            symbol: Stock symbol
        
        Returns:
            Dictionary with stats
        """
        try:
            data = self.client.keyStats(symbol)
            logger.info(f"✅ Fetched stats for {symbol}")
            return data
        except Exception as e:
            logger.error(f"Failed to fetch stats for {symbol}: {e}")
            return {}
    
    def fetch_news(
        self,
        symbol: str,
        limit: int = 10
    ) -> pl.DataFrame:
        """
        Fetch news articles for a symbol.
        
        Args:
            symbol: Stock symbol
            limit: Number of articles to fetch
        
        Returns:
            Polars DataFrame with news
        """
        try:
            data = self.client.news(symbol, last=limit)
            
            if not data:
                logger.warning(f"No news found for {symbol}")
                return pl.DataFrame()
            
            news_items = []
            for item in data:
                news_items.append({
                    "symbol": symbol,
                    "timestamp": item.get("datetime"),
                    "headline": item.get("headline"),
                    "source": item.get("source"),
                    "url": item.get("url"),
                    "summary": item.get("summary"),
                    "sentiment": item.get("sentiment")  # If available
                })
            
            df = pl.DataFrame(news_items)
            logger.info(f"✅ Fetched {len(df)} news articles for {symbol}")
            
            return df
        
        except Exception as e:
            logger.error(f"Failed to fetch news for {symbol}: {e}")
            return pl.DataFrame()
    
    def fetch_previous_day(self, symbol: str) -> Dict:
        """
        Fetch previous trading day data.
        
        Args:
            symbol: Stock symbol
        
        Returns:
            Dictionary with previous day OHLCV
        """
        try:
            data = self.client.previousDF(symbol)
            
            if data.empty:
                return {}
            
            # Convert to dict
            result = data.iloc[0].to_dict()
            logger.info(f"✅ Fetched previous day data for {symbol}")
            
            return result
        
        except Exception as e:
            logger.error(f"Failed to fetch previous day for {symbol}: {e}")
            return {}
    
    def fetch_tops(self, symbols: Optional[List[str]] = None) -> pl.DataFrame:
        """
        Fetch TOPS (real-time trade reports).
        
        Args:
            symbols: Optional list of symbols (None = all)
        
        Returns:
            Polars DataFrame with trade data
        """
        try:
            if symbols:
                data = self.client.tops(symbols)
            else:
                data = self.client.tops()
            
            if not data:
                logger.warning("No TOPS data returned")
                return pl.DataFrame()
            
            df = pl.DataFrame(data)
            logger.info(f"✅ Fetched TOPS data for {len(df)} symbols")
            
            return df
        
        except Exception as e:
            logger.error(f"Failed to fetch TOPS: {e}")
            return pl.DataFrame()
    
    def validate_against_primary(
        self,
        symbol: str,
        primary_price: float,
        tolerance: float = 0.01
    ) -> bool:
        """
        Validate IEX price against primary data source.
        
        Args:
            symbol: Stock symbol
            primary_price: Price from primary source
            tolerance: Maximum allowed relative difference (1% = 0.01)
        
        Returns:
            True if prices match within tolerance
        """
        try:
            quote = self.fetch_quote(symbol)
            iex_price = quote.last_price
            
            if primary_price == 0:
                logger.warning(f"Primary price is 0 for {symbol}")
                return False
            
            rel_diff = abs(iex_price - primary_price) / primary_price
            
            if rel_diff <= tolerance:
                logger.info(
                    f"✅ IEX validation passed for {symbol}: "
                    f"primary=${primary_price:.2f}, iex=${iex_price:.2f}, "
                    f"diff={rel_diff:.2%}"
                )
                return True
            else:
                logger.warning(
                    f"⚠️  IEX validation failed for {symbol}: "
                    f"primary=${primary_price:.2f}, iex=${iex_price:.2f}, "
                    f"diff={rel_diff:.2%} > tolerance={tolerance:.2%}"
                )
                return False
        
        except Exception as e:
            logger.error(f"Failed to validate {symbol}: {e}")
            return False


# Example usage
if __name__ == "__main__":
    import os
    
    # Get API token from environment
    api_token = os.getenv("IEX_API_TOKEN", "YOUR_API_TOKEN")
    
    if api_token == "YOUR_API_TOKEN":
        print("\n⚠️  WARNING: IEX API token not configured!")
        print("\n📝 To use this adapter:")
        print("1. Sign up for free at: https://iexcloud.io/")
        print("2. Get your API token (50K messages/month free)")
        print("3. Set environment variable:")
        print("   export IEX_API_TOKEN='your_token'")
        print("\nUsing sandbox mode for examples...\n")
        
        # Use sandbox for examples
        api_token = "Tsk_sandbox_token"
        use_sandbox = True
    else:
        use_sandbox = False
    
    # Initialize adapter
    adapter = IEXAdapter(
        api_token=api_token,
        use_sandbox=use_sandbox
    )
    
    # Example 1: Fetch quote
    print("\n" + "="*60)
    print("EXAMPLE 1: Fetch Real-Time Quote")
    print("="*60)
    
    try:
        quote = adapter.fetch_quote("SPY")
        print(f"\nSPY Quote:")
        print(f"  Last Price: ${quote.last_price:.2f}")
        print(f"  Bid/Ask: ${quote.bid}/{quote.ask}")
        print(f"  Volume: {quote.volume:,}")
        print(f"  Change: {quote.change:+.2f} ({quote.change_percent:+.2%})")
    except Exception as e:
        print(f"Error: {e}")
    
    # Example 2: Fetch OHLCV
    print("\n" + "="*60)
    print("EXAMPLE 2: Fetch Historical OHLCV")
    print("="*60)
    
    df_ohlcv = adapter.fetch_ohlcv("AAPL", timeframe="1d", limit=5)
    
    if not df_ohlcv.is_empty():
        print(f"\nAAPL Last 5 Days:")
        print(df_ohlcv)
    
    # Example 3: Fetch news
    print("\n" + "="*60)
    print("EXAMPLE 3: Fetch News")
    print("="*60)
    
    df_news = adapter.fetch_news("TSLA", limit=5)
    
    if not df_news.is_empty():
        print(f"\nTSLA Latest News:")
        print(df_news.select(["timestamp", "headline", "source"]))
    
    # Example 4: Validate price
    print("\n" + "="*60)
    print("EXAMPLE 4: Validate Against Primary Source")
    print("="*60)
    
    # Simulate primary source price (e.g., from Alpaca)
    primary_price = 450.25
    
    try:
        is_valid = adapter.validate_against_primary(
            symbol="SPY",
            primary_price=primary_price,
            tolerance=0.01  # 1%
        )
        print(f"\nValidation result: {'PASS' if is_valid else 'FAIL'}")
    except Exception as e:
        print(f"Error: {e}")
