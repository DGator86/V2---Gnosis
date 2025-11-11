"""
Data ingestion module.
Handles loading data from various sources (API, files, database).
"""

import pandas as pd
from typing import List, Optional
from datetime import datetime
from ..schemas.bars import Bar
from ..schemas.options import OptionSnapshot


def load_bars_from_csv(
    filepath: str,
    symbol: str
) -> List[Bar]:
    """
    Load bar data from CSV file.
    
    Parameters
    ----------
    filepath : str
        Path to CSV file
    symbol : str
        Symbol to associate with bars
        
    Returns
    -------
    list[Bar]
        List of Bar objects
    """
    df = pd.read_csv(filepath)
    
    # Expected columns: timestamp, open, high, low, close, volume
    bars = []
    for _, row in df.iterrows():
        bar = Bar(
            ts=pd.to_datetime(row['timestamp']),
            symbol=symbol,
            open=float(row['open']),
            high=float(row['high']),
            low=float(row['low']),
            close=float(row['close']),
            volume=float(row['volume']),
            vwap=float(row['vwap']) if 'vwap' in row and pd.notna(row['vwap']) else None
        )
        bars.append(bar)
    
    return bars


def load_options_from_csv(
    filepath: str,
    symbol: str
) -> List[OptionSnapshot]:
    """
    Load options data from CSV file.
    
    Parameters
    ----------
    filepath : str
        Path to CSV file
    symbol : str
        Underlying symbol
        
    Returns
    -------
    list[OptionSnapshot]
        List of OptionSnapshot objects
    """
    df = pd.read_csv(filepath)
    
    options = []
    for _, row in df.iterrows():
        opt = OptionSnapshot(
            ts=pd.to_datetime(row['timestamp']),
            symbol=symbol,
            expiry=str(row['expiry']),
            strike=float(row['strike']),
            right=str(row['right']),
            bid=float(row['bid']),
            ask=float(row['ask']),
            iv=float(row['iv']),
            delta=float(row['delta']),
            gamma=float(row['gamma']),
            vega=float(row['vega']),
            theta=float(row['theta']),
            open_interest=int(row['open_interest']) if 'open_interest' in row and pd.notna(row['open_interest']) else None,
            volume=int(row['volume']) if 'volume' in row and pd.notna(row['volume']) else None
        )
        options.append(opt)
    
    return options


def load_bars_from_api(
    symbol: str,
    start: datetime,
    end: datetime,
    timeframe: str = '1Hour',
    api_config: Optional[dict] = None
) -> List[Bar]:
    """
    Load bar data from API (e.g., Alpaca).
    
    Parameters
    ----------
    symbol : str
        Ticker symbol
    start : datetime
        Start date
    end : datetime
        End date
    timeframe : str
        Timeframe (e.g., '1Hour', '1Day')
    api_config : dict, optional
        API configuration
        
    Returns
    -------
    list[Bar]
        List of Bar objects
    """
    # Placeholder: would implement actual API calls
    # Example using Alpaca:
    # import alpaca_trade_api as tradeapi
    # api = tradeapi.REST(**api_config)
    # bars_df = api.get_bars(symbol, timeframe, start=start, end=end).df
    
    return []
