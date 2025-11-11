# Gnosis V2 Trading Framework

A comprehensive, modular framework for quantitative trading analysis using pressure fields, liquidity metrics, sentiment analysis, and intelligent agents.

## Version 2.0

This repository now contains the **V2 framework** with a complete multi-layered architecture:

- ✅ **Data Layer**: Ingestion, normalization, feature storage
- ✅ **Engine Layer**: Hedge pressure, liquidity, sentiment & regime analysis
- ✅ **Agent Layer**: Specialized analysis agents + thesis composer
- ✅ **Trade Layer**: Strategy construction + risk management
- ✅ **Evaluation Layer**: Backtesting + performance metrics

## Quick Start

### V2 Framework (Recommended)

```bash
# Install dependencies
pip install -r requirements.txt

# Run the V2 example
python example_framework.py
```

### V1 Legacy (Backward Compatible)

```bash
# Run the V1 example
python example_usage.py
```

## Project Structure

```
/home/runner/work/V2---Gnosis/V2---Gnosis/
├── src/                      # V2 Framework (NEW)
│   ├── schemas/             # Pydantic data models
│   ├── engines/             # Hedge, Liquidity, Sentiment engines
│   ├── agents/              # Analysis agents + Composer
│   ├── trade/               # Trade construction + Risk mgmt
│   ├── eval/                # Backtesting + Metrics
│   ├── data_io/             # Data ingestion & storage
│   ├── utils/               # Utilities
│   ├── config/              # YAML configuration
│   └── pipeline.py          # Main orchestrator
├── engines/                 # V1 Legacy engines (deprecated)
│   ├── dhpe.py             # Dealer Hedge Pressure Engine
│   ├── liquidity.py        # Liquidity metrics (Amihud λ)
│   └── orderflow.py        # Order flow analysis (ΔV, CVD)
├── example_framework.py     # V2 complete demo
├── example_usage.py         # V1 legacy demo
├── config.py               # V1 legacy config
├── requirements.txt        # Python dependencies
└── README.md              # This file
```

## V2 Framework Architecture

### Layers

1. **Data Layer** (`src/data_io/`)
   - Ingestion from CSV, API, databases
   - Normalization to common schemas
   - Feature store for caching (Parquet/DuckDB)

2. **Engine Layer** (`src/engines/`)
   - **Hedge Engine**: GEX, vanna, charm, gamma flip level, pressure score
   - **Liquidity Engine**: Amihud, Kyle's λ, VPOC, zones, dark pool ratio
   - **Sentiment Engine**: News sentiment, regime classification, Wyckoff phases

3. **Agent Layer** (`src/agents/`)
   - **Hedge Agent**: Interprets dealer pressure fields
   - **Liquidity Agent**: Maps liquidity zones and trends
   - **Sentiment Agent**: Validates direction via sentiment/Wyckoff
   - **Composer Agent**: Merges findings into unified thesis

4. **Trade Layer** (`src/trade/`)
   - Trade constructor for stocks and options strategies
   - Risk management: Kelly sizing, position limits, VaR

5. **Evaluation Layer** (`src/eval/`)
   - Backtesting engine with walk-forward validation
   - Performance metrics: Sharpe, Sortino, MAR, drawdown, etc.

### Data Flow

```
Raw Data → Engines → Agents → Composer → Trade Ideas → Evaluation
```

## Usage Examples

### V2 Framework Pipeline

```python
from src import run_pipeline, load_config, Bar, OptionSnapshot

# Load configuration
config = load_config()

# Prepare data
bars = [...]      # List[Bar] - price history
options = [...]   # List[OptionSnapshot] - options chain
news_scores = [...] # Optional[List[float]] - sentiment scores

# Run complete pipeline
trade_ideas = run_pipeline(
    symbol="SPY",
    bars=bars,
    options=options,
    news_scores=news_scores
)

# Process results
for idea in trade_ideas:
    print(f"Strategy: {idea.strategy}")
    print(f"Direction: {idea.direction}")
    print(f"Expected P&L: ${idea.projected_pnl:.2f}")
```

### Individual Components

