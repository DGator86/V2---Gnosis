"""Input adapter protocols for Super Gnosis."""
from .market_data_adapter import MarketDataAdapter
from .news_adapter import NewsAdapter
from .options_chain_adapter import OptionsChainAdapter
from .stub_adapters import StaticMarketDataAdapter, StaticNewsAdapter, StaticOptionsAdapter

__all__ = [
    "MarketDataAdapter",
    "NewsAdapter",
    "OptionsChainAdapter",
    "StaticMarketDataAdapter",
    "StaticNewsAdapter",
    "StaticOptionsAdapter",
]
