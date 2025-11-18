"""Public.com API adapter for market data.

Public.com provides real-time quotes, historical bars, and options data
with no commissions and robust API access.

API Documentation: https://public.com/api/docs
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import polars as pl
from loguru import logger
import httpx
from enum import Enum


class PublicInstrumentType(str, Enum):
    """Instrument types supported by Public.com API."""
    EQUITY = "EQUITY"
    OPTION = "OPTION"
    INDEX = "INDEX"


class PublicTimeframe(str, Enum):
    """Timeframe intervals for historical data."""
    ONE_MINUTE = "1m"
    FIVE_MINUTE = "5m"
    FIFTEEN_MINUTE = "15m"
    THIRTY_MINUTE = "30m"
    ONE_HOUR = "1h"
    FOUR_HOUR = "4h"
    ONE_DAY = "1d"
    ONE_WEEK = "1w"
    ONE_MONTH = "1M"


class PublicAdapter:
    """Adapter for Public.com market data API.
    
    Features:
    - Real-time quotes for stocks and options
    - Historical OHLCV data
    - Options chain data
    - Multi-instrument batch requests
    - No commission trading
    
    Requires:
    - API Secret Key (for authentication)
    - marketdata scope for quotes and historical data
    
    Rate Limits:
    - Consult Public.com API documentation for current limits
    """
    
    BASE_URL = "https://api.public.com"
    
    # Symbol mappings for indices
    VIX_SYMBOL = "^VIX"
    SPX_SYMBOL = "^SPX"  # S&P 500 Index
    SPY_SYMBOL = "SPY"   # S&P 500 ETF (more liquid alternative)
    
    def __init__(self, api_secret: str, timeout: int = 30):
        """Initialize Public.com adapter.
        
        Args:
            api_secret: API Secret Key from Public.com
            timeout: Request timeout in seconds (default: 30)
        """
        if not api_secret:
            raise ValueError("API secret is required")
        
        self.api_secret = api_secret
        self.timeout = timeout
        self.access_token = None
        self.token_expires_at = None
        
        # Initialize HTTP client (will set auth after getting access token)
        self.client = httpx.Client(
            base_url=self.BASE_URL,
            headers={
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )
        
        # Exchange secret for access token
        self._get_access_token()
        
        logger.info("PublicAdapter initialized with API authentication")
    
    def __del__(self):
        """Clean up HTTP client."""
        if hasattr(self, 'client'):
            self.client.close()
    
    def _get_access_token(self) -> str:
        """Exchange API secret for access token.
        
        Returns:
            Access token string
        
        Raises:
            httpx.HTTPError: If token exchange fails
        """
        try:
            # Check if we have a valid cached token
            if self.access_token and self.token_expires_at:
                if datetime.now() < self.token_expires_at:
                    return self.access_token
            
            # Exchange secret for access token
            # Note: validityInMinutes is optional (default: 60 minutes)
            response = self.client.post(
                "/userapiauthservice/personal/access-tokens",
                json={
                    "secret": self.api_secret,
                    "validityInMinutes": 60  # Request 60-minute token
                }
            )
            
            # Log response for debugging
            if response.status_code != 200:
                logger.error(f"Token exchange failed: {response.status_code} - {response.text}")
            
            response.raise_for_status()
            
            # Parse response (Public.com uses camelCase: accessToken)
            data = response.json()
            self.access_token = data.get("accessToken")
            
            if not self.access_token:
                raise ValueError(f"No accessToken in response: {data}")
            
            # Calculate expiration time (60 minutes with 5 minute buffer)
            validity_minutes = 60
            self.token_expires_at = datetime.now() + timedelta(minutes=validity_minutes - 5)
            
            # Update client headers with new token
            self.client.headers["Authorization"] = f"Bearer {self.access_token}"
            
            logger.debug("Access token obtained successfully")
            return self.access_token
            
        except httpx.HTTPError as e:
            logger.error(f"Failed to get access token: {e}")
            raise
    
    def _ensure_authenticated(self):
        """Ensure we have a valid access token, refresh if needed."""
        if not self.access_token or (self.token_expires_at and datetime.now() >= self.token_expires_at):
            self._get_access_token()
    
    def fetch_quotes(
        self,
        symbols: List[str],
        instrument_type: PublicInstrumentType = PublicInstrumentType.EQUITY
    ) -> Dict[str, Dict[str, Any]]:
        """Fetch real-time quotes for multiple symbols.
        
        Args:
            symbols: List of symbols (e.g., ["SPY", "AAPL", "TSLA"])
            instrument_type: Type of instruments (EQUITY, OPTION, INDEX)
        
        Returns:
            Dictionary mapping symbols to quote data:
            {
                "SPY": {
                    "symbol": "SPY",
                    "bid": 450.25,
                    "ask": 450.30,
                    "last": 450.27,
                    "bid_size": 100,
                    "ask_size": 200,
                    "last_size": 50,
                    "volume": 12345678,
                    "timestamp": "2025-11-18T15:30:00Z"
                },
                ...
            }
        
        Raises:
            httpx.HTTPError: If API request fails
        """
        try:
            # Ensure we have a valid access token
            self._ensure_authenticated()
            
            # Prepare request payload
            payload = {
                "symbols": symbols,
                "instrument_type": instrument_type.value
            }
            
            # Make API request
            response = self.client.post(
                "/market-data/quotes",
                json=payload
            )
            response.raise_for_status()
            
            # Parse response
            data = response.json()
            
            # Transform to standardized format
            quotes = {}
            for quote in data.get("data", []):
                symbol = quote.get("symbol")
                quotes[symbol] = {
                    "symbol": symbol,
                    "bid": quote.get("bidPrice", 0.0),
                    "ask": quote.get("askPrice", 0.0),
                    "last": quote.get("lastPrice", 0.0),
                    "bid_size": quote.get("bidSize", 0),
                    "ask_size": quote.get("askSize", 0),
                    "last_size": quote.get("lastSize", 0),
                    "volume": quote.get("volume", 0),
                    "timestamp": quote.get("timestamp", datetime.now().isoformat()),
                }
            
            logger.debug(f"Fetched quotes for {len(quotes)} symbols")
            return quotes
            
        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch quotes: {e}")
            raise
    
    def fetch_quote(self, symbol: str) -> Dict[str, Any]:
        """Fetch quote for a single symbol.
        
        Args:
            symbol: Stock symbol (e.g., "SPY")
        
        Returns:
            Quote data dictionary
        """
        quotes = self.fetch_quotes([symbol])
        if symbol in quotes:
            return quotes[symbol]
        else:
            raise ValueError(f"No quote data returned for {symbol}")
    
    def fetch_vix(self) -> float:
        """Fetch current VIX value.
        
        Returns:
            Current VIX value (float)
        
        Raises:
            ValueError: If VIX data cannot be fetched
        """
        try:
            quotes = self.fetch_quotes([self.VIX_SYMBOL], PublicInstrumentType.INDEX)
            vix_value = quotes[self.VIX_SYMBOL]["last"]
            logger.debug(f"VIX fetched: {vix_value:.2f}")
            return vix_value
        except Exception as e:
            logger.error(f"Failed to fetch VIX: {e}")
            raise ValueError(f"VIX fetch failed: {e}")
    
    def fetch_spx(self, use_etf: bool = True) -> float:
        """Fetch current SPX value.
        
        Args:
            use_etf: If True, use SPY ETF (more reliable). If False, use ^SPX index.
        
        Returns:
            Current SPX value (float)
        
        Raises:
            ValueError: If SPX data cannot be fetched
        """
        symbol = self.SPY_SYMBOL if use_etf else self.SPX_SYMBOL
        instrument_type = PublicInstrumentType.EQUITY if use_etf else PublicInstrumentType.INDEX
        
        try:
            quotes = self.fetch_quotes([symbol], instrument_type)
            spx_value = quotes[symbol]["last"]
            logger.debug(f"SPX fetched ({symbol}): {spx_value:.2f}")
            return spx_value
        except Exception as e:
            logger.error(f"Failed to fetch SPX from {symbol}: {e}")
            raise ValueError(f"SPX fetch failed: {e}")
    
    def fetch_historical_bars(
        self,
        symbol: str,
        timeframe: PublicTimeframe = PublicTimeframe.FIVE_MINUTE,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> pl.DataFrame:
        """Fetch historical OHLCV bars.
        
        Args:
            symbol: Stock symbol (e.g., "SPY", "AAPL")
            timeframe: Bar timeframe (1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w, 1M)
            start_date: Start date (default: 30 days ago)
            end_date: End date (default: now)
            limit: Maximum number of bars to return
        
        Returns:
            Polars DataFrame with columns: timestamp, open, high, low, close, volume
        
        Note:
            - Intraday data (< 1d) may have limited history
            - Daily and weekly data available for longer periods
        """
        try:
            # Set default date range
            if end_date is None:
                end_date = datetime.now()
            if start_date is None:
                start_date = end_date - timedelta(days=30)
            
            # Prepare request payload
            payload = {
                "symbol": symbol,
                "timeframe": timeframe.value,
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
                "limit": limit
            }
            
            # Make API request
            response = self.client.post(
                "/market-data/historical/bars",
                json=payload
            )
            response.raise_for_status()
            
            # Parse response
            data = response.json()
            bars = data.get("data", [])
            
            if not bars:
                raise ValueError(f"No data returned for {symbol}")
            
            # Convert to Polars DataFrame
            df = pl.DataFrame({
                "timestamp": [bar["timestamp"] for bar in bars],
                "open": [bar["open"] for bar in bars],
                "high": [bar["high"] for bar in bars],
                "low": [bar["low"] for bar in bars],
                "close": [bar["close"] for bar in bars],
                "volume": [bar["volume"] for bar in bars],
            })
            
            # Parse timestamp
            df = df.with_columns([
                pl.col("timestamp").str.strptime(pl.Datetime, "%Y-%m-%dT%H:%M:%S%z").alias("timestamp")
            ])
            
            logger.info(
                f"Fetched {len(df)} bars for {symbol} "
                f"(timeframe={timeframe.value}, range={start_date.date()} to {end_date.date()})"
            )
            
            return df
            
        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch historical bars for {symbol}: {e}")
            raise ValueError(f"Historical bars fetch failed for {symbol}: {e}")
    
    def fetch_ohlcv(
        self,
        symbol: str,
        period: str = "1mo",
        interval: str = "5m",
    ) -> pl.DataFrame:
        """Fetch OHLCV data (compatible with yfinance interface).
        
        Args:
            symbol: Stock symbol (e.g., "SPY", "AAPL")
            period: Time period ("1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y")
            interval: Data interval ("1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w", "1M")
        
        Returns:
            Polars DataFrame with columns: timestamp, open, high, low, close, volume
        """
        # Map period to date range
        period_map = {
            "1d": 1,
            "5d": 5,
            "1mo": 30,
            "3mo": 90,
            "6mo": 180,
            "1y": 365,
            "2y": 730,
            "5y": 1825,
            "10y": 3650,
        }
        days = period_map.get(period, 30)
        
        # Map interval to timeframe
        interval_map = {
            "1m": PublicTimeframe.ONE_MINUTE,
            "5m": PublicTimeframe.FIVE_MINUTE,
            "15m": PublicTimeframe.FIFTEEN_MINUTE,
            "30m": PublicTimeframe.THIRTY_MINUTE,
            "1h": PublicTimeframe.ONE_HOUR,
            "4h": PublicTimeframe.FOUR_HOUR,
            "1d": PublicTimeframe.ONE_DAY,
            "1w": PublicTimeframe.ONE_WEEK,
            "1M": PublicTimeframe.ONE_MONTH,
        }
        timeframe = interval_map.get(interval, PublicTimeframe.FIVE_MINUTE)
        
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # Fetch bars
        return self.fetch_historical_bars(
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            limit=5000  # Public.com typically allows large limits
        )
    
    def fetch_spx_history(
        self,
        period: str = "1mo",
        interval: str = "5m",
        use_etf: bool = True,
    ) -> pl.DataFrame:
        """Fetch historical SPX data for realized volatility calculation.
        
        Args:
            period: Time period
            interval: Data interval
            use_etf: Use SPY ETF instead of ^SPX index
        
        Returns:
            Polars DataFrame with SPX historical data
        """
        symbol = self.SPY_SYMBOL if use_etf else self.SPX_SYMBOL
        return self.fetch_ohlcv(symbol, period=period, interval=interval)
    
    def fetch_vix_history(
        self,
        period: str = "1mo",
        interval: str = "5m",
    ) -> pl.DataFrame:
        """Fetch historical VIX data.
        
        Args:
            period: Time period
            interval: Data interval
        
        Returns:
            Polars DataFrame with VIX historical data
        """
        return self.fetch_ohlcv(self.VIX_SYMBOL, period=period, interval=interval)
    
    def fetch_market_regime_data(self) -> dict:
        """Fetch all market regime data in one call.
        
        Returns:
            Dictionary with:
            - vix: Current VIX value
            - spx: Current SPX value
            - vix_history: VIX historical data (for regime classification)
            - spx_history: SPX historical data (for realized vol)
        """
        try:
            # Fetch current values
            vix = self.fetch_vix()
            spx = self.fetch_spx()
            
            # Fetch historical data (last 60 days, 5-minute bars)
            vix_history = self.fetch_vix_history(period="60d", interval="5m")
            spx_history = self.fetch_spx_history(period="60d", interval="5m")
            
            return {
                "vix": vix,
                "spx": spx,
                "vix_history": vix_history,
                "spx_history": spx_history,
            }
            
        except Exception as e:
            logger.error(f"Failed to fetch market regime data: {e}")
            raise
    
    def fetch_options_chain(
        self,
        symbol: str,
        expiry_date: Optional[str] = None,
        min_days_to_expiry: int = 7,
        max_days_to_expiry: int = 60,
    ) -> pl.DataFrame:
        """Fetch options chain from Public.com.
        
        Args:
            symbol: Stock symbol (e.g., "SPY", "AAPL")
            expiry_date: Specific expiry date (YYYY-MM-DD) or None for auto-select
            min_days_to_expiry: Minimum days to expiry for auto-select
            max_days_to_expiry: Maximum days to expiry for auto-select
        
        Returns:
            Polars DataFrame with options chain data including Greeks
        """
        try:
            # Prepare request payload
            payload = {
                "symbol": symbol,
                "instrument_type": PublicInstrumentType.OPTION.value
            }
            
            if expiry_date:
                payload["expiry_date"] = expiry_date
            else:
                payload["min_days_to_expiry"] = min_days_to_expiry
                payload["max_days_to_expiry"] = max_days_to_expiry
            
            # Make API request
            response = self.client.post(
                "/market-data/options/chain",
                json=payload
            )
            response.raise_for_status()
            
            # Parse response
            data = response.json()
            options = data.get("data", [])
            
            if not options:
                raise ValueError(f"No options available for {symbol}")
            
            # Convert to Polars DataFrame
            rows = []
            for opt in options:
                rows.append({
                    "symbol": symbol,
                    "strike": opt["strike"],
                    "expiry": opt["expiry_date"],
                    "option_type": opt["option_type"].lower(),  # "call" or "put"
                    "bid": opt.get("bid", 0.0),
                    "ask": opt.get("ask", 0.0),
                    "last_price": opt.get("last_price", 0.0),
                    "volume": opt.get("volume", 0),
                    "open_interest": opt.get("open_interest", 0),
                    "implied_volatility": opt.get("implied_volatility", 0.0),
                    # Greeks
                    "delta": opt.get("delta", 0.0),
                    "gamma": opt.get("gamma", 0.0),
                    "theta": opt.get("theta", 0.0),
                    "vega": opt.get("vega", 0.0),
                    "vanna": opt.get("vanna", 0.0),
                    "charm": opt.get("charm", 0.0),
                })
            
            df = pl.DataFrame(rows)
            
            logger.info(
                f"Fetched {len(df)} options for {symbol}"
            )
            
            return df
            
        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch options chain for {symbol}: {e}")
            raise ValueError(f"Options chain fetch failed for {symbol}: {e}")
    
    def test_connection(self) -> bool:
        """Test connection to Public.com API.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Try to fetch SPY quote (most reliable symbol)
            quote = self.fetch_quote("SPY")
            
            if not quote or "last" not in quote:
                logger.error("Public.com API test failed: No data returned")
                return False
            
            logger.info(f"Public.com API connection test: SUCCESS (SPY @ ${quote['last']:.2f})")
            return True
            
        except Exception as e:
            logger.error(f"Public.com API connection test failed: {e}")
            return False