```python
from src.engines import compute_hedge_fields, compute_liquidity_fields
from src.agents import analyze_hedge, compose_thesis
from src.trade import construct_trade_ideas

# Use engines individually
hedge_fields = compute_hedge_fields(symbol, options, bars)
liquidity_fields = compute_liquidity_fields(symbol, bars)

# Use agents
hedge_finding = analyze_hedge(snapshot)

# Construct trades
trade_ideas = construct_trade_ideas(thesis, options, bars)
```

## Configuration

Edit `src/config/settings.yaml` to customize:

```yaml
symbols: [SPY, QQQ]

risk:
  max_risk_per_trade: 0.01   # 1% per trade
  max_open_trades: 5

engines:
  hedge:
    min_oi_threshold: 50
  liquidity:
    profile_lookback: 60
  sentiment:
    wyckoff_enable: true
```

## Documentation

- **V2 Framework**: See `src/README.md` for complete architecture
- **Quick Start**: See `QUICKSTART.md` for tutorials
- **Theory**: See `docs/THEORY.md` for mathematical background
- **Implementation**: See `docs/IMPLEMENTATION_ROADMAP.md`

## Key Features

✅ **Type-Safe**: Pydantic models enforce data contracts  
✅ **Modular**: Independent, testable layers  
✅ **Vectorized**: NumPy operations for performance  
✅ **Explainable**: Feature breadcrumbs in every decision  
✅ **Configurable**: YAML-based configuration  
✅ **Extensible**: Easy to add new engines/agents

## V1 Legacy Components

The original V1 engines are still available for backward compatibility:

## V1 Legacy Components (Deprecated)

The original V1 engines are still available in `engines/` directory:

### 1. DHPE Engine (`engines/dhpe.py`)
Implements the core dealer hedge pressure mechanics:
- **sources()**: Computes Gamma, Vanna, Charm densities
- **greens_kernel()**: Builds Green's function for liquidity operator
- **potential()**: Forms pressure potential Π from weighted sources
- **gradient()**: Computes spatial gradient ∂xΠ
- **dPi_dt()**: Approximates temporal derivative ∂tΠ

### 2. Liquidity Engine (`engines/liquidity.py`)
Measures market resistance:
- **estimate_amihud()**: Computes Amihud illiquidity λ with EWMA smoothing

### 3. Order Flow Engine (`engines/orderflow.py`)
Derivatives directional flow metrics:
- **compute()**: Calculates signed volume (ΔV) and cumulative volume delta (CVD)

**Note**: V1 engines are maintained for backward compatibility but new development should use V2 framework.

## Migration from V1 to V2

V1 users can migrate gradually:

1. V1 code still works (no breaking changes)
2. Import V2 components: `from src import run_pipeline`
3. Use V2 schemas: `from src.schemas import Bar, OptionSnapshot`
4. Leverage V2 agents for enhanced analysis
5. Eventually deprecate V1 engine calls

## Development

### Running Tests

```bash
pytest tests/
```

### Code Formatting

```bash
black src/ engines/ --check
flake8 src/ engines/
```

## Setup (V1 Legacy)

## Setup (V2 Framework)

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Settings

Edit `src/config/settings.yaml` or create a `.env` file for API credentials.

### 3. Run Example

```bash
python example_framework.py
```

### 4. Import and Use

```python
from src import run_pipeline

trade_ideas = run_pipeline(symbol, bars, options)
```

## API Credentials (Optional)

For live data integration via Alpaca API:

## API Credentials (Optional)

For live data integration, create a `.env` file:

```bash
ALPACA_API_KEY=your_key
ALPACA_API_SECRET=your_secret
ALPACA_API_URL=https://paper-api.alpaca.markets/v2
```

The system integrates with:
- **Alpaca Markets**: Paper trading API for market data and execution

All credentials are loaded via `python-dotenv`.

## Next Steps

1. **Live Data**: Connect Alpaca API for real-time feeds
2. **Backtest**: Run historical simulations to validate strategies
3. **Enhance**: Add FinBERT for news sentiment, HMM for Wyckoff
4. **Dashboard**: Build visualization interface
5. **Deploy**: Set up production monitoring and alerts

## Security Notes

⚠️ **IMPORTANT**: 
- Never commit `.env` file to version control
- Rotate API keys regularly
- Use paper trading accounts for testing
- Keep credentials encrypted in production

## License

Proprietary - All rights reserved
