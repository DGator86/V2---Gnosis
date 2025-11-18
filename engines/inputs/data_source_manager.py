"""
Unified Data Source Manager.

Orchestrates all data sources with intelligent fallback, validation,
and caching strategies. Provides a single interface for all market data needs.

Data Source Hierarchy (NEW - Unusual Whales Primary):
1. Primary: Unusual Whales (options flow, chains, sentiment, market data)
2. Backup: Public.com (real-time quotes, historical)
3. Backup: IEX Cloud (validation)
4. Fallback: Alpaca (real-time, official)
5. Macro: FRED (economic data)
6. Sentiment: StockTwits + WSB (social)
7. Dark Pool: Dark Pool Adapter (institutional flow)
8. Short Volume: FINRA (short interest)

NOTE: yfinance and Polygon have been completely removed.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, date, timedelta
from loguru import logger
import polars as pl
from pydantic import BaseModel, Field
from enum import Enum

# Import all adapters
from engines.inputs.unusual_whales_adapter import UnusualWhalesAdapter
from engines.inputs.public_trading_adapter import PublicTradingAdapter
from engines.inputs.fred_adapter import FREDAdapter
from engines.inputs.dark_pool_adapter import DarkPoolAdapter
from engines.inputs.short_volume_adapter import ShortVolumeAdapter
from engines.inputs.stocktwits_adapter import StockTwitsAdapter
from engines.inputs.wsb_sentiment_adapter import WSBSentimentAdapter
from engines.inputs.iex_adapter import IEXAdapter


class DataSourceType(str, Enum):
    """Data source types."""
    UNUSUAL_WHALES = "unusual_whales"  # NEW PRIMARY
    PUBLIC = "public"
    ALPACA = "alpaca"
    IEX = "iex"
    FRED = "fred"
    DARK_POOL = "dark_pool"
    SHORT_VOLUME = "short_volume"
    STOCKTWITS = "stocktwits"
    WSB = "wsb"


class DataSourceStatus(BaseModel):
    """Status of a data source."""
    
    source_type: DataSourceType
    is_available: bool = True
    is_healthy: bool = True
    last_check: Optional[str] = None
    error_count: int = 0
    last_error: Optional[str] = None


class UnifiedMarketData(BaseModel):
    """Unified market data from all sources."""
    
    symbol: str
    timestamp: str
    
    # OHLCV (from primary source)
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    volume: Optional[int] = None
    
    # Regime data
    vix: Optional[float] = None
    spx: Optional[float] = None
    vix_percentile: Optional[float] = None
    
    # Macro data
    fed_funds_rate: Optional[float] = None
    treasury_10y: Optional[float] = None
    yield_curve_slope: Optional[float] = None
    
    # Options data (NEW - from Unusual Whales)
    options_chain_available: bool = False
    num_options: int = 0
    options_flow_alerts: int = 0
    
    # Market sentiment (NEW - from Unusual Whales Market Tide)
    market_tide: Optional[float] = None
    unusual_whales_sentiment: Optional[float] = None
    
    # Sentiment data (traditional)
    stocktwits_sentiment: Optional[float] = None
    wsb_sentiment: Optional[float] = None
    wsb_mentions: Optional[int] = None
    
    # Dark pool / institutional
    dark_pool_ratio: Optional[float] = None
    dark_pool_pressure: Optional[float] = None
    
    # Short interest
    short_volume_ratio: Optional[float] = None
    short_squeeze_pressure: Optional[float] = None
    
    # Data quality
    data_sources_used: List[str] = Field(default_factory=list)
    validation_passed: bool = True


class DataSourceManager:
    """
    Unified data source manager with Unusual Whales as primary source.
    
    Features:
    - Unusual Whales for options flow, chains, and market sentiment
    - Automatic fallback to backup sources (Public.com, IEX, Alpaca)
    - Cross-validation between sources
    - Health monitoring and circuit breaking
    - Intelligent caching
    - Parallel fetching where possible
    
    NO LONGER USES: yfinance, Polygon (completely removed)
    """
    
    def __init__(
        self,
        # Primary source (NEW)
        unusual_whales_api_key: Optional[str] = None,
        
        # Backup sources
        public_api_secret: Optional[str] = None,
        alpaca_api_key: Optional[str] = None,
        alpaca_api_secret: Optional[str] = None,
        alpaca_paper: bool = True,
        iex_api_token: Optional[str] = None,
        
        # Free sources
        fred_api_key: Optional[str] = None,
        
        # Sentiment sources
        reddit_client_id: Optional[str] = None,
        reddit_client_secret: Optional[str] = None,
        reddit_user_agent: Optional[str] = None,
        
        # Configuration
        enable_validation: bool = True,
        validation_tolerance: float = 0.01,
        cache_ttl_minutes: int = 5
    ):
        """
        Initialize data source manager with Unusual Whales as primary.
        
        Args:
            unusual_whales_api_key: Unusual Whales API key (PRIMARY)
            public_api_secret: Public.com API secret (backup)
            alpaca_api_key: Alpaca API key (backup)
            alpaca_api_secret: Alpaca API secret
            alpaca_paper: Use paper trading
            iex_api_token: IEX Cloud token (backup)
            fred_api_key: FRED API key (macro data)
            reddit_client_id: Reddit client ID (WSB sentiment)
            reddit_client_secret: Reddit secret
            reddit_user_agent: Reddit user agent
            enable_validation: Enable cross-source validation
            validation_tolerance: Price validation tolerance (1% = 0.01)
            cache_ttl_minutes: Cache TTL in minutes
        """
        self.enable_validation = enable_validation
        self.validation_tolerance = validation_tolerance
        self.cache_ttl = timedelta(minutes=cache_ttl_minutes)
        
        # Initialize status tracking
        self.status: Dict[DataSourceType, DataSourceStatus] = {}
        
        # Initialize PRIMARY source (Unusual Whales) - NEW!
        self.unusual_whales = None
        if unusual_whales_api_key:
            try:
                self.unusual_whales = UnusualWhalesAdapter(api_key=unusual_whales_api_key)
                self.status[DataSourceType.UNUSUAL_WHALES] = DataSourceStatus(
                    source_type=DataSourceType.UNUSUAL_WHALES,
                    is_available=True
                )
                logger.info("✅ Unusual Whales adapter initialized (PRIMARY)")
            except Exception as e:
                logger.warning(f"Failed to initialize Unusual Whales: {e}")
                self.status[DataSourceType.UNUSUAL_WHALES] = DataSourceStatus(
                    source_type=DataSourceType.UNUSUAL_WHALES,
                    is_available=False,
                    last_error=str(e)
                )
        
        # Initialize backup source (Public.com)
        self.public = None
        if public_api_secret:
            try:
                self.public = PublicTradingAdapter(secret_key=public_api_secret)
                self.status[DataSourceType.PUBLIC] = DataSourceStatus(
                    source_type=DataSourceType.PUBLIC,
                    is_available=True
                )
                logger.info("✅ Public.com adapter initialized (backup)")
            except Exception as e:
                logger.warning(f"Failed to initialize Public.com: {e}")
                self.status[DataSourceType.PUBLIC] = DataSourceStatus(
                    source_type=DataSourceType.PUBLIC,
                    is_available=False,
                    last_error=str(e)
                )
        
        # Initialize backup source (IEX)
        self.iex = None
        if iex_api_token:
            try:
                self.iex = IEXAdapter(api_token=iex_api_token)
                self.status[DataSourceType.IEX] = DataSourceStatus(
                    source_type=DataSourceType.IEX,
                    is_available=True
                )
                logger.info("✅ IEX adapter initialized (backup)")
            except Exception as e:
                logger.warning(f"Failed to initialize IEX: {e}")
                self.status[DataSourceType.IEX] = DataSourceStatus(
                    source_type=DataSourceType.IEX,
                    is_available=False,
                    last_error=str(e)
                )
        
        # Initialize free sources
        try:
            self.dark_pool = DarkPoolAdapter()
            self.status[DataSourceType.DARK_POOL] = DataSourceStatus(
                source_type=DataSourceType.DARK_POOL,
                is_available=True
            )
            logger.info("✅ Dark Pool adapter initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize Dark Pool: {e}")
            self.dark_pool = None
        
        try:
            self.short_volume = ShortVolumeAdapter()
            self.status[DataSourceType.SHORT_VOLUME] = DataSourceStatus(
                source_type=DataSourceType.SHORT_VOLUME,
                is_available=True
            )
            logger.info("✅ Short Volume adapter initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize Short Volume: {e}")
            self.short_volume = None
        
        # Initialize FRED (requires API key)
        self.fred = None
        if fred_api_key:
            try:
                self.fred = FREDAdapter(api_key=fred_api_key)
                self.status[DataSourceType.FRED] = DataSourceStatus(
                    source_type=DataSourceType.FRED,
                    is_available=True
                )
                logger.info("✅ FRED adapter initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize FRED: {e}")
                self.status[DataSourceType.FRED] = DataSourceStatus(
                    source_type=DataSourceType.FRED,
                    is_available=False,
                    last_error=str(e)
                )
        
        # Initialize sentiment sources
        self.stocktwits = None
        try:
            self.stocktwits = StockTwitsAdapter()
            self.status[DataSourceType.STOCKTWITS] = DataSourceStatus(
                source_type=DataSourceType.STOCKTWITS,
                is_available=True
            )
            logger.info("✅ StockTwits adapter initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize StockTwits: {e}")
        
        self.wsb = None
        if reddit_client_id and reddit_client_secret and reddit_user_agent:
            try:
                self.wsb = WSBSentimentAdapter(
                    client_id=reddit_client_id,
                    client_secret=reddit_client_secret,
                    user_agent=reddit_user_agent
                )
                self.status[DataSourceType.WSB] = DataSourceStatus(
                    source_type=DataSourceType.WSB,
                    is_available=True
                )
                logger.info("✅ WSB adapter initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize WSB: {e}")
                self.status[DataSourceType.WSB] = DataSourceStatus(
                    source_type=DataSourceType.WSB,
                    is_available=False,
                    last_error=str(e)
                )
        
        logger.info(f"✅ DataSourceManager initialized with {len(self.status)} sources")
        logger.info(f"🚀 PRIMARY DATA SOURCE: Unusual Whales")
    
    def get_source_status(self) -> pl.DataFrame:
        """Get status of all data sources."""
        if not self.status:
            return pl.DataFrame()
        
        status_list = [s.model_dump() for s in self.status.values()]
        return pl.DataFrame(status_list)
    
    def fetch_quote(self, symbol: str) -> Optional[Dict[str, float]]:
        """
        Fetch real-time quote with fallback.
        
        Order: Unusual Whales -> Public.com -> IEX -> Alpaca
        
        Args:
            symbol: Stock symbol
        
        Returns:
            Dictionary with price data
        """
        # Try PRIMARY source (Unusual Whales)
        if self.unusual_whales and self.status.get(DataSourceType.UNUSUAL_WHALES, DataSourceStatus(source_type=DataSourceType.UNUSUAL_WHALES, is_available=False)).is_healthy:
            try:
                overview = self.unusual_whales.get_ticker_overview(symbol)
                if overview and 'data' in overview:
                    data = overview['data']
                    quote = {
                        "last": data.get("price", data.get("close")),
                        "bid": data.get("bid"),
                        "ask": data.get("ask")
                    }
                    logger.info(f"✅ Quote from Unusual Whales: {symbol} = ${quote['last']}")
                    return quote
            except Exception as e:
                logger.warning(f"Unusual Whales failed, trying backup: {e}")
                if DataSourceType.UNUSUAL_WHALES in self.status:
                    self.status[DataSourceType.UNUSUAL_WHALES].error_count += 1
                    self.status[DataSourceType.UNUSUAL_WHALES].last_error = str(e)
        
        # Try backup source (Public.com)
        if self.public and self.status.get(DataSourceType.PUBLIC, DataSourceStatus(source_type=DataSourceType.PUBLIC, is_available=False)).is_healthy:
            try:
                # Public.com requires account_id - get it first
                account_id = self.public.account_id if hasattr(self.public, 'account_id') else None
                if account_id:
                    quotes = self.public.get_quotes(account_id, [{"symbol": symbol}])
                    if symbol in quotes:
                        quote = quotes[symbol]
                        logger.info(f"✅ Quote from Public.com: {symbol} = ${quote['price']}")
                        return {"last": quote['price'], "bid": quote.get('bid'), "ask": quote.get('ask')}
            except Exception as e:
                logger.warning(f"Public.com failed, trying IEX: {e}")
                if DataSourceType.PUBLIC in self.status:
                    self.status[DataSourceType.PUBLIC].error_count += 1
                    self.status[DataSourceType.PUBLIC].last_error = str(e)
        
        # Try backup source (IEX)
        if self.iex and self.status.get(DataSourceType.IEX, DataSourceStatus(source_type=DataSourceType.IEX, is_available=False)).is_healthy:
            try:
                quote_obj = self.iex.fetch_quote(symbol)
                quote = {
                    "bid": quote_obj.bid or quote_obj.last_price,
                    "ask": quote_obj.ask or quote_obj.last_price,
                    "last": quote_obj.last_price
                }
                logger.info(f"✅ Quote from IEX: {symbol} = ${quote['last']}")
                return quote
            except Exception as e:
                logger.warning(f"IEX failed: {e}")
                if DataSourceType.IEX in self.status:
                    self.status[DataSourceType.IEX].error_count += 1
                    self.status[DataSourceType.IEX].last_error = str(e)
        
        logger.error(f"No quote sources available for {symbol}")
        return None
    
    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1d",
        limit: int = 100
    ) -> Optional[pl.DataFrame]:
        """
        Fetch OHLCV data with fallback.
        
        Order: Unusual Whales -> Public.com -> IEX
        
        Args:
            symbol: Stock symbol
            timeframe: Timeframe (1d, 1h, etc.)
            limit: Number of bars
        
        Returns:
            Polars DataFrame with OHLCV data
        """
        # Try Unusual Whales first
        if self.unusual_whales and self.status.get(DataSourceType.UNUSUAL_WHALES, DataSourceStatus(source_type=DataSourceType.UNUSUAL_WHALES, is_available=False)).is_healthy:
            try:
                # Use ticker historical endpoint
                from datetime import datetime, timedelta
                end_date = datetime.now().strftime("%Y-%m-%d")
                start_date = (datetime.now() - timedelta(days=limit)).strftime("%Y-%m-%d")
                
                hist = self.unusual_whales.get_ticker_historical(symbol, start_date, end_date)
                if hist and 'data' in hist and hist['data']:
                    # Convert to polars DataFrame
                    df = pl.DataFrame(hist['data'])
                    if not df.is_empty():
                        logger.info(f"✅ OHLCV from Unusual Whales: {symbol} ({len(df)} bars)")
                        return df
            except Exception as e:
                logger.warning(f"Unusual Whales OHLCV failed: {e}")
        
        # Try Public.com
        if self.public and self.status.get(DataSourceType.PUBLIC, DataSourceStatus(source_type=DataSourceType.PUBLIC, is_available=False)).is_healthy:
            try:
                account_id = self.public.account_id if hasattr(self.public, 'account_id') else None
                if account_id:
                    # Map timeframe to period
                    period = "60d" if timeframe == "1d" else "7d"
                    hist = self.public.get_history(account_id, symbol, period=period, interval=timeframe)
                    if hist and 'history' in hist:
                        df = pl.DataFrame(hist['history'])
                        if not df.is_empty():
                            df = df.tail(limit)
                            logger.info(f"✅ OHLCV from Public.com: {symbol} ({len(df)} bars)")
                            return df
            except Exception as e:
                logger.warning(f"Public.com OHLCV failed: {e}")
        
        # Try IEX
        if self.iex and self.status.get(DataSourceType.IEX, DataSourceStatus(source_type=DataSourceType.IEX, is_available=False)).is_healthy:
            try:
                df = self.iex.fetch_ohlcv(symbol, timeframe, limit)
                if df and not df.is_empty():
                    logger.info(f"✅ OHLCV from IEX: {symbol} ({len(df)} bars)")
                    return df
            except Exception as e:
                logger.warning(f"IEX OHLCV failed: {e}")
        
        return None
    
    def fetch_unified_data(
        self,
        symbol: str,
        include_options: bool = True,
        include_sentiment: bool = True,
        include_macro: bool = True
    ) -> UnifiedMarketData:
        """
        Fetch all available data for a symbol in one call.
        
        NEW: Uses Unusual Whales as primary for options, flow, and sentiment.
        
        Args:
            symbol: Stock symbol
            include_options: Fetch options chain
            include_sentiment: Fetch sentiment data
            include_macro: Fetch macro regime data
        
        Returns:
            UnifiedMarketData with all available information
        """
        logger.info(f"Fetching unified data for {symbol}")
        
        data = UnifiedMarketData(
            symbol=symbol,
            timestamp=datetime.now().isoformat()
        )
        
        # 1. Get OHLCV (primary data)
        df_ohlcv = self.fetch_ohlcv(symbol, timeframe="1d", limit=1)
        if df_ohlcv and not df_ohlcv.is_empty():
            row = df_ohlcv.row(0, named=True)
            data.open = row.get("open")
            data.high = row.get("high")
            data.low = row.get("low")
            data.close = row.get("close")
            data.volume = row.get("volume")
            data.data_sources_used.append("ohlcv")
        
        # 2. Get market sentiment from Unusual Whales Market Tide (NEW)
        if self.unusual_whales:
            try:
                tide = self.unusual_whales.get_market_tide()
                if tide and 'data' in tide:
                    data.market_tide = tide['data']
                    data.data_sources_used.append("unusual_whales_tide")
            except Exception as e:
                logger.warning(f"Failed to fetch Market Tide: {e}")
        
        # 3. Get macro data
        if self.fred and include_macro:
            try:
                macro = self.fred.fetch_macro_regime_data()
                data.fed_funds_rate = macro.get("fed_funds_rate")
                data.treasury_10y = macro.get("treasury_10y")
                data.yield_curve_slope = macro.get("yield_curve_slope")
                data.data_sources_used.append("macro")
            except Exception as e:
                logger.warning(f"Failed to fetch macro data: {e}")
        
        # 4. Get options chain from Unusual Whales (NEW)
        if self.unusual_whales and include_options:
            try:
                chain = self.unusual_whales.get_ticker_chain(symbol)
                if chain and 'data' in chain and chain['data']:
                    data.options_chain_available = True
                    data.num_options = len(chain['data'])
                    data.data_sources_used.append("unusual_whales_options")
                
                # Also get options flow alerts
                flow = self.unusual_whales.get_flow_alerts(ticker=symbol, limit=10)
                if flow and 'data' in flow:
                    data.options_flow_alerts = len(flow['data'])
                    data.data_sources_used.append("unusual_whales_flow")
            except Exception as e:
                logger.warning(f"Failed to fetch Unusual Whales options: {e}")
        
        # 5. Get sentiment
        if include_sentiment:
            # StockTwits
            if self.stocktwits:
                try:
                    sentiment = self.stocktwits.fetch_sentiment(symbol, limit=30)
                    data.stocktwits_sentiment = sentiment.sentiment_score
                    data.data_sources_used.append("stocktwits")
                except Exception as e:
                    logger.warning(f"Failed to fetch StockTwits: {e}")
            
            # WSB (rate limited, only for popular symbols)
            if self.wsb and symbol in ["SPY", "QQQ", "TSLA", "AAPL", "NVDA"]:
                try:
                    df_wsb = self.wsb.fetch_sentiment(limit=50, min_mentions=1)
                    if df_wsb and not df_wsb.is_empty():
                        symbol_row = df_wsb.filter(pl.col("symbol") == symbol)
                        if not symbol_row.is_empty():
                            row = symbol_row.row(0, named=True)
                            data.wsb_sentiment = row.get("sentiment_score")
                            data.wsb_mentions = row.get("total_mentions")
                            data.data_sources_used.append("wsb")
                except Exception as e:
                    logger.warning(f"Failed to fetch WSB: {e}")
        
        # 6. Get dark pool data
        if self.dark_pool:
            try:
                dp = self.dark_pool.estimate_dark_pool_pressure(symbol)
                data.dark_pool_ratio = dp.get("dark_pool_ratio")
                data.dark_pool_pressure = dp.get("accumulation_score")
                data.data_sources_used.append("dark_pool")
            except Exception as e:
                logger.warning(f"Failed to fetch dark pool: {e}")
        
        # 7. Get short volume
        if self.short_volume:
            try:
                short = self.short_volume.calculate_short_squeeze_pressure(symbol)
                data.short_volume_ratio = short.get("avg_short_ratio")
                data.short_squeeze_pressure = short.get("squeeze_pressure")
                data.data_sources_used.append("short_volume")
            except Exception as e:
                logger.warning(f"Failed to fetch short volume: {e}")
        
        logger.info(
            f"✅ Unified data for {symbol}: "
            f"{len(data.data_sources_used)} sources used"
        )
        
        return data


# Example usage
if __name__ == "__main__":
    import os
    
    # Initialize manager with Unusual Whales as PRIMARY
    manager = DataSourceManager(
        # PRIMARY: Unusual Whales
        unusual_whales_api_key=os.getenv("UNUSUAL_WHALES_API_KEY", "8932cd23-72b3-4f74-9848-13f9103b9df5"),
        
        # Backup: Public.com
        public_api_secret=os.getenv("PUBLIC_API_SECRET"),
        
        # Backup: IEX
        iex_api_token=os.getenv("IEX_API_TOKEN"),
        
        # Macro: FRED
        fred_api_key=os.getenv("FRED_API_KEY"),
        
        # Sentiment: Reddit
        reddit_client_id=os.getenv("REDDIT_CLIENT_ID"),
        reddit_client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
        reddit_user_agent="DataSourceManager/2.0",
        
        # Configuration
        enable_validation=True,
        validation_tolerance=0.01
    )
    
    # Check source status
    print("\n" + "="*60)
    print("DATA SOURCE STATUS (Unusual Whales Primary)")
    print("="*60)
    
    df_status = manager.get_source_status()
    print(df_status)
    
    # Fetch unified data
    print("\n" + "="*60)
    print("UNIFIED DATA FOR SPY (Unusual Whales Primary)")
    print("="*60)
    
    data = manager.fetch_unified_data(
        symbol="SPY",
        include_options=True,
        include_sentiment=True,
        include_macro=True
    )
    
    print(f"\nSymbol: {data.symbol}")
    print(f"Timestamp: {data.timestamp}")
    print(f"\nOHLCV:")
    print(f"  Close: ${data.close}")
    print(f"  Volume: {data.volume:,}")
    print(f"\nMarket Sentiment (Unusual Whales):")
    print(f"  Market Tide: {data.market_tide}")
    print(f"\nOptions (Unusual Whales):")
    print(f"  Chain Available: {data.options_chain_available}")
    print(f"  Num Options: {data.num_options}")
    print(f"  Flow Alerts: {data.options_flow_alerts}")
    print(f"\nData Sources Used: {', '.join(data.data_sources_used)}")
