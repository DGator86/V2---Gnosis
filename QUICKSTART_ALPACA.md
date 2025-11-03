# Quick Start: Alpaca API Usage

**5-Minute Guide to Using Alpaca Integration**

---

## 🚀 Fetch Market Data

### Single Day (Hourly Bars)
```bash
cd /home/user/webapp/agentic-trading
python -m gnosis.ingest.adapters.alpaca SPY 2024-11-01
```

### Date Range (Multiple Days)
```python
from gnosis.ingest.adapters.alpaca import AlpacaAdapter

adapter = AlpacaAdapter()
df = adapter.fetch_bars('SPY', '2024-10-01', '2024-10-31', '1Hour')
path = adapter.save_to_l1(df, date='2024-10-01')
```

### Different Timeframes
```python
# 1-minute bars (recent data only)
df = adapter.fetch_bars('SPY', '2024-11-01', '2024-11-01', '1Min')

# 5-minute bars
df = adapter.fetch_bars('SPY', '2024-11-01', '2024-11-01', '5Min')

# Daily bars (unlimited history)
df = adapter.fetch_bars('SPY', '2024-01-01', '2024-12-31', '1Day')
```

---

## 🧮 Generate L3 Features

```python
import pandas as pd
from gnosis.engines.hedge_v0 import compute_hedge_v0
from gnosis.engines.liquidity_v0 import compute_liquidity_v0
from gnosis.engines.sentiment_v0 import compute_sentiment_v0
from gnosis.feature_store.store import FeatureStore
from gnosis.schemas.base import L3Canonical

# Load L1 data
df = pd.read_parquet("data_l1/l1_2024-10-01.parquet")

# Initialize feature store
fs = FeatureStore()

# Process each bar (skip first 50 for warmup)
for i in range(50, len(df)):
    t = df.loc[i, "t_event"]
    price = df.loc[i, "price"]
    window = df.iloc[max(0, i-60):i+1].copy()
    
    # Compute features
    hedge = compute_hedge_v0("SPY", t, price, options_chain)
    liq = compute_liquidity_v0("SPY", t, window)
    sent = compute_sentiment_v0("SPY", t, window)
    
    # Store
    row = L3Canonical(symbol="SPY", bar=t, hedge=hedge, liquidity=liq, sentiment=sent)
    fs.write(row)
```

---

## 📊 Run Backtest

### Quick Test
```bash
./run_comparison.sh SPY 2024-10-01
```

### Programmatic Backtest
```python
from gnosis.backtest.comparative_backtest import run_comparison

results = run_comparison("SPY", "2024-10-01")
print(results)
```

---

## 🔐 API Credentials

Stored in `.env` file:
```bash
ALPACA_API_KEY=PKFOCAPPJWKTFSA2JCQVD3ZD46
ALPACA_SECRET_KEY=9yzE77dNy1kbDwcZnvBDnrHp7VUz5KJXjUNErgwEnecx
ALPACA_BASE_URL=https://paper-api.alpaca.markets/v2
```

**Account:** PA326XSPPXOS (Paper Trading, $30,000 balance)

---

## 📁 Data Locations

| Data Layer | Path | Description |
|------------|------|-------------|
| L1 (Raw) | `data_l1/l1_YYYY-MM-DD.parquet` | Price bars from Alpaca |
| L3 (Features) | `data/date=YYYY-MM-DD/symbol=*/feature_set_id=v0.1.0/` | Computed features |
| Backtest Results | `comparative_backtest_*.json` | Test outputs |

---

## 🛠️ Common Tasks

### Check API Connection
```python
from gnosis.ingest.adapters.alpaca import AlpacaAdapter
adapter = AlpacaAdapter()  # Will print status
```

### View Available Data
```bash
ls -lh data_l1/
ls -lh data/date=2024-*/symbol=SPY/feature_set_id=v0.1.0/
```

### Run Latest Backtest
```bash
# Get today's date
DATE=$(date +%Y-%m-%d)
./run_comparison.sh SPY $DATE
```

---

## 📖 Full Documentation

- Architecture: `ARCHITECTURE_REPORT.md`
- Integration Details: `ALPACA_INTEGRATION_COMPLETE.md`
- Session Summary: `SESSION_SUMMARY.md`
- Alpaca Docs: https://alpaca.markets/docs/

---

## ⚠️ Important Notes

1. **1-Minute Data:** Only available for last 30 days
2. **Hourly/Daily:** Unlimited historical data
3. **Options Data:** Currently using synthetic/placeholder
4. **Rate Limits:** Alpaca has API rate limits - implement backoff if hitting them
5. **Paper Trading:** Current setup uses paper account (no real money)

---

## 🚨 Troubleshooting

### "401 Unauthorized"
- Check credentials in `.env` file
- Verify Alpaca account is active

### "No bars returned"
- Check date format (YYYY-MM-DD)
- Ensure market was open on that date
- Try different timeframe (1Hour works best)

### "Module not found"
- Activate virtual environment: `source venv/bin/activate`
- Install dependencies: `pip install -r requirements.txt`

---

**Last Updated:** 2025-11-03  
**Status:** ✅ Operational and Production Ready
