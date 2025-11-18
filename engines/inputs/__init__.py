"""Input adapter protocols for Super Gnosis."""
from .market_data_adapter import MarketDataAdapter
from .news_adapter import NewsAdapter
from .options_chain_adapter import OptionsChainAdapter
from .stub_adapters import StaticMarketDataAdapter, StaticNewsAdapter, StaticOptionsAdapter
from .public_trading_adapter import PublicTradingAdapter, create_adapter
from .sample_options_generator import SampleOptionsGenerator, generate_sample_chain_for_testing
from .unusual_whales_adapter import UnusualWhalesAdapter

__all__ = [
    "MarketDataAdapter",
    "NewsAdapter",
    "OptionsChainAdapter",
    "StaticMarketDataAdapter",
    "StaticNewsAdapter",
    "StaticOptionsAdapter",
    "PublicTradingAdapter",
    "create_adapter",
    "SampleOptionsGenerator",
    "generate_sample_chain_for_testing",
    "UnusualWhalesAdapter",
]
