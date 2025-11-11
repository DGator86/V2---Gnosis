"""
Gnosis Trading Framework
A modular framework for quantitative trading analysis using pressure fields,
liquidity metrics, and sentiment analysis.
"""

__version__ = "2.0.0"

# Core pipeline
from .pipeline import run_pipeline, run_pipeline_batch

# Configuration
from .config.config_loader import load_config

# Schemas
from .schemas import (
    Bar, OptionSnapshot,
    HedgeFields, LiquidityFields, SentimentFields, EngineSnapshot,
    AgentFinding, ComposerOutput,
    TradeIdea
)

# Engines
from .engines import (
    compute_hedge_fields,
    compute_liquidity_fields,
    compute_sentiment_fields,
)

# Agents
from .agents import (
    analyze_hedge,
    analyze_liquidity,
    analyze_sentiment,
    compose_thesis,
)

# Trade layer
from .trade import (
    construct_trade_ideas,
    compute_position_size,
    apply_kelly_fraction,
    check_portfolio_limits,
    calculate_var,
)

# Evaluation
from .eval import (
    backtest,
    walk_forward_validation,
    summarize_metrics,
)

# Data I/O
from .data_io import (
    load_bars_from_csv,
    load_options_from_csv,
    normalize_bars,
    normalize_options,
    FeatureStore,
)

# Utils
from .utils import (
    setup_logger,
    log_pipeline_step,
    cached,
)

__all__ = [
    # Core
    'run_pipeline',
    'run_pipeline_batch',
    'load_config',
    
    # Schemas
    'Bar',
    'OptionSnapshot',
    'HedgeFields',
    'LiquidityFields',
    'SentimentFields',
    'EngineSnapshot',
    'AgentFinding',
    'ComposerOutput',
    'TradeIdea',
    
    # Engines
    'compute_hedge_fields',
    'compute_liquidity_fields',
    'compute_sentiment_fields',
    
    # Agents
    'analyze_hedge',
    'analyze_liquidity',
    'analyze_sentiment',
    'compose_thesis',
    
    # Trade
    'construct_trade_ideas',
    'compute_position_size',
    'apply_kelly_fraction',
    'check_portfolio_limits',
    'calculate_var',
    
    # Eval
    'backtest',
    'walk_forward_validation',
    'summarize_metrics',
    
    # Data I/O
    'load_bars_from_csv',
    'load_options_from_csv',
    'normalize_bars',
    'normalize_options',
    'FeatureStore',
    
    # Utils
    'setup_logger',
    'log_pipeline_step',
    'cached',
]
