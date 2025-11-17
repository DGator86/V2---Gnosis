"""yfinance adapter for free market data (VIX, SPX, OHLCV)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional
import polars as pl
from loguru import logger

try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False
    yf = None


class YFinanceAdapter:
    """Adapter for fetching free market data via yfinance.
    
    Provides:
    - VIX data (CBOE Volatility Index)
    - SPX data (S&P 500 Index via ^GSPC or SPY ETF)
    - Historical OHLCV for any symbol
    
    Note: Data has ~15-minute delay for free tier.
    """
    
    # Symbol mappings
    VIX_SYMBOL = "^VIX"
    SPX_INDEX_SYMBOL = "^GSPC"  # S&P 500 Index
    SPX_ETF_SYMBOL = "SPY"      # S&P 500 ETF (more liquid, better data)
    
    def __init__(self):
        """Initialize yfinance adapter."""
        if not YFINANCE_AVAILABLE:
            raise ImportError(
                "yfinance not installed. Install with: pip install yfinance"
            )
        
        logger.info("YFinanceAdapter initialized (FREE tier - 15min delay)")
    
    def fetch_vix(self) -> float:
        """Fetch current VIX value.
        
        Returns:
            Current VIX value (float)
            
        Raises:
            ValueError: If VIX data cannot be fetched
        """
        try:
            vix_ticker = yf.Ticker(self.VIX_SYMBOL)
            
            # Get most recent data
            hist = vix_ticker.history(period="1d", interval="1m")
            
            if hist.empty:
                raise ValueError("No VIX data returned")
            
            # Get last close price
            vix_value = float(hist["Close"].iloc[-1])
            
            logger.debug(f"VIX fetched: {vix_value:.2f}")
            
            return vix_value
            
        except Exception as e:
            logger.error(f"Failed to fetch VIX: {e}")
            raise ValueError(f"VIX fetch failed: {e}")
    
    def fetch_spx(self, use_etf: bool = True) -> float:
        """Fetch current SPX value.
        
        Args:
            use_etf: If True, use SPY ETF (more reliable). If False, use ^GSPC index.
            
        Returns:
            Current SPX value (float)
            
        Raises:
            ValueError: If SPX data cannot be fetched
        """
        symbol = self.SPX_ETF_SYMBOL if use_etf else self.SPX_INDEX_SYMBOL
        
        try:
            spx_ticker = yf.Ticker(symbol)
            
            # Get most recent data
            hist = spx_ticker.history(period="1d", interval="1m")
            
            if hist.empty:
                raise ValueError(f"No SPX data returned for {symbol}")
            
            # Get last close price
            spx_value = float(hist["Close"].iloc[-1])
            
            logger.debug(f"SPX fetched ({symbol}): {spx_value:.2f}")
            
            return spx_value
            
        except Exception as e:
            logger.error(f"Failed to fetch SPX from {symbol}: {e}")
            raise ValueError(f"SPX fetch failed: {e}")
    
    def fetch_ohlcv(
        self,
        symbol: str,
        period: str = "1mo",
        interval: str = "5m",
    ) -> pl.DataFrame:
        """Fetch OHLCV data for a symbol.
        
        Args:
            symbol: Stock symbol (e.g., "SPY", "AAPL")
            period: Time period ("1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max")
            interval: Data interval ("1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h", "1d", "5d", "1wk", "1mo", "3mo")
            
        Returns:
            Polars DataFrame with columns: timestamp, open, high, low, close, volume
            
        Note:
            - 1m data: available for last 7 days only
            - 5m data: available for last 60 days
            - 1h data: available for last 730 days
        """
        try:
            ticker = yf.Ticker(symbol)
            
            # Fetch data
            hist = ticker.history(period=period, interval=interval)
            
            if hist.empty:
                raise ValueError(f"No data returned for {symbol}")
            
            # Convert to Polars DataFrame
            hist = hist.reset_index()
            
            # Rename columns to lowercase
            hist.columns = [col.lower() for col in hist.columns]
            
            # Convert to Polars
            df = pl.DataFrame({
                "timestamp": hist["datetime"].astype(str).tolist(),
                "open": hist["open"].tolist(),
                "high": hist["high"].tolist(),
                "low": hist["low"].tolist(),
                "close": hist["close"].tolist(),
                "volume": hist["volume"].astype(int).tolist(),
            })
            
            # Parse timestamp
            df = df.with_columns([
                pl.col("timestamp").str.strptime(pl.Datetime, "%Y-%m-%d %H:%M:%S%z").alias("timestamp")
            ])
            
            logger.info(
                f"Fetched {len(df)} bars for {symbol} "
                f"(period={period}, interval={interval})"
            )
            
            return df
            
        except Exception as e:
            logger.error(f"Failed to fetch OHLCV for {symbol}: {e}")
            raise ValueError(f"OHLCV fetch failed for {symbol}: {e}")
    
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
            use_etf: Use SPY ETF instead of ^GSPC index
            
        Returns:
            Polars DataFrame with SPX historical data
        """
        symbol = self.SPX_ETF_SYMBOL if use_etf else self.SPX_INDEX_SYMBOL
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
    
    def test_connection(self) -> bool:
        """Test connection to yfinance.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Try to fetch SPY (most reliable symbol)
            spy = yf.Ticker("SPY")
            hist = spy.history(period="1d", interval="1m")
            
            if hist.empty:
                logger.error("yfinance test failed: No data returned")
                return False
            
            logger.info("yfinance connection test: SUCCESS")
            return True
            
        except Exception as e:
            logger.error(f"yfinance connection test failed: {e}")
            return False


# Convenience functions

def get_vix() -> float:
    """Get current VIX value.
    
    Returns:
        Current VIX value
    """
    adapter = YFinanceAdapter()
    return adapter.fetch_vix()


def get_spx() -> float:
    """Get current SPX value.
    
    Returns:
        Current SPX value (via SPY ETF)
    """
    adapter = YFinanceAdapter()
    return adapter.fetch_spx(use_etf=True)


def get_market_regime_data() -> dict:
    """Get all market regime data.
    
    Returns:
        Dictionary with vix, spx, and historical data
    """
    adapter = YFinanceAdapter()
    return adapter.fetch_market_regime_data()


def get_ohlcv(symbol: str, period: str = "1mo", interval: str = "5m") -> pl.DataFrame:
    """Get OHLCV data for a symbol.
    
    Args:
        symbol: Stock symbol
        period: Time period
        interval: Data interval
        
    Returns:
        Polars DataFrame with OHLCV data
    """
    adapter = YFinanceAdapter()
    return adapter.fetch_ohlcv(symbol, period=period, interval=interval)


# Example usage
if __name__ == "__main__":
    # Test adapter
    adapter = YFinanceAdapter()
    
    print("Testing yfinance adapter...")
    
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
