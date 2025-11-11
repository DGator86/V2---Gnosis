"""
Type definitions and helpers.
"""

from typing import TypeVar, Union, List
from datetime import datetime


# Generic type variables
T = TypeVar('T')


# Common type aliases
Timestamp = Union[datetime, str]
Symbol = str
Price = float
Volume = float


def ensure_list(value: Union[T, List[T]]) -> List[T]:
    """
    Ensure value is a list.
    
    Parameters
    ----------
    value : T or list[T]
        Value or list of values
        
    Returns
    -------
    list[T]
        Value wrapped in list if not already a list
    """
    if isinstance(value, list):
        return value
    return [value]


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """
    Safe division that returns default on division by zero.
    
    Parameters
    ----------
    numerator : float
        Numerator
    denominator : float
        Denominator
    default : float
        Default value if denominator is zero
        
    Returns
    -------
    float
        Result of division or default
    """
    if denominator == 0:
        return default
    return numerator / denominator
