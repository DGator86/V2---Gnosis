"""
Fetch real market data for testing

Uses yfinance to get actual historical data.
Since 1-minute data is limited, we'll use daily data which has unlimited history.
"""

import sys
from datetime import datetime, timedelta
from gnosis.ingest.adapters.yfinance_adapter import YFinanceAdapter
import pandas as pd

def fetch_month_of_data(symbol: str, start_date: str, days: int = 30):
    """Fetch multiple days and combine into one file for engines"""
    
    adapter = YFinanceAdapter()
    
    # Parse start date
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = start_dt + timedelta(days=days)
    
    print(f"\n{'='*70}")
    print(f"  Fetching {days} days of {symbol} data")
    print(f"  From: {start_date}")
    print(f"  To: {end_dt.strftime('%Y-%m-%d')}")
    print(f"{'='*70}\n")
    
    # Fetch hourly data (good compromise - lots of bars, long history)
    df = adapter.fetch_bars(
        symbol=symbol,
        start_date=start_date,
        end_date=end_dt.strftime("%Y-%m-%d"),
        interval="1h"  # Hourly gives us ~180 bars per month
    )
    
    print(f"\n✅ Fetched {len(df)} hourly bars")
    print(f"   Date range: {df['t_event'].min()} to {df['t_event'].max()}")
    print(f"   Price range: ${df['price'].min():.2f} - ${df['price'].max():.2f}")
    
    # Save as single file (engines will use this as rolling window)
    path = adapter.save_to_l1(df, date=start_date)
    
    print(f"\n💾 Saved to: {path}")
    print(f"\n✅ Ready for backtesting!")
    
    return path

if __name__ == "__main__":
    symbol = sys.argv[1] if len(sys.argv) > 1 else "SPY"
    start_date = sys.argv[2] if len(sys.argv) > 2 else "2024-10-01"
    days = int(sys.argv[3]) if len(sys.argv) > 3 else 30
    
    fetch_month_of_data(symbol, start_date, days)
