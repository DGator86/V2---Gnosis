"""Input adapter protocols for Super Gnosis."""
from .market_data_adapter import MarketDataAdapter
from .news_adapter import NewsAdapter
from .options_chain_adapter import OptionsChainAdapter
from .stub_adapters import StaticMarketDataAdapter, StaticNewsAdapter, StaticOptionsAdapter
from .yfinance_adapter import YFinanceAdapter, get_vix, get_spx, get_market_regime_data
from .sample_options_generator import SampleOptionsGenerator, generate_sample_chain_for_testing

__all__ = [
    "MarketDataAdapter",
    "NewsAdapter",
    "OptionsChainAdapter",
    "StaticMarketDataAdapter",
    "StaticNewsAdapter",
    "StaticOptionsAdapter",
    "YFinanceAdapter",
    "get_vix",
    "get_spx",
    "get_market_regime_data",
    "SampleOptionsGenerator",
    "generate_sample_chain_for_testing",
]
