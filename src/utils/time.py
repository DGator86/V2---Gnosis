"""
Time utilities for the framework.
"""

from datetime import datetime, timedelta
from typing import List
import pandas as pd


def get_trading_days(start: datetime, end: datetime) -> List[datetime]:
    """
    Get list of trading days between start and end dates.
    
    Parameters
    ----------
    start : datetime
        Start date
    end : datetime
        End date
        
    Returns
    -------
    list[datetime]
        Trading days (excludes weekends)
    """
    days = []
    current = start
    
    while current <= end:
        # Skip weekends (Saturday=5, Sunday=6)
        if current.weekday() < 5:
            days.append(current)
        current += timedelta(days=1)
    
    return days


def round_to_market_hours(dt: datetime) -> datetime:
    """
    Round datetime to nearest market hour (9:30 AM - 4:00 PM ET).
    
    Parameters
    ----------
    dt : datetime
        Input datetime
        
    Returns
    -------
    datetime
        Rounded to market hours
    """
    # Simple implementation: round to nearest hour
    # In production, would handle market open/close times properly
    return dt.replace(minute=0, second=0, microsecond=0)


def is_market_open(dt: datetime) -> bool:
    """
    Check if market is open at given datetime.
    
    Parameters
    ----------
    dt : datetime
        Datetime to check
        
    Returns
    -------
    bool
        True if market is open
    """
    # Simple check: weekdays only
    # In production, would check actual market calendar
    return dt.weekday() < 5


def annualize_return(
    total_return: float,
    num_days: int
) -> float:
    """
    Annualize a return.
    
    Parameters
    ----------
    total_return : float
        Total return over period
    num_days : int
        Number of days in period
        
    Returns
    -------
    float
        Annualized return
    """
    if num_days <= 0:
        return 0.0
    
    years = num_days / 365.0
    annualized = (1 + total_return) ** (1 / years) - 1
    
    return annualized
