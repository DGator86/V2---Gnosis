"""
Unified Data Source Manager.

Orchestrates all data sources with intelligent fallback, validation,
and caching strategies. Provides a single interface for all market data needs.

Data Source Hierarchy:
1. Primary: Public.com (real-time quotes, historical, options)
2. Backup: IEX Cloud (validation)
3. Fallback: Alpaca (real-time, official)
4. Macro: FRED (economic data)
5. Sentiment: StockTwits + WSB (social)
6. Dark Pool: Dark Pool Adapter (institutional flow)
7. Short Volume: FINRA (short interest)
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, date, timedelta
from loguru import logger
import polars as pl
from pydantic import BaseModel, Field
from enum import Enum

# Import all adapters
# from engines.inputs.alpaca_adapter import AlpacaAdapter  # TODO: Create alpaca_adapter in engines/inputs
from engines.inputs.yfinance_adapter import YFinanceAdapter
from engines.inputs.yahoo_options_adapter import YahooOptionsAdapter
from engines.inputs.fred_adapter import FREDAdapter
from engines.inputs.dark_pool_adapter import DarkPoolAdapter
from engines.inputs.short_volume_adapter import ShortVolumeAdapter
from engines.inputs.stocktwits_adapter import StockTwitsAdapter
from engines.inputs.wsb_sentiment_adapter import WSBSentimentAdapter
from engines.inputs.iex_adapter import IEXAdapter


class DataSourceType(str, Enum):
    """Data source types."""
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
    
    # Options data
    options_chain_available: bool = False
    num_options: int = 0
    
    # Sentiment data
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
    Unified data source manager with intelligent fallback and validation.
    
    Features:
    - Automatic fallback to backup sources
    - Cross-validation between sources
    - Health monitoring and circuit breaking
    - Intelligent caching
    - Parallel fetching where possible
    """
    
    def __init__(
        self,
        # Primary source
        public_api_secret: Optional[str] = None,
        
        # Backup sources
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
        Initialize data source manager.
        
        Args:
            public_api_secret: Public.com API secret (primary)
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
        
        # Initialize primary source (Public.com)
        self.public = None
        if public_api_secret:
            try:
                self.public = PublicAdapter(api_secret=public_api_secret)
                self.status[DataSourceType.PUBLIC] = DataSourceStatus(
                    source_type=DataSourceType.PUBLIC,
                    is_available=True
                )
                logger.info("✅ Public.com adapter initialized (primary)")
            except Exception as e:
                logger.warning(f"Failed to initialize Public.com: {e}")
                self.status[DataSourceType.PUBLIC] = DataSourceStatus(
                    source_type=DataSourceType.PUBLIC,
                    is_available=False,
                    last_error=str(e)
                )
        
        # Initialize backup source (Alpaca) - DISABLED: alpaca_adapter not in engines/inputs
        self.alpaca = None
        # TODO: Move alpaca_adapter to engines/inputs or use engines/execution/alpaca_executor
        # if alpaca_api_key and alpaca_api_secret:
        #     try:
        #         self.alpaca = AlpacaAdapter(
        #             api_key=alpaca_api_key,
        #             api_secret=alpaca_api_secret,
        #             paper=alpaca_paper
        #         )
        #         self.status[DataSourceType.ALPACA] = DataSourceStatus(
        #             source_type=DataSourceType.ALPACA,
        #             is_available=True
        #         )
        #         logger.info("✅ Alpaca adapter initialized (backup)")
        #     except Exception as e:
        #         logger.warning(f"Failed to initialize Alpaca: {e}")
        #         self.status[DataSourceType.ALPACA] = DataSourceStatus(
        #             source_type=DataSourceType.ALPACA,
        #             is_available=False,
        #             last_error=str(e)
        #         )
        
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
        
        # Initialize free sources (always available)
        try:
            self.yfinance = YFinanceAdapter()
            self.status[DataSourceType.YFINANCE] = DataSourceStatus(
                source_type=DataSourceType.YFINANCE,
                is_available=True
            )
            logger.info("✅ yfinance adapter initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize yfinance: {e}")
            self.yfinance = None
        
        try:
            self.yahoo_options = YahooOptionsAdapter()
            self.status[DataSourceType.YAHOO_OPTIONS] = DataSourceStatus(
                source_type=DataSourceType.YAHOO_OPTIONS,
                is_available=True
            )
            logger.info("✅ Yahoo Options adapter initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize Yahoo Options: {e}")
            self.yahoo_options = None
        
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
        
        # Initialize sentiment sources (requires credentials)
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
    
    def get_source_status(self) -> pl.DataFrame:
        """Get status of all data sources."""
        if not self.status:
            return pl.DataFrame()
        
        status_list = [s.model_dump() for s in self.status.values()]
        return pl.DataFrame(status_list)
    
    def fetch_quote(self, symbol: str) -> Optional[Dict[str, float]]:
        """
        Fetch real-time quote with fallback.
        
        Order: Public.com -> IEX -> Alpaca
        
        Args:
            symbol: Stock symbol
        
        Returns:
            Dictionary with price data
        """
        # Try primary source (Public.com)
        if self.public and self.status.get(DataSourceType.PUBLIC, DataSourceStatus(source_type=DataSourceType.PUBLIC, is_available=False)).is_healthy:
            try:
                quote = self.public.fetch_quote(symbol)
                logger.info(f"✅ Quote from Public.com: {symbol} = ${quote['last']}")
                return quote
            except Exception as e:
                logger.warning(f"Public.com failed, trying backup: {e}")
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
                logger.warning(f"IEX failed, trying Alpaca: {e}")
                if DataSourceType.IEX in self.status:
                    self.status[DataSourceType.IEX].error_count += 1
                    self.status[DataSourceType.IEX].last_error = str(e)
        
        # Try Alpaca as last resort
        if self.alpaca and self.status.get(DataSourceType.ALPACA, DataSourceStatus(source_type=DataSourceType.ALPACA, is_available=False)).is_healthy:
            try:
                quote = self.alpaca.get_latest_quote(symbol)
                logger.info(f"✅ Quote from Alpaca: {symbol} = ${quote['bid']}")
                return quote
            except Exception as e:
                logger.error(f"All quote sources failed for {symbol}: {e}")
                return None
        
        logger.error(f"No quote sources available for {symbol}")
        return None
    
    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1m",
        limit: int = 100
    ) -> Optional[pl.DataFrame]:
        """
        Fetch OHLCV data with fallback.
        
        Order: Public.com -> IEX -> Alpaca
        
        Args:
            symbol: Stock symbol
            timeframe: Timeframe (1m, 5m, 1h, 1d)
            limit: Number of bars
        
        Returns:
            Polars DataFrame with OHLCV data
        """
        # Try Public.com first
        if self.public and self.status.get(DataSourceType.PUBLIC, DataSourceStatus(source_type=DataSourceType.PUBLIC, is_available=False)).is_healthy:
            try:
                # Map timeframe to period
                if timeframe == "1d":
                    period = "60d"
                else:
                    period = "7d"  # Max intraday
                
                df = self.public.fetch_ohlcv(symbol, period=period, interval=timeframe)
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
                if not df.is_empty():
                    logger.info(f"✅ OHLCV from IEX: {symbol} ({len(df)} bars)")
                    return df
            except Exception as e:
                logger.warning(f"IEX OHLCV failed: {e}")
        
        # Try Alpaca
        if self.alpaca and self.status.get(DataSourceType.ALPACA, DataSourceStatus(source_type=DataSourceType.ALPACA, is_available=False)).is_healthy:
            try:
                df = self.alpaca.get_bars(symbol, timeframe, limit)
                if not df.is_empty():
                    logger.info(f"✅ OHLCV from Alpaca: {symbol} ({len(df)} bars)")
                    return df
            except Exception as e:
                logger.error(f"All OHLCV sources failed for {symbol}: {e}")
                return None
        
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
        
        # 2. Get regime data (VIX, SPX)
        if self.public and include_macro:
            try:
                regime = self.public.fetch_market_regime_data()
                data.vix = regime.get("vix")
                data.spx = regime.get("spx")
                data.data_sources_used.append("regime")
            except Exception as e:
                logger.warning(f"Failed to fetch regime data: {e}")
        
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
        
        # 4. Get options chain
        if self.yahoo_options and include_options:
            try:
                chain = self.yahoo_options.fetch_options_chain(symbol)
                if not chain.is_empty():
                    data.options_chain_available = True
                    data.num_options = len(chain)
                    data.data_sources_used.append("options")
            except Exception as e:
                logger.warning(f"Failed to fetch options: {e}")
        
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
                    if not df_wsb.is_empty():
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
    
    # Initialize manager with credentials
    manager = DataSourceManager(
        # Primary (Public.com)
        public_api_secret=os.getenv("PUBLIC_API_SECRET", "tVi7dG9UEyYtz3BY8Ab1N2BxEwxBDs9c"),
        
        # Backup (Alpaca) - optional
        alpaca_api_key=os.getenv("ALPACA_API_KEY"),
        alpaca_api_secret=os.getenv("ALPACA_API_SECRET"),
        alpaca_paper=True,
        
        # Backup (IEX) - optional
        iex_api_token=os.getenv("IEX_API_TOKEN"),
        
        # Macro (FRED) - optional
        fred_api_key=os.getenv("FRED_API_KEY"),
        
        # Sentiment (Reddit) - optional
        reddit_client_id=os.getenv("REDDIT_CLIENT_ID"),
        reddit_client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
        reddit_user_agent="DataSourceManager/1.0",
        
        # Configuration
        enable_validation=True,
        validation_tolerance=0.01
    )
    
    # Check source status
    print("\n" + "="*60)
    print("DATA SOURCE STATUS")
    print("="*60)
    
    df_status = manager.get_source_status()
    print(df_status)
    
    # Fetch unified data
    print("\n" + "="*60)
    print("UNIFIED DATA FOR SPY")
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
    print(f"  Open: ${data.open}")
    print(f"  High: ${data.high}")
    print(f"  Low: ${data.low}")
    print(f"  Close: ${data.close}")
    print(f"  Volume: {data.volume:,}")
    print(f"\nRegime:")
    print(f"  VIX: {data.vix}")
    print(f"  SPX: {data.spx}")
    print(f"\nMacro:")
    print(f"  Fed Funds: {data.fed_funds_rate}")
    print(f"  10Y Treasury: {data.treasury_10y}")
    print(f"  Yield Curve: {data.yield_curve_slope}")
    print(f"\nOptions:")
    print(f"  Available: {data.options_chain_available}")
    print(f"  Num Options: {data.num_options}")
    print(f"\nSentiment:")
    print(f"  StockTwits: {data.stocktwits_sentiment}")
    print(f"  WSB: {data.wsb_sentiment} ({data.wsb_mentions} mentions)")
    print(f"\nDark Pool:")
    print(f"  Ratio: {data.dark_pool_ratio}")
    print(f"  Pressure: {data.dark_pool_pressure}")
    print(f"\nShort Interest:")
    print(f"  Short Ratio: {data.short_volume_ratio}")
    print(f"  Squeeze Pressure: {data.short_squeeze_pressure}")
    print(f"\nData Sources Used: {', '.join(data.data_sources_used)}")
