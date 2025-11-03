#!/usr/bin/env python3
"""
Fetch multiple days of real market data for comparative testing.
"""
import sys
from pathlib import Path
from gnosis.ingest.adapters.yfinance_adapter import YFinanceAdapter

def main():
    adapter = YFinanceAdapter()
    
    # Fetch 5 recent trading days (working backwards from Oct 31)
    dates = ['2025-10-30', '2025-10-29', '2025-10-28', '2025-10-27', '2025-10-24']
    
    print("=" * 60)
    print("FETCHING MULTI-DAY MARKET DATA")
    print("=" * 60)
    
    success_count = 0
    for date in dates:
        print(f'\n📅 Fetching {date}...')
        try:
            df = adapter.fetch_bars('SPY', start_date=date, interval='1m')
            if len(df) > 0:
                output_path = f'data_l1/l1_{date}.parquet'
                df.to_parquet(output_path)
                print(f'✓ Saved {len(df)} bars to {output_path}')
                print(f'  Price range: ${df.price.min():.2f} - ${df.price.max():.2f}')
                print(f'  Volume: {df.volume.sum():,.0f}')
                success_count += 1
            else:
                print(f'⚠ No data available for {date}')
        except Exception as e:
            print(f'✗ Error: {e}')
    
    print(f'\n{"=" * 60}')
    print(f'✓ Successfully fetched {success_count}/{len(dates)} days')
    print(f'{"=" * 60}\n')
    
    return 0 if success_count > 0 else 1

if __name__ == '__main__':
    sys.exit(main())
