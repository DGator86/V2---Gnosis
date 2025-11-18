"""Input adapter protocols for Super Gnosis."""
from .market_data_adapter import MarketDataAdapter
from .news_adapter import NewsAdapter
from .options_chain_adapter import OptionsChainAdapter
from .stub_adapters import StaticMarketDataAdapter, StaticNewsAdapter, StaticOptionsAdapter
try:
    from .yfinance_adapter import (
        YFinanceMarketAdapter,
        YFinanceOptionsAdapter, 
        YFinanceNewsAdapter,
        create_yfinance_adapters
    )
except ImportError:
    pass  # yfinance not installed
from .sample_options_generator import SampleOptionsGenerator, generate_sample_chain_for_testing

__all__ = [
    "MarketDataAdapter",
    "NewsAdapter",
    "OptionsChainAdapter",
    "StaticMarketDataAdapter",
    "StaticNewsAdapter",
    "StaticOptionsAdapter",
    "YFinanceMarketAdapter",
    "YFinanceOptionsAdapter",
    "YFinanceNewsAdapter",
    "create_yfinance_adapters",
    "SampleOptionsGenerator",
    "generate_sample_chain_for_testing",
]
