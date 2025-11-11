"""
Data normalization module.
Standardizes data from different sources into common schemas.
"""

import pandas as pd
from typing import List
from ..schemas.bars import Bar
from ..schemas.options import OptionSnapshot


def normalize_bars(raw_df: pd.DataFrame, symbol: str) -> List[Bar]:
    """
    Normalize raw bar data into Bar schema.
    
    Parameters
    ----------
    raw_df : pd.DataFrame
        Raw bar data with various column names
    symbol : str
        Symbol to associate
        
    Returns
    -------
    list[Bar]
        Normalized Bar objects
    """
    # Map common column name variations
    column_map = {
        'time': 'timestamp',
        'date': 'timestamp',
        'datetime': 'timestamp',
        'o': 'open',
        'h': 'high',
        'l': 'low',
        'c': 'close',
        'v': 'volume',
        'vol': 'volume',
    }
    
    # Rename columns
    df = raw_df.copy()
    df.columns = [column_map.get(c.lower(), c.lower()) for c in df.columns]
    
    # Convert to Bar objects
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


def normalize_options(raw_df: pd.DataFrame, symbol: str) -> List[OptionSnapshot]:
    """
    Normalize raw options data into OptionSnapshot schema.
    
    Parameters
    ----------
    raw_df : pd.DataFrame
        Raw options data
    symbol : str
        Underlying symbol
        
    Returns
    -------
    list[OptionSnapshot]
        Normalized OptionSnapshot objects
    """
    options = []
    for _, row in raw_df.iterrows():
        opt = OptionSnapshot(
            ts=pd.to_datetime(row.get('timestamp', row.get('time', row.get('date')))),
            symbol=symbol,
            expiry=str(row['expiry']),
            strike=float(row['strike']),
            right=str(row.get('right', row.get('type', row.get('option_type')))).upper()[0],
            bid=float(row['bid']),
            ask=float(row['ask']),
            iv=float(row.get('iv', row.get('implied_volatility', 0.0))),
            delta=float(row['delta']),
            gamma=float(row['gamma']),
            vega=float(row['vega']),
            theta=float(row['theta']),
            open_interest=int(row['open_interest']) if 'open_interest' in row and pd.notna(row['open_interest']) else None,
            volume=int(row['volume']) if 'volume' in row and pd.notna(row['volume']) else None
        )
        options.append(opt)
    
    return options
