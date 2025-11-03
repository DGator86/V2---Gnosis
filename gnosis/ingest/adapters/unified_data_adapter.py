"""
Unified Market Data Adapter

Tries multiple data sources in priority order:
1. Alpaca Markets (if credentials valid)
2. Yahoo Finance (free fallback)

Provides consistent L1 format regardless of source.
"""

from __future__ import annotations
import os
import warnings
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class UnifiedDataAdapter:
    """
    Smart data adapter that tries multiple sources
    
    Priority:
    1. Alpaca (premium, 1-minute bars, real-time)
    2. Yahoo Finance (free, limited to recent 1m, unlimited hourly/daily)
    """
    
    def __init__(self):
        self.alpaca_available = self._check_alpaca()
        self.yfinance_available = self._check_yfinance()
        
        print(f"📡 Data Sources Available:")
        print(f"   Alpaca: {'✅' if self.alpaca_available else '❌'}")
        print(f"   Yahoo Finance: {'✅' if self.yfinance_available else '❌'}")
    
    def _check_alpaca(self) -> bool:
        """Check if Alpaca credentials are valid"""
        try:
            from alpaca.data.historical import StockHistoricalDataClient
            from alpaca.data.requests import StockBarsRequest
            from alpaca.data.timeframe import TimeFrame
            
            api_key = os.getenv("ALPACA_API_KEY")
            secret_key = os.getenv("ALPACA_SECRET_KEY")
            
            if not api_key or not secret_key:
                return False
            
            # Quick test with minimal data request
            client = StockHistoricalDataClient(api_key, secret_key)
            request = StockBarsRequest(
                symbol_or_symbols=["SPY"],
                timeframe=TimeFrame.Day,
                start=datetime.now() - timedelta(days=2),
                end=datetime.now() - timedelta(days=1)
            )
            
            bars = client.get_stock_bars(request)
            return len(bars.df) > 0
            
        except Exception as e:
            warnings.warn(f"Alpaca unavailable: {e}")
            return False
    
    def _check_yfinance(self) -> bool:
        """Check if yfinance is available"""
        try:
            import yfinance as yf
            # Quick test
            ticker = yf.Ticker("SPY")
            df = ticker.history(period="1d")
            return len(df) > 0
        except Exception as e:
            warnings.warn(f"yfinance unavailable: {e}")
            return False
    
    def fetch_bars(
        self,
        symbol: str,
        start_date: str,
        end_date: Optional[str] = None,
        interval: str = "1h"  # Default to hourly
    ) -> pd.DataFrame:
        """
        Fetch bars from best available source
        
        Args:
            symbol: Ticker symbol (e.g., "SPY")
            start_date: Start date in YYYY-MM-DD format
            end_date: End date (optional, defaults to start_date)
            interval: Bar interval
                - "1m", "5m", "15m", "30m" (minute bars)
                - "1h" (hourly - recommended for history)
                - "1d" (daily)
        
        Returns:
            DataFrame with standardized L1 format:
            - t_event: timestamp
            - symbol: ticker
            - price: close price
            - volume: share volume
            - dollar_volume: price * volume
        """
        if end_date is None:
            end_date = start_date
        
        # Try Alpaca first
        if self.alpaca_available:
            try:
                return self._fetch_alpaca(symbol, start_date, end_date, interval)
            except Exception as e:
                warnings.warn(f"Alpaca fetch failed: {e}. Falling back to Yahoo Finance.")
        
        # Fall back to Yahoo Finance
        if self.yfinance_available:
            return self._fetch_yfinance(symbol, start_date, end_date, interval)
        
        raise RuntimeError("No data sources available!")
    
    def _fetch_alpaca(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        interval: str
    ) -> pd.DataFrame:
        """Fetch from Alpaca Markets"""
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame
        
        # Map interval to Alpaca TimeFrame
        timeframe_map = {
            "1m": TimeFrame.Minute,
            "5m": TimeFrame(5, "Min"),
            "15m": TimeFrame(15, "Min"),
            "30m": TimeFrame(30, "Min"),
            "1h": TimeFrame.Hour,
            "1d": TimeFrame.Day
        }
        
        if interval not in timeframe_map:
            raise ValueError(f"Invalid interval: {interval}")
        
        api_key = os.getenv("ALPACA_API_KEY")
        secret_key = os.getenv("ALPACA_SECRET_KEY")
        
        client = StockHistoricalDataClient(api_key, secret_key)
        
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
        
        request = StockBarsRequest(
            symbol_or_symbols=[symbol],
            timeframe=timeframe_map[interval],
            start=start_dt,
            end=end_dt
        )
        
        print(f"📡 Fetching {symbol} from Alpaca ({interval} bars)...")
        bars = client.get_stock_bars(request)
        df = bars.df.reset_index()
        
        # Standardize to L1 format
        df = df.rename(columns={
            "timestamp": "t_event",
            "close": "price"
        })
        df["symbol"] = symbol
        df["dollar_volume"] = df["price"] * df["volume"]
        
        result = df[["t_event", "symbol", "price", "volume", "dollar_volume"]]
        print(f"   ✅ Fetched {len(result)} bars from Alpaca")
        
        return result
    
    def _fetch_yfinance(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        interval: str
    ) -> pd.DataFrame:
        """Fetch from Yahoo Finance"""
        import yfinance as yf
        
        # Map our interval format to yfinance format
        interval_map = {
            "1m": "1m",
            "5m": "5m",
            "15m": "15m",
            "30m": "30m",
            "1h": "1h",
            "1d": "1d"
        }
        
        if interval not in interval_map:
            raise ValueError(f"Invalid interval: {interval}")
        
        yf_interval = interval_map[interval]
        
        # Calculate date range
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
        
        # Warning for minute data limitations
        if interval in ["1m", "5m", "15m", "30m"]:
            days_back = (datetime.now() - start_dt).days
            if days_back > 30:
                warnings.warn(
                    f"Minute data requested for {days_back} days ago. "
                    f"Yahoo Finance only provides minute data for last 30 days. "
                    f"Consider using hourly (1h) or daily (1d) interval."
                )
        
        print(f"📡 Fetching {symbol} from Yahoo Finance ({yf_interval} bars)...")
        
        ticker = yf.Ticker(symbol)
        df = ticker.history(
            start=start_dt,
            end=end_dt,
            interval=yf_interval,
            actions=False
        )
        
        if len(df) == 0:
            raise ValueError(f"No data returned from Yahoo Finance for {symbol}")
        
        # Standardize to L1 format
        df = df.reset_index()
        
        # Handle different column names (Datetime vs Date)
        if "Datetime" in df.columns:
            df["t_event"] = pd.to_datetime(df["Datetime"])
        elif "Date" in df.columns:
            df["t_event"] = pd.to_datetime(df["Date"])
        else:
            df["t_event"] = df.index
        
        df["symbol"] = symbol
        df["price"] = df["Close"]
        df["volume"] = df["Volume"]
        df["dollar_volume"] = df["price"] * df["volume"]
        
        result = df[["t_event", "symbol", "price", "volume", "dollar_volume"]]
        print(f"   ✅ Fetched {len(result)} bars from Yahoo Finance")
        
        return result
    
    def save_to_l1(
        self,
        df: pd.DataFrame,
        output_dir: str = "data_l1",
        date: Optional[str] = None
    ) -> str:
        """
        Save bars to L1 format (parquet)
        
        Args:
            df: DataFrame with bars
            output_dir: Output directory
            date: Date string (extracted from df if not provided)
        
        Returns:
            Path to saved file
        """
        if date is None:
            date = df["t_event"].iloc[0].strftime("%Y-%m-%d")
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        filename = output_path / f"l1_{date}.parquet"
        
        # Add metadata columns
        df["source"] = "unified_adapter"
        df["units_normalized"] = True
        df["raw_ref"] = f"unified://{date}"
        
        df.to_parquet(filename, index=False)
        print(f"💾 Saved {len(df)} bars to: {filename}")
        
        return str(filename)
    
    def fetch_and_save(
        self,
        symbol: str,
        start_date: str,
        end_date: Optional[str] = None,
        interval: str = "1h",
        output_dir: str = "data_l1"
    ) -> str:
        """
        Convenience method: fetch and save in one call
        
        Args:
            symbol: Ticker symbol
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (optional)
            interval: Bar interval (1m, 1h, 1d)
            output_dir: Output directory
        
        Returns:
            Path to saved file
        """
        df = self.fetch_bars(symbol, start_date, end_date, interval)
        path = self.save_to_l1(df, output_dir, start_date)
        return path
    
    def fetch_range(
        self,
        symbol: str,
        start_date: str,
        num_days: int,
        interval: str = "1h",
        output_dir: str = "data_l1"
    ) -> list[str]:
        """
        Fetch a range of days and save each
        
        Args:
            symbol: Ticker symbol
            start_date: Start date (YYYY-MM-DD)
            num_days: Number of days to fetch
            interval: Bar interval
            output_dir: Output directory
        
        Returns:
            List of saved file paths
        """
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = start_dt + timedelta(days=num_days)
        
        print(f"\n{'='*60}")
        print(f"  Fetching {symbol}: {start_date} to {end_dt.strftime('%Y-%m-%d')}")
        print(f"  Interval: {interval} | Days: {num_days}")
        print(f"{'='*60}\n")
        
        # Fetch entire range at once (more efficient)
        df = self.fetch_bars(
            symbol,
            start_date,
            end_dt.strftime("%Y-%m-%d"),
            interval
        )
        
        # Save to single file
        path = self.save_to_l1(df, output_dir, start_date)
        
        print(f"\n✅ Complete! {len(df)} bars saved to {path}")
        
        return [path]


# CLI interface
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python -m gnosis.ingest.adapters.unified_data_adapter SPY 2024-10-01 [num_days] [interval]")
        print()
        print("Examples:")
        print("  python -m gnosis.ingest.adapters.unified_data_adapter SPY 2024-10-01 30 1h")
        print("  python -m gnosis.ingest.adapters.unified_data_adapter SPY 2024-11-01 1 1d")
        sys.exit(1)
    
    symbol = sys.argv[1]
    start_date = sys.argv[2]
    num_days = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    interval = sys.argv[4] if len(sys.argv) > 4 else "1h"
    
    try:
        adapter = UnifiedDataAdapter()
        paths = adapter.fetch_range(symbol, start_date, num_days, interval)
        print(f"\n🎉 Success! Saved {len(paths)} file(s)")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
