"""
Alpaca Market Data Adapter

Fetches historical bars and options chain from Alpaca Markets API.
Uses paper trading endpoint for testing.

Updated 2025-11-03: Using official alpaca-py SDK for better reliability
"""

from __future__ import annotations
import os
from datetime import datetime, timedelta
from typing import Optional
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

# Load environment variables from .env file
load_dotenv()

class AlpacaAdapter:
    """Adapter for Alpaca Markets API"""
    
    def __init__(self, api_key: str = None, secret_key: str = None):
        """
        Initialize Alpaca adapter using official SDK
        
        Args:
            api_key: Alpaca API key (defaults to env var)
            secret_key: Alpaca secret key (defaults to env var)
        """
        self.api_key = api_key or os.getenv("ALPACA_API_KEY")
        self.secret_key = secret_key or os.getenv("ALPACA_SECRET_KEY")
        
        if not self.api_key or not self.secret_key:
            raise ValueError("Alpaca API credentials not found. Set ALPACA_API_KEY and ALPACA_SECRET_KEY")
        
        # Initialize official SDK client
        self.client = StockHistoricalDataClient(self.api_key, self.secret_key)
        
        print(f"✅ Alpaca adapter initialized (Account: {self.api_key[:6]}...)")
    
    def fetch_bars(
        self,
        symbol: str,
        start_date: str,
        end_date: str = None,
        timeframe: str = "1Hour"
    ) -> pd.DataFrame:
        """
        Fetch historical bars from Alpaca using official SDK
        
        Args:
            symbol: Trading symbol (e.g., "SPY")
            start_date: Start date in YYYY-MM-DD format
            end_date: End date (defaults to start_date)
            timeframe: Bar timeframe - "1Min", "5Min", "15Min", "30Min", "1Hour", "1Day"
        
        Returns:
            DataFrame with columns: t_event, symbol, price, volume, dollar_volume
        """
        if end_date is None:
            end_date = start_date
        
        # Parse dates
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
        
        # Map timeframe string to TimeFrame object
        timeframe_map = {
            "1Min": TimeFrame.Minute,
            "5Min": TimeFrame(5, "Min"),
            "15Min": TimeFrame(15, "Min"),
            "30Min": TimeFrame(30, "Min"),
            "1Hour": TimeFrame.Hour,
            "1Day": TimeFrame.Day
        }
        
        if timeframe not in timeframe_map:
            raise ValueError(f"Invalid timeframe: {timeframe}. Choose from: {list(timeframe_map.keys())}")
        
        tf = timeframe_map[timeframe]
        
        print(f"📡 Fetching {symbol} from Alpaca...")
        print(f"   Date range: {start_date} to {end_date}")
        print(f"   Timeframe: {timeframe}")
        
        # Create request
        request = StockBarsRequest(
            symbol_or_symbols=[symbol],
            timeframe=tf,
            start=start_dt,
            end=end_dt
        )
        
        # Fetch data
        bars = self.client.get_stock_bars(request)
        df = bars.df.reset_index()
        
        if len(df) == 0:
            raise ValueError(f"No bars returned for {symbol} on {start_date}")
        
        print(f"   ✅ Fetched {len(df)} bars")
        
        # Standardize to L1 format
        df = df.rename(columns={
            "timestamp": "t_event",
            "close": "price"
        })
        df["symbol"] = symbol
        df["dollar_volume"] = df["price"] * df["volume"]
        
        # Select and reorder columns
        result = df[["t_event", "symbol", "price", "volume", "dollar_volume"]]
        
        return result
    
    def fetch_options_chain(
        self,
        symbol: str,
        date: str = None
    ) -> pd.DataFrame:
        """
        Fetch options chain snapshot
        
        Note: Alpaca's options data access may be limited on paper trading.
        This is a placeholder implementation.
        
        Args:
            symbol: Underlying symbol (e.g., "SPY")
            date: Date for options chain (defaults to today)
        
        Returns:
            DataFrame with columns: strike, expiry, iv, delta, gamma, vega, theta, open_interest
        """
        # Alpaca options API (limited on paper)
        # For production, may need to use a dedicated options data provider
        
        print(f"⚠️  Options chain fetching not fully implemented for Alpaca")
        print(f"    Consider using CBOE or another options data provider")
        
        # Return synthetic options chain for now
        spot_price = self._get_last_trade(symbol)
        
        strikes = [spot_price * (1 + i * 0.01) for i in range(-10, 11)]
        expiry = datetime.now() + timedelta(days=7)
        
        chain = pd.DataFrame({
            "strike": strikes,
            "expiry": expiry,
            "iv": [0.20] * len(strikes),  # Placeholder IV
            "delta": [0.5] * len(strikes),  # Placeholder Greeks
            "gamma": [0.01] * len(strikes),
            "vega": [0.02] * len(strikes),
            "theta": [-0.01] * len(strikes),
            "open_interest": [100] * len(strikes)
        })
        
        return chain
    
    def _get_last_trade(self, symbol: str) -> float:
        """Get last trade price for a symbol (fallback for options chain)"""
        try:
            # Fetch 1 bar to get latest price
            request = StockBarsRequest(
                symbol_or_symbols=[symbol],
                timeframe=TimeFrame.Day,
                start=datetime.now() - timedelta(days=2),
                end=datetime.now()
            )
            bars = self.client.get_stock_bars(request)
            df = bars.df
            if len(df) > 0:
                return float(df['close'].iloc[-1])
        except:
            pass
        
        return 450.0  # Fallback
    
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
        df["source"] = "alpaca"
        df["units_normalized"] = True
        df["raw_ref"] = f"alpaca://{date}"
        
        df.to_parquet(filename, index=False)
        print(f"💾 Saved to: {filename}")
        
        return str(filename)

def fetch_and_save_day(symbol: str, date: str) -> str:
    """
    Convenience function: fetch day and save to L1
    
    Args:
        symbol: Trading symbol
        date: Date in YYYY-MM-DD format
    
    Returns:
        Path to saved file
    """
    adapter = AlpacaAdapter()
    df = adapter.fetch_bars(symbol, date)
    path = adapter.save_to_l1(df, date=date)
    return path

if __name__ == "__main__":
    import sys
    
    # CLI: python -m gnosis.ingest.adapters.alpaca SPY 2025-11-01
    symbol = sys.argv[1] if len(sys.argv) > 1 else "SPY"
    date = sys.argv[2] if len(sys.argv) > 2 else datetime.now().strftime("%Y-%m-%d")
    
    print(f"\n{'='*60}")
    print(f"  Alpaca Data Fetch: {symbol} on {date}")
    print(f"{'='*60}\n")
    
    try:
        path = fetch_and_save_day(symbol, date)
        print(f"\n✅ Success! Data saved to: {path}")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
