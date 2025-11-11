"""I/O utilities for time series data handling."""

from __future__ import annotations
import pandas as pd
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


def ensure_timeseries(
    df: pd.DataFrame,
    ts_col: str = "timestamp",
    sort: bool = True
) -> pd.DataFrame:
    """Ensure DataFrame has proper DatetimeIndex.
    
    Args:
        df: Input DataFrame
        ts_col: Name of timestamp column (if not index)
        sort: Whether to sort by index
        
    Returns:
        DataFrame with DatetimeIndex
    """
    df = df.copy()
    
    # Convert timestamp column to index if needed
    if ts_col in df.columns:
        df = df.set_index(ts_col)
    
    # Ensure index is DatetimeIndex
    if not isinstance(df.index, pd.DatetimeIndex):
        try:
            df.index = pd.to_datetime(df.index, utc=True, errors="coerce")
        except Exception as e:
            logger.warning(f"Failed to convert index to datetime: {e}")
            return df
    
    # Remove invalid timestamps
    df = df[~df.index.isna()]
    
    # Sort if requested
    if sort:
        df = df.sort_index()
    
    # Remove duplicates
    df = df[~df.index.duplicated(keep='first')]
    
    return df


def align_merge(
    dfs: List[pd.DataFrame],
    how: str = "outer"
) -> pd.DataFrame:
    """Merge multiple DataFrames on their indices.
    
    Args:
        dfs: List of DataFrames to merge
        how: Join method ('outer', 'inner', 'left', 'right')
        
    Returns:
        Merged DataFrame
    """
    if not dfs:
        return pd.DataFrame()
    
    # Filter out None and empty DataFrames
    valid_dfs = [df for df in dfs if df is not None and not df.empty]
    
    if not valid_dfs:
        return pd.DataFrame()
    
    # Start with first DataFrame
    result = valid_dfs[0].copy()
    
    # Merge remaining DataFrames
    for df in valid_dfs[1:]:
        result = result.join(df, how=how, rsuffix='_dup')
        
        # Remove duplicate columns
        dup_cols = [c for c in result.columns if c.endswith('_dup')]
        if dup_cols:
            result = result.drop(columns=dup_cols)
    
    # Sort and clean
    result = result.sort_index()
    result = result.dropna(how='all')
    
    return result


def resample_ohlcv(
    df: pd.DataFrame,
    freq: str = "1H",
    ohlcv_cols: Optional[dict] = None
) -> pd.DataFrame:
    """Resample OHLCV data to different frequency.
    
    Args:
        df: Input OHLCV DataFrame
        freq: Target frequency (e.g., '5T', '1H', '1D')
        ohlcv_cols: Column mapping (defaults to standard names)
        
    Returns:
        Resampled DataFrame
    """
    if ohlcv_cols is None:
        ohlcv_cols = {
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }
    
    df = ensure_timeseries(df)
    
    # Build aggregation dict for available columns
    agg_dict = {}
    for col, agg in ohlcv_cols.items():
        if col in df.columns:
            agg_dict[col] = agg
    
    if not agg_dict:
        logger.warning("No OHLCV columns found for resampling")
        return df
    
    resampled = df.resample(freq).agg(agg_dict)
    resampled = resampled.dropna(how='all')
    
    return resampled