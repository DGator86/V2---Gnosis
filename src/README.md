# Gnosis V2 Trading Framework

A comprehensive, modular framework for quantitative trading analysis using pressure fields, liquidity metrics, sentiment analysis, and intelligent agents.

## Overview

The Gnosis V2 framework implements a multi-layered architecture for systematic trading analysis:

- **Data Layer**: Ingestion, normalization, and feature storage
- **Engine Layer**: Hedge pressure, liquidity metrics, sentiment & regime analysis
- **Agent Layer**: Specialized analysis agents and thesis composition
- **Trade Layer**: Strategy construction and risk management
- **Evaluation Layer**: Backtesting and performance metrics

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                       Data Layer                            │
│  Ingestion → Normalize → Feature Store (Parquet/DuckDB)    │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                      Engine Layer                           │
│  ┌─────────────┐  ┌────────────┐  ┌──────────────────┐    │
│  │   Hedge     │  │ Liquidity  │  │    Sentiment     │    │
│  │   Engine    │  │  Engine    │  │  & Regime Engine │    │
│  └─────────────┘  └────────────┘  └──────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                      Agent Layer                            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │  Hedge   │  │Liquidity │  │Sentiment │  │ Composer │  │
│  │  Agent   │  │  Agent   │  │  Agent   │  │  Agent   │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                      Trade Layer                            │
│     Trade Constructor + Risk Management + Position Sizing   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                   Evaluation Layer                          │
│        Backtesting + Metrics + Walk-Forward Validation      │
└─────────────────────────────────────────────────────────────┘
```

## Project Structure

```
/home/runner/work/V2---Gnosis/V2---Gnosis/
├── src/                      # Main framework source
│   ├── schemas/             # Pydantic data models
│   │   ├── bars.py          # Bar (OHLCV) schema
│   │   ├── options.py       # Options snapshot schema
│   │   ├── features.py      # Engine output schemas
│   │   ├── signals.py       # Agent output schemas
│   │   └── trades.py        # Trade idea schema
│   ├── data_io/             # Data ingestion & storage
│   │   ├── ingest.py        # Load from CSV/API
│   │   ├── normalize.py     # Data normalization
│   │   └── feature_store.py # Feature caching
│   ├── engines/             # Analytical engines
│   │   ├── hedge_engine.py  # Dealer hedge pressure (GEX, vanna, charm)
│   │   ├── liquidity_engine.py # Liquidity metrics (Amihud, Kyle's λ)
│   │   └── sentiment_engine.py # Sentiment & Wyckoff analysis
│   ├── agents/              # Intelligent agents
│   │   ├── agent_hedge.py   # Hedge specialist
│   │   ├── agent_liquidity.py # Liquidity cartographer
│   │   ├── agent_sentiment.py # Sentiment interpreter
│   │   └── agent_composer.py  # Thesis composer
│   ├── trade/               # Trade construction & risk
│   │   ├── trade_constructor.py # Strategy builder
│   │   └── risk.py          # Risk management & sizing
│   ├── eval/                # Evaluation & backtesting
│   │   ├── backtest.py      # Backtesting engine
│   │   └── metrics.py       # Performance metrics
│   ├── utils/               # Utilities
│   │   ├── time.py          # Time utilities
│   │   ├── caching.py       # Caching helpers
│   │   ├── logging.py       # Logging setup
│   │   └── typing.py        # Type helpers
│   ├── config/              # Configuration
│   │   ├── settings.yaml    # Main config file
│   │   └── config_loader.py # Config loader
│   ├── pipeline.py          # Main orchestrator
│   └── __init__.py          # Package exports
├── engines/                 # Legacy engines (for backward compatibility)
│   ├── dhpe.py
│   ├── liquidity.py
│   └── orderflow.py
├── config.py                # Legacy config
├── example_framework.py     # V2 framework demo
├── example_usage.py         # Legacy demo
├── requirements.txt         # Dependencies
├── README.md               # This file
└── QUICKSTART.md           # Quick start guide
```

## Quick Start

### Installation

```bash
pip install -r requirements.txt
```

### Basic Usage

```python
from src import run_pipeline, load_config, Bar, OptionSnapshot

# Load configuration
config = load_config()

# Prepare your data (or load from CSV/API)
bars = [...]      # List[Bar]
options = [...]   # List[OptionSnapshot]
news_scores = [...] # Optional[List[float]]

# Run the complete pipeline
trade_ideas = run_pipeline(
    symbol="SPY",
    bars=bars,
    options=options,
    news_scores=news_scores
)

# Inspect results
for idea in trade_ideas:
    print(f"Strategy: {idea.strategy}")
    print(f"Entry: ${idea.entry_cost:.2f}")
    print(f"Target: ${idea.exit_target:.2f}")
    print(f"P&L: ${idea.projected_pnl:.2f}")
```

### Run Complete Example

```bash
python example_framework.py
```

This demonstrates the full pipeline with synthetic data.

## Core Components

### 1. Schemas (Data Contracts)

All data uses Pydantic models for type safety:

- **Bar**: OHLCV price data
- **OptionSnapshot**: Options chain with Greeks
- **HedgeFields**: Dealer hedge pressure metrics (GEX, vanna, charm)
- **LiquidityFields**: Liquidity metrics (Amihud, Kyle's λ, VPOC, zones)
- **SentimentFields**: Sentiment scores and regime classification
- **AgentFinding**: Individual agent analysis output
- **ComposerOutput**: Unified trading thesis
- **TradeIdea**: Complete trade specification with risk parameters

### 2. Engine Layer

#### Hedge Engine
Computes dealer-driven pressure fields:
- **GEX** (Gamma Exposure): Net dealer gamma position
- **Vanna**: Sensitivity to spot-vol correlation
- **Charm**: Gamma decay with time
- **Gamma Flip Level**: Price where net gamma crosses zero
- **Pressure Score**: Normalized field intensity (0..1)

#### Liquidity Engine
Measures market microstructure:
- **Amihud Illiquidity**: Price impact per unit volume
- **Kyle's λ**: Price impact coefficient
- **VPOC**: Volume Point of Control
- **Zones**: Key supply/demand levels
- **Dark Pool Ratio**: Off-exchange volume fraction
- **Liquidity Trend**: Tightening/loosening/neutral

#### Sentiment & Regime Engine
Classifies market state:
- **News Sentiment**: Aggregated news scores (-1..1)
- **Regime**: calm/normal/elevated/squeeze_risk/gamma_storm
- **Wyckoff Phase**: accumulation/markup/distribution/markdown

### 3. Agent Layer

#### Hedge Agent
Interprets hedge pressure fields and flags gamma environments.

#### Liquidity Agent
Maps liquidity zones, warns on tightening, identifies liquidity pools.

#### Sentiment Agent
Validates or contradicts direction via sentiment and Wyckoff phase.

#### Composer Agent
Merges findings into coherent thesis with:
- Direction (long/short/neutral)
- Conviction (0..1)
- Time horizon
- Key levels
- Risk flags
- Expected volatility

### 4. Trade Layer

Constructs trade ideas based on regime and thesis:
- **Directional**: Call/put debit spreads, stock positions
- **Neutral**: Iron condors, short strangles
- **Risk Management**: Kelly sizing, position limits, VaR

### 5. Evaluation Layer

Backtesting and performance analysis:
- **Metrics**: Sharpe, Sortino, MAR, max drawdown, win rate, profit factor
- **Walk-Forward**: Expanding window validation
- **Replay**: Historical snapshot reconstruction

## Configuration

Edit `src/config/settings.yaml`:

```yaml
symbols:
  - SPY
  - QQQ

risk:
  max_risk_per_trade: 0.01   # 1% per trade
  max_open_trades: 5
  kelly_fraction: 0.25       # quarter Kelly

engines:
  hedge:
    min_oi_threshold: 50
  liquidity:
    profile_lookback: 60
  sentiment:
    wyckoff_enable: true
```

## Advanced Features

### Caching

```python
from src.utils import cached

@cached(ttl_seconds=300)
def expensive_computation():
    # Results cached for 5 minutes
    pass
```

### Logging

```python
from src.utils import setup_logger, log_pipeline_step

logger = setup_logger("my_module", level="DEBUG")
log_pipeline_step("ENGINE", "SPY", "Computing fields...")
```

### Feature Store

```python
from src.data_io import FeatureStore

store = FeatureStore("data/features")
store.save_features("hedge", "SPY", features, timestamp)
cached_features = store.load_features("hedge", "SPY", start, end)
```

## Backtesting

```python
from src.eval import backtest, summarize_metrics
from datetime import datetime

results = backtest(
    symbols=["SPY"],
    start=datetime(2023, 1, 1),
    end=datetime(2023, 12, 31),
    config=config,
    pipeline_func=run_pipeline
)

metrics = summarize_metrics(results['trade_log'])
print(f"Sharpe: {metrics['sharpe']:.2f}")
print(f"Max DD: {metrics['max_drawdown']:.2%}")
```

## Development

### Running Tests

```bash
pytest tests/
```

### Code Style

```bash
black src/ --check
flake8 src/
```

## Key Principles

1. **Modular**: Each layer is independent and testable
2. **Type-Safe**: Pydantic models enforce data contracts
3. **Vectorized**: NumPy operations for performance
4. **Deterministic**: Fixed seeds, explicit lookbacks
5. **Explainable**: Feature breadcrumbs in every decision

## Migration from V1

The V2 framework maintains backward compatibility with V1 engines:

- Legacy engines in `engines/` directory still work
- V1 config in `config.py` still supported
- Use `example_usage.py` for V1 demo
- Use `example_framework.py` for V2 demo

## Next Steps

1. **Connect Live Data**: Integrate Alpaca API for real-time feeds
2. **Backtest**: Run on historical data to validate strategies
3. **Enhance Wyckoff**: Implement HMM-based phase detection
4. **News API**: Integrate FinBERT for sentiment analysis
5. **Dashboard**: Build visualization interface
6. **Alerts**: Add Telegram/email notifications

## References

- Architecture: See `docs/IMPLEMENTATION_ROADMAP.md`
- Theory: See `docs/THEORY.md`
- Quick Start: See `QUICKSTART.md`
- Example: `example_framework.py`

## License

Proprietary - All rights reserved

## Support

For questions or issues, refer to:
- Code: `src/` directory
- Config: `src/config/settings.yaml`
- Examples: `example_framework.py`
