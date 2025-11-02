# Gnosis DHPE - Quick Start Guide

## Installation

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Verify Installation

```bash
python example_usage.py
```

You should see output demonstrating all three engines working together.

## Basic Usage

### Import the Engines

```python
from engines import dhpe, liquidity, orderflow
from config import get_dhpe_config
```

### Load Configuration

```python
config = get_dhpe_config()
```

### Prepare Your Data

Your market data should be in pandas DataFrame format:

```python
import pandas as pd

# Price bars with columns: ['timestamp', 'close', 'volume']
bars_df = pd.DataFrame({
    'timestamp': [...],  # datetime values
    'close': [...],      # closing prices
    'volume': [...]      # trading volume
})

# Options data with columns: ['strike', 'tau', 'gamma', 'vanna', 'charm', 'oi', 'mid_iv']
options_df = pd.DataFrame({
    'strike': [...],     # strike prices
    'tau': [...],        # time to expiry (years)
    'gamma': [...],      # gamma values
    'vanna': [...],      # vanna values
    'charm': [...],      # charm values
    'oi': [...],         # open interest
    'mid_iv': [...]      # mid implied volatility
})
```

### Run the Analysis

```python
# 1. Compute liquidity
lam = liquidity.estimate_amihud(bars_df, span=20)

# 2. Compute DHPE sources (Gamma, Vanna, Charm densities)
G, Vn, Ch = dhpe.sources(options_df, projector=config['projector'])

# 3. Build Green's kernel
K = dhpe.greens_kernel(lam, kappa=config['kernel']['kappa'])

# 4. Compute pressure potential
Pi = dhpe.potential(G, Vn, Ch, K, weights=config['weights'])

# 5. Compute gradients
grad = dhpe.gradient(Pi)      # Spatial gradient
dPi = dhpe.dPi_dt(Pi)         # Temporal derivative

# 6. Compute order flow
dV, cvd = orderflow.compute(bars_df)
```

### Interpret Results

- **λ (lambda)**: Amihud illiquidity - higher values indicate less liquid market
- **Π (Pi)**: Pressure potential - represents dealer hedging pressure
- **∂xΠ (grad)**: Spatial gradient - indicates pressure direction
- **∂tΠ (dPi)**: Temporal derivative - indicates pressure rate of change
- **ΔV (dV)**: Signed volume - directional flow per bar
- **CVD**: Cumulative volume delta - aggregate buying/selling pressure

## Working with Alpaca API

### Get Configuration

```python
from config import get_alpaca_config
alpaca_config = get_alpaca_config()
```

### Initialize Alpaca Client

```python
import alpaca_trade_api as tradeapi

api = tradeapi.REST(
    key_id=alpaca_config['key_id'],
    secret_key=alpaca_config['secret_key'],
    base_url=alpaca_config['base_url']
)

# Fetch historical bars
bars = api.get_bars('SPY', '1Hour', limit=100).df
```

## Configuration

Edit `config.py` to adjust DHPE parameters:

```python
DHPE_CONFIG = {
    'kernel': {
        'kappa': 0.1,  # Screening parameter (controls kernel width)
    },
    'weights': {
        'alpha_G': 1.0,   # Gamma weight
        'alpha_V': 0.5,   # Vanna weight  
        'alpha_C': 0.3,   # Charm weight
    },
    'projector': {
        'mode': 'sticky-delta',
        'bins': 50,
    },
    'liquidity': {
        'span': 20,  # EWMA smoothing window
    },
}
```

## Environment Variables

All API credentials are stored in `.env` file (already configured from the credentials you provided).

⚠️ **Security**: Never commit `.env` to version control!

## Next Steps

1. **Review the code**: Check out `engines/dhpe.py`, `engines/liquidity.py`, and `engines/orderflow.py`
2. **Implement TODOs**: The engines have placeholder implementations marked with `# TODO`
3. **Add real data**: Connect to Alpaca API for live market data
4. **Build signals**: Create trading signals based on DHPE outputs
5. **Backtest**: Implement backtesting framework

## Common Issues

### Import Errors

If you see `ModuleNotFoundError`, ensure you're in the project directory and have installed dependencies:

```bash
cd /home/user/webapp
pip install -r requirements.txt
```

### Data Format Errors

Ensure your DataFrames have the correct column names:
- `bars_df`: `['close', 'volume']` minimum required
- `options_df`: `['strike', 'tau', 'gamma', 'vanna', 'charm', 'oi', 'mid_iv']`

## Support

For more details, see:
- `README.md` - Full documentation
- `example_usage.py` - Working examples
- `engines/*.py` - Engine implementations

## License

Proprietary - All rights reserved