# Convenience functions

def get_vix(api_secret: str) -> float:
    """Get current VIX value.
    
    Args:
        api_secret: Public.com API secret
    
    Returns:
        Current VIX value
    """
    adapter = PublicAdapter(api_secret)
    return adapter.fetch_vix()


def get_spx(api_secret: str) -> float:
    """Get current SPX value.
    
    Args:
        api_secret: Public.com API secret
    
    Returns:
        Current SPX value (via SPY ETF)
    """
    adapter = PublicAdapter(api_secret)
    return adapter.fetch_spx(use_etf=True)


def get_market_regime_data(api_secret: str) -> dict:
    """Get all market regime data.
    
    Args:
        api_secret: Public.com API secret
    
    Returns:
        Dictionary with vix, spx, and historical data
    """
    adapter = PublicAdapter(api_secret)
    return adapter.fetch_market_regime_data()


def get_ohlcv(api_secret: str, symbol: str, period: str = "1mo", interval: str = "5m") -> pl.DataFrame:
    """Get OHLCV data for a symbol.
    
    Args:
        api_secret: Public.com API secret
        symbol: Stock symbol
        period: Time period
        interval: Data interval
    
    Returns:
        Polars DataFrame with OHLCV data
    """
    adapter = PublicAdapter(api_secret)
    return adapter.fetch_ohlcv(symbol, period=period, interval=interval)


