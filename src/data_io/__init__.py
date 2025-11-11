"""
Data I/O package initialization.
Provides ingestion, normalization, and feature store functionality.
"""

from .ingest import load_bars_from_csv, load_options_from_csv, load_bars_from_api
from .normalize import normalize_bars, normalize_options
from .feature_store import FeatureStore

__all__ = [
    'load_bars_from_csv',
    'load_options_from_csv',
    'load_bars_from_api',
    'normalize_bars',
    'normalize_options',
    'FeatureStore',
]
