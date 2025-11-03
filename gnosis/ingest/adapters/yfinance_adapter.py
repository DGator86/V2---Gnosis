"""
Yahoo Finance Adapter

Free historical market data - no API key required!
Perfect for testing and development.
"""

from __future__ import annotations
import yfinance as yf
from datetime import datetime, timedelta
from typing import Optional
import pandas as pd
from pathlib import Path

class YFinanceAdapter:
    """Adapter for Yahoo Finance (free, no API key needed)"""
    
    def fetch_bars(
        self,
        symbol: str,
        start_date: str,
        end_date: str = None,
        interval: str = "1m"
    ) -> pd.DataFrame:
        """
        Fetch historical bars from Yahoo Finance
        
        Args:
            symbol: Trading symbol (e.g., "SPY")
            start_date: Start date in YYYY-MM-DD format
            end_date: End date (defaults to start_date)
            interval: Bar interval (1m, 5m, 15m, 1h, 1d)
        
        Returns:
            DataFrame with columns: t_event, symbol, price, volume
        
        Note: 1m data is only available for last 7 days
        """
        if end_date is None:
            # For intraday, need to go to next day to get full day
            end_dt = datetime.strptime(start_date, "%Y-%m-%d") + timedelta(days=1)
            end_date = end_dt.strftime("%Y-%m-%d")
        
        print(f"Fetching {symbol} bars from Yahoo Finance...")
        print(f"  Date range: {start_date} to {end_date}")
        print(f"  Interval: {interval}")
        
        ticker = yf.Ticker(symbol)
        
        try:
            df = ticker.history(
                start=start_date,
                end=end_date,
                interval=interval,
                actions=False
            )
        except Exception as e:
            raise Exception(f"Yahoo Finance error: {e}")
        
        if df.empty:
            raise ValueError(f"No bars returned for {symbol} on {start_date}. Note: 1m data only available for last 7 days.")
        
        print(f"  ✅ Fetched {len(df)} bars")
        
        # Convert to our format
        df = df.reset_index()
        df["symbol"] = symbol
        df["t_event"] = pd.to_datetime(df["Datetime"] if "Datetime" in df.columns else df["Date"])
        df["price"] = df["Close"]
        df = df.rename(columns={"Volume": "volume"})
        
        # Calculate dollar volume
        df["dollar_volume"] = df["price"] * df["volume"]
        
        # Select columns
        df = df[["t_event", "symbol", "price", "volume", "dollar_volume"]]
        
        # Filter to only market hours if intraday
        if interval in ["1m", "5m", "15m", "30m"]:
            df = df[
                (df["t_event"].dt.time >= pd.Timestamp("09:30").time()) &
                (df["t_event"].dt.time <= pd.Timestamp("16:00").time())
            ]
        
        return df
    
    def save_to_l1(
        self,
        df: pd.DataFrame,
        output_dir: str = "data_l1",
        date: str = None
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
        
        # Add required L1 columns
        df["source"] = "yfinance"
        df["units_normalized"] = True
        df["raw_ref"] = f"yfinance://{date}"
        
        df.to_parquet(filename, index=False)
        print(f"💾 Saved to: {filename}")
        
        return str(filename)

def fetch_and_save_day(symbol: str, date: str, interval: str = "1m") -> str:
    """
    Convenience function: fetch day and save to L1
    
    Args:
        symbol: Trading symbol
        date: Date in YYYY-MM-DD format
        interval: Bar interval (1m, 5m, 15m, 1h, 1d)
    
    Returns:
        Path to saved file
    """
    adapter = YFinanceAdapter()
    df = adapter.fetch_bars(symbol, date, interval=interval)
    path = adapter.save_to_l1(df, date=date)
    return path

if __name__ == "__main__":
    import sys
    
    # CLI: python -m gnosis.ingest.adapters.yfinance_adapter SPY 2024-11-01
    symbol = sys.argv[1] if len(sys.argv) > 1 else "SPY"
    date = sys.argv[2] if len(sys.argv) > 2 else (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    interval = sys.argv[3] if len(sys.argv) > 3 else "1m"
    
    print(f"\n{'='*60}")
    print(f"  Yahoo Finance Data Fetch: {symbol} on {date}")
    print(f"{'='*60}\n")
    
    try:
        path = fetch_and_save_day(symbol, date, interval)
        print(f"\n✅ Success! Data saved to: {path}")
        
        # Show summary
        df = pd.read_parquet(path)
        print(f"\n📊 Summary:")
        print(f"   Bars: {len(df)}")
        print(f"   Time range: {df['t_event'].min()} to {df['t_event'].max()}")
        print(f"   Price range: ${df['price'].min():.2f} - ${df['price'].max():.2f}")
        print(f"   Avg volume: {df['volume'].mean():.0f}")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print(f"\n💡 Tip: For 1-minute data, use a recent date (last 7 days)")
        print(f"   Or use --interval 1d for daily data (unlimited history)")
        sys.exit(1)
