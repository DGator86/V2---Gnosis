# Quick Start Guide - Agentic Trading System

## 🚀 One-Minute Overview

This system generates trade ideas by combining three AI agents:
1. **Hedge Agent** reads dealer positioning from options
2. **Liquidity Agent** maps support/resistance zones  
3. **Sentiment Agent** measures market mood

**Decision Rule:** Need 2-of-3 agents aligned with high confidence (≥0.6)

---

## 📦 Installation

```bash
cd agentic-trading

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install fastapi uvicorn pandas numpy pyarrow duckdb python-dateutil pydantic
```

---

## ⚡ Quick Commands

### 1. Start API Server
```bash
uvicorn app:app --reload --port 8000
```
Access at: http://localhost:8000/docs (Swagger UI)

### 2. Generate Test Data
```bash
python generate_test_day.py
```
Creates: `data_l1/l1_2025-11-03.parquet` with 391 1-minute bars

### 3. Run Backtest
```bash
python -m gnosis.backtest --symbol SPY --date 2025-11-03
```

### 4. Process Single Bar (API)
```bash
curl -X POST "http://localhost:8000/run_bar/SPY?price=451.62&bar=2025-11-03T15:30:00&volume=12500"
```

### 5. Get Historical Features
```bash
curl "http://localhost:8000/features/SPY?bar=2025-11-03T15:30:00"
```

---

## 📊 Data Flow (60 seconds)

```
Raw Vendor Data (L0)
    ↓ [normalize time/symbol/units]
L1 Thin (Parquet)
    ↓ [compute features]
L3 Features (Hedge + Liquidity + Sentiment)
    ↓ [build agent views]
3 Agent Views (dir_bias, confidence, thesis)
    ↓ [2-of-3 voting]
Trade Idea (take/pass, direction, size, stops)
    ↓ [backtest execution]
P&L & Performance Metrics
```

---

## 🎯 Key Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Health check |
| `/run_bar/{symbol}` | POST | Process bar & generate idea |
| `/features/{symbol}` | GET | Retrieve L3 features (PIT) |
| `/ideas/log` | POST | Log trade idea |
| `/ideas/log` | GET | Retrieve logged ideas |
| `/ingest/l1thin` | POST | Ingest vendor data to L1 |

---

## 🔧 Configuration

### Symbol Mapping
Edit `gnosis/ingest/config.py`:
```python
SYMBOL_MAP = {
    "SPY.P": "SPY",
    "SPX": "SPX",
    # Add your vendor symbols here
}
```

### Timezone
```python
VENDOR_TIMEZONE = "America/New_York"  # Default: NYSE
```

### Feature Version
Current: `v0.1.0`  
Increment when changing engine logic to maintain history.

---

## 📁 Key Files

| File | Purpose |
|------|---------|
| `app.py` | FastAPI orchestrator (main entry point) |
| `gnosis/schemas/base.py` | Data models (L1, L3, Features) |
| `gnosis/engines/` | Feature computation (3 engines) |
| `gnosis/agents/agents_v1.py` | Agent views + composer |
| `gnosis/backtest/replay_v0.py` | Event-time backtest |
| `gnosis/feature_store/store.py` | Parquet storage with PIT reads |

---

## 🧪 Test Data Structure

After running `generate_test_day.py`:

```
data_l1/
└── l1_2025-11-03.parquet          # 391 bars, columns: t_event, symbol, price, volume

data/
└── date=2025-11-03/
    └── symbol=SPY/
        └── feature_set_id=v0.1.0/
            └── features.parquet    # L3 features per bar
```

---

## 🎓 Understanding Agent Views

### Example View
```python
AgentView(
    agent="hedge",              # Which agent (hedge/liquidity/sentiment)
    dir_bias=1.0,               # -1=short, 0=neutral, +1=long
    confidence=0.78,            # 0-1 conviction level
    thesis="breakout_up",       # Human-readable reasoning
    notes="hedge_force=0.34"    # Debug info
)
```

