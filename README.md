# Gnosis DHPE Trading System

Dealer Hedge Pressure Engine (DHPE) implementation for quantitative trading analysis.

## Project Structure

```
/home/user/webapp/
├── engines/               # Core analytical engines
│   ├── __init__.py       # Package initialization
│   ├── dhpe.py          # Dealer Hedge Pressure Engine
│   ├── liquidity.py     # Liquidity metrics (Amihud λ)
│   └── orderflow.py     # Order flow analysis (ΔV, CVD)
├── config.py            # Configuration and credentials
├── .env                 # Environment variables (DO NOT COMMIT)
├── .gitignore          # Git ignore patterns
├── requirements.txt     # Python dependencies
└── README.md           # This file
```

## Engine Components

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

## Setup

### 1. Install Dependencies

```bash
cd /home/user/webapp
pip install -r requirements.txt
```

### 2. Configure Environment

The `.env` file contains all API credentials. Ensure it's properly configured but never committed to version control.

### 3. Import and Use

```python
from engines import dhpe, liquidity, orderflow
from config import get_dhpe_config, get_alpaca_config

# Load configuration
config = get_dhpe_config()

# Compute liquidity
lam = liquidity.estimate_amihud(bars_df)

# Compute DHPE sources
G, Vn, Ch = dhpe.sources(options_df, projector=config['projector'])

# Build kernel and potential
K = dhpe.greens_kernel(lam, kappa=config['kernel']['kappa'])
Pi = dhpe.potential(G, Vn, Ch, K, weights=config['weights'])

# Compute gradients
grad = dhpe.gradient(Pi)
dPi = dhpe.dPi_dt(Pi)

# Order flow metrics
dV, cvd = orderflow.compute(bars_df)
```

## API Credentials

The system integrates with:
- **Alpaca Markets**: Paper trading API for market data and execution
- **ChatGPT**: AI-powered analysis and insights
- **Google Cloud**: Cloud services and APIs
- **N8n**: Workflow automation
- **Git**: Version control integration

All credentials are stored in `.env` and loaded via `config.py`.

## Development

### Running Tests
```bash
pytest tests/
```

### Code Formatting
```bash
black engines/ config.py
flake8 engines/ config.py
```

## Implementation Notes

### M2: DHPE Core
- Source density projections use sticky-delta mapping
- Green's function solves: (-∂x λ⁻¹ ∂x + κ²) K = δ(x)
- Potential combines weighted sources via convolution

### M3: Extensions
- Liquidity: Amihud illiquidity with EWMA smoothing
- Order Flow: Signed volume and cumulative delta
- Future: Kyle's λ, volume-weighted metrics

### TODO
- Implement full sticky-delta projector logic
- Complete Green's function computation
- Add FFT-based convolution for potential
- Integrate real-time data feeds
- Build signal generation layer
- Implement backtesting framework

## Security Notes

⚠️ **IMPORTANT**: 
- Never commit `.env` file to version control
- Rotate API keys regularly
- Use paper trading accounts for testing
- Keep credentials encrypted in production

## License

Proprietary - All rights reserved