def get_options_chain(api_secret: str, symbol: str) -> pl.DataFrame:
    """Get options chain for a symbol.
    
    Args:
        api_secret: Public.com API secret
        symbol: Stock symbol
    
    Returns:
        Polars DataFrame with options chain and Greeks
    """
    adapter = PublicAdapter(api_secret)
    return adapter.fetch_options_chain(symbol)


# Example usage
if __name__ == "__main__":
    import os
    
    # Get API secret from environment or use provided key
    api_secret = os.getenv("PUBLIC_API_SECRET", "tVi7dG9UEyYtz3BY8Ab1N2BxEwxBDs9c")
    
    # Test adapter
    adapter = PublicAdapter(api_secret)
    
    print("Testing Public.com adapter...")
    
    # Test connection
    if adapter.test_connection():
        print("✅ Connection successful")
    else:
        print("❌ Connection failed")
        exit(1)
    
    # Fetch VIX
    try:
        vix = adapter.fetch_vix()
        print(f"✅ VIX: {vix:.2f}")
    except Exception as e:
        print(f"❌ VIX fetch failed: {e}")
    
    # Fetch SPX
    try:
        spx = adapter.fetch_spx()
        print(f"✅ SPX: {spx:.2f}")
    except Exception as e:
        print(f"❌ SPX fetch failed: {e}")
    
    # Fetch SPY OHLCV
    try:
        df = adapter.fetch_ohlcv("SPY", period="1d", interval="5m")
        print(f"✅ SPY OHLCV: {len(df)} bars fetched")
        print(df.head())
    except Exception as e:
        print(f"❌ SPY OHLCV fetch failed: {e}")
    
    # Fetch market regime data
    try:
        regime_data = adapter.fetch_market_regime_data()
        print(f"✅ Market regime data fetched:")
        print(f"   VIX: {regime_data['vix']:.2f}")
        print(f"   SPX: {regime_data['spx']:.2f}")
        print(f"   VIX history: {len(regime_data['vix_history'])} bars")
        print(f"   SPX history: {len(regime_data['spx_history'])} bars")
    except Exception as e:
        print(f"❌ Market regime data fetch failed: {e}")
    
    # Fetch options chain
    try:
        chain = adapter.fetch_options_chain("SPY")
        print(f"✅ Options chain: {len(chain)} options fetched")
        print(chain.head(6))
    except Exception as e:
        print(f"❌ Options chain fetch failed: {e}")