### Composer Decision
- **Need:** 2+ agents with `confidence >= 0.6` pointing same way
- **Edge:** Winning side must have 20% score advantage
- **Output:** `take_trade=True/False`, direction, sizing hint, time stop

---

## 🔍 Interpreting Backtest Results

```json
{
    "pnl": 12.45,                    // Realized P&L for the day
    "num_trades": 3,                 // Number of round trips
    "win_rate": 0.667,               // 2 winners out of 3
    "avg_win": 8.20,                 // Average winning trade
    "avg_loss": -3.50,               // Average losing trade
    "sharpe_like_intraday": 1.82,    // Annualized intraday Sharpe
    "max_drawdown": 4.30             // Largest peak-to-trough drop
}
```

**Zero Trades on Synthetic Data?**  
Expected! Synthetic data lacks realistic signal correlation. The 2-of-3 alignment requirement is correctly filtering out weak signals.

---

## 📈 Feature Metrics Cheat Sheet

### Liquidity Engine
- **Amihud:** `1e-11` (very liquid) to `1e-8` (illiquid)
- **Kyle Lambda:** Higher = steeper price impact
- **Zones:** Support below price, resistance above

### Hedge Engine
- **Hedge Force:** `-1` to `+1` (dealer positioning pressure)
- **Regime:** `pin` (sticky) | `neutral` | `breakout` (volatile)
- **Gamma Wall:** Distance to high-OI strike

### Sentiment Engine
- **Momentum Z:** Positive = bullish trend, negative = bearish
- **Vol Z:** Positive = elevated vol (stress), negative = suppressed
- **Regime:** `risk_on` | `neutral` | `risk_off`
- **Flip Prob:** Probability of regime change in next 10 bars

---

## 🚨 Common Issues

### "No features for symbol on date"
→ Run `/run_bar` to generate features first, or check `data/` directory

### "Backtest returns 0 trades"
→ Expected with synthetic data. Try real market data or loosen alignment rules.

### "Parquet file not found"
→ Run `generate_test_day.py` to create test data

### API returns 500 error
→ Check logs for validation errors in request payload

---

## 🎯 Next Steps (Pick One)

### **A. Add TP/SL from Zones** ⭐ Recommended
Wire liquidity zones into exits:
- Take profit at next resistance (long) or support (short)
- Stop loss behind nearest opposing zone
- Reduces time-based exits, improves risk/reward

### **B. Real Data Integration** 🔥 Highest Value
Connect to Polygon.io or Alpha Vantage:
- Replace synthetic bars with real 1-min data
- Pull actual options chain (CBOE/OPRA)
- Validate signals on historical dates

### **C. Options Builder**
Turn equity ideas into vertical spreads:
- Bull call spread for long ideas
- Bear put spread for short ideas
- Strike selection from liquidity zones

### **D. Champion/Challenger**
A/B test different composer rules:
- Compare "2-of-3" vs "weighted majority" vs "require 3-of-3"
- Track metrics per rule set
- Promote winner automatically

---

## 📚 Further Reading

- **Full Architecture:** See `ARCHITECTURE_REPORT.md` (40 pages)
- **API Docs:** http://localhost:8000/docs (when server running)
- **Code Comments:** All engines have docstrings

---

## 🆘 Getting Help

**Check Logs:**
```bash
# API logs (if running with uvicorn)
tail -f uvicorn.log

# Backtest output
python -m gnosis.backtest --symbol SPY --date 2025-11-03 2>&1 | tee backtest.log
```

**Debug Single Bar:**
```python
from gnosis.engines.liquidity_v0 import compute_liquidity_v0
import pandas as pd
from datetime import datetime

df = pd.DataFrame({
    "t_event": pd.date_range("2025-11-03 09:30", periods=60, freq="1min"),
    "price": [450.0] * 60,
    "volume": [2000] * 60
})

liq = compute_liquidity_v0("SPY", datetime.now(), df)
print(liq.model_dump_json(indent=2))
```

---

*Last Updated: 2025-11-03*  
*System Version: v0.1.0*
