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

try:
    from .public_adapter import (
        PublicMarketAdapter,
        PublicOptionsAdapter,
        PublicNewsAdapter,
        create_public_adapters
    )
except ImportError:
    pass  # requests not installed or Public.com adapter unavailable

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
    "PublicMarketAdapter",
    "PublicOptionsAdapter",
    "PublicNewsAdapter",
    "create_public_adapters",
    "SampleOptionsGenerator",
    "generate_sample_chain_for_testing",
]

# Public.com adapters (requires requests)
try:
    from .public_adapter import (
        PublicMarketAdapter,
        PublicOptionsAdapter,
        PublicNewsAdapter,
        create_public_adapters
    )
    __all__.extend([
        "PublicMarketAdapter",
        "PublicOptionsAdapter",
        "PublicNewsAdapter",
        "create_public_adapters",
    ])
except ImportError:
    pass  # requests not installed
