# Multi-Symbol Trading Guide

## 🎯 Overview

Super Gnosis V2 now supports **multi-symbol trading** with intelligent opportunity scanning across your entire watchlist.

The system can:
- ✅ Scan 25+ symbols simultaneously
- ✅ Rank opportunities using DHPE physics
- ✅ Trade top N symbols in rotation
- ✅ Re-scan periodically to adapt to market changes
- ✅ Optimize capital allocation across symbols

---

## 🚀 New Commands

### 1. **Opportunity Scanner** (`scan-opportunities`)

Scans multiple symbols and ranks them by trading opportunity quality.

```bash
# Scan default universe (75 liquid stocks)
python main.py scan-opportunities

# Top 10 opportunities with minimum score 0.6
python main.py scan-opportunities --top 10 --min-score 0.6

# Custom symbol list
python main.py scan-opportunities --universe "SPY,QQQ,AAPL,TSLA,NVDA,AMD,GOOGL,META"

# Save results to file
python main.py scan-opportunities --output opportunities.json
```

**What It Does**:
- Runs DHPE engines on each symbol
- Calculates composite opportunity score (0-1)
- Ranks by: energy asymmetry, liquidity, volatility, sentiment, options activity
- Identifies opportunity type: directional, volatility, range_bound, gamma_squeeze

**Output Example**:
```
#1 TSLA - Score: 0.782
   Type: DIRECTIONAL
   Direction: BULLISH (confidence: 85%)
   Energy: +12.3 | Movement: 1450
   Liquidity: 0.82 | Options: 0.91
   Strong directional bias detected | High energy asymmetry (bullish) | Excellent liquidity

#2 NVDA - Score: 0.745
   Type: VOLATILITY
   Direction: NEUTRAL (confidence: 45%)
   Energy: -2.1 | Movement: 980
   Liquidity: 0.88 | Options: 0.87
   Volatility expansion opportunity | Excellent liquidity

#3 SPY - Score: 0.698
   Type: RANGE_BOUND
   Direction: NEUTRAL (confidence: 35%)
   Energy: +1.5 | Movement: 320
   Liquidity: 0.95 | Options: 0.93
   Range-bound, premium selling opportunity | Excellent liquidity
```

---

### 2. **Multi-Symbol Autonomous Loop** (`multi-symbol-loop`)

Runs autonomous trading on multiple symbols simultaneously.

```bash
# Trade top 5 opportunities (re-scan every 5 minutes)
python main.py multi-symbol-loop

# Top 10, scan every 10 minutes, trade every 90 seconds
python main.py multi-symbol-loop --top 10 --scan-interval 600 --trade-interval 90

# Dry-run mode (test without execution)
python main.py multi-symbol-loop --dry-run

# Custom universe
python main.py multi-symbol-loop --universe "SPY,QQQ,IWM,AAPL,TSLA,NVDA,AMD,GOOGL,META,AMZN"
```

**How It Works**:

1. **Initial Scan** (every {scan_interval} seconds, default 300):
   - Scans entire universe
   - Ranks opportunities using DHPE
   - Selects top N symbols

2. **Trading Cycle** (every {trade_interval} seconds, default 60):
   - Runs full pipeline for each active symbol
   - Generates trade ideas
   - Executes when confident (>50%)

3. **Re-Scan & Adapt**:
   - Periodically re-scans universe
   - Drops symbols with declining opportunities
   - Adds new emerging opportunities
   - Dynamic portfolio rebalancing

**Output Example**:
```
[15:30:00] Iteration #1
--------------------------------------------------------------------------------
🔍 Scanning universe for opportunities...
✓ Top 5 opportunities:
   1. TSLA - directional (0.782)
   2. NVDA - volatility (0.745)
   3. SPY - range_bound (0.698)
   4. QQQ - directional (0.672)
   5. AMD - volatility (0.645)

📊 Trading TSLA...
   ✓ TSLA: 3 trade ideas generated
   📈 TSLA: 1 orders executed
📊 Trading NVDA...
   ✓ NVDA: 4 trade ideas generated
   📈 NVDA: 2 orders executed
📊 Trading SPY...
   ✓ SPY: 2 trade ideas generated
📊 Trading QQQ...
   ✓ QQQ: 3 trade ideas generated
   📈 QQQ: 1 orders executed
📊 Trading AMD...
   ✓ AMD: 2 trade ideas generated

   💰 Portfolio: $32,150.00 | Positions: 8
   ⏳ Next iteration in 60 seconds...
```

---

## 🎯 Opportunity Scoring

The scanner uses a **composite score (0-1)** based on:

### Component Scores (weighted)

1. **Energy Score (30%)**: 
   - High energy asymmetry = directional opportunity
   - High movement energy = active opportunity
   - Formula: `0.7 * (asymmetry/10) + 0.3 * (energy/1000)`

2. **Liquidity Score (25%)**:
   - From Liquidity Engine
   - Measures orderflow, absorption, displacement
   - >0.7 = excellent, <0.4 = caution

3. **Volatility Score (20%)**:
   - Gamma regime (negative = expansion)
   - Elasticity (low = easy to move)
   - Detects breakout potential

4. **Sentiment Score (15%)**:
   - Sentiment strength × confidence
   - Strong conviction = opportunity
   - Neutral sentiment = range-bound

5. **Options Score (10%)**:
   - Open interest and volume
   - Liquid options = better execution
   - >500 OI avg = good

### Opportunity Types

**DIRECTIONAL** (asymmetry > 10):
- Strong bias in one direction
- Best for: Debit spreads, outright options
- Trade: In direction of bias

**VOLATILITY** (high energy, low asymmetry):
- Expansion potential
- Best for: Straddles, strangles
- Trade: Sell when expanding, buy when compressing

**RANGE_BOUND** (low energy):
- Stable price action
- Best for: Iron condors, credit spreads
- Trade: Premium selling

**GAMMA_SQUEEZE** (gamma regime indicators):
- Potential explosive move
- Best for: Directional, tight stops
- Trade: Direction of squeeze

---

## 📊 Default Universe

The scanner includes **75 highly liquid, optionable stocks**:

### Major Indices & ETFs (10)
SPY, QQQ, IWM, DIA, EEM, EFA, GLD, SLV, TLT, HYG

### Mega Cap Tech (8)
AAPL, MSFT, GOOGL, AMZN, META, TSLA, NVDA, AMD

### Large Cap Tech (7)
NFLX, CRM, ADBE, ORCL, INTC, CSCO, AVGO

### Finance (8)
JPM, BAC, WFC, GS, MS, C, BLK, AXP

### Healthcare (8)
JNJ, UNH, PFE, ABBV, MRK, TMO, ABT, CVS

### Consumer (8)
WMT, HD, MCD, NKE, SBUX, TGT, COST, DIS

### Industrial (7)
BA, CAT, GE, MMM, HON, UPS, RTX

### Energy (6)
XOM, CVX, COP, SLB, EOG, PXD

### Volatility & Meme (5)
AMC, GME, COIN, RIOT, MARA

---

## ⚙️ Configuration

Add to `config/config.yaml`:

```yaml
scanner:
  default_universe: "default"  # or "sp500", "nasdaq100", "custom"
  top_n: 25                     # Top opportunities to consider
  min_score: 0.5                # Minimum opportunity score
  scan_interval_seconds: 300    # 5 minutes
  trade_interval_seconds: 60    # 1 minute per symbol
  
  filters:
    min_price: 10.0             # Minimum stock price
    max_price: 1000.0           # Maximum stock price
    min_volume: 1_000_000       # Minimum daily volume
    min_option_oi: 100          # Minimum option OI
  
  weights:
    energy: 0.30                # Energy asymmetry weight
    liquidity: 0.25             # Liquidity quality weight
    volatility: 0.20            # Volatility regime weight
    sentiment: 0.15             # Sentiment strength weight
    options: 0.10               # Options activity weight
```

---

## 🚦 Usage Patterns

### Pattern 1: Morning Scan + Day Trading
```bash
# Morning: Scan for opportunities
python main.py scan-opportunities --output morning_scan.json

# Review results, pick top 5-10

# Day: Trade selected symbols
python main.py multi-symbol-loop --universe "TSLA,NVDA,SPY,QQQ,AMD" --top 5
```

### Pattern 2: Continuous Multi-Symbol Trading
```bash
# Autonomous: Scan + trade continuously
python main.py multi-symbol-loop --top 10
```

### Pattern 3: Focused High-Conviction
```bash
# Scan for top 3 highest-confidence opportunities
python main.py scan-opportunities --top 3 --min-score 0.7

# Trade those 3 aggressively
python main.py multi-symbol-loop --universe "TOP3SYMBOLS" --trade-interval 30
```

### Pattern 4: Diversified Portfolio
```bash
# Trade top 15 symbols with longer intervals
python main.py multi-symbol-loop --top 15 --scan-interval 600 --trade-interval 120
```

---

## 📈 Capital Allocation

### Single Symbol Mode
- 100% capital available for one symbol
- Max 2% position size
- Max $5k daily loss

### Multi-Symbol Mode (N symbols)
- Capital divided by N (e.g., 5 symbols = 20% each)
- Each symbol gets its own allocation
- Global daily loss limit still applies
- Position size limits per symbol

**Example** ($100k portfolio, 5 symbols):
- Each symbol: $20k allocation
- Max position per symbol: $400 (2% of $20k)
- Global stop: $5k total loss across all symbols

---

## 🎯 When to Use Each Mode

### Single Symbol (`live-loop`)
**Use when**:
- High conviction on ONE opportunity
- Want to concentrate capital
- Learning/testing new strategy
- Market has clear dominant theme

**Best for**: SPY, QQQ during strong trends

### Multi-Symbol (`multi-symbol-loop`)
**Use when**:
- Multiple opportunities exist
- Want diversification
- Market has mixed signals
- Reducing concentration risk

**Best for**: Normal market conditions with multiple setups

### Scanner Only (`scan-opportunities`)
**Use when**:
- Morning prep/research
- Building watchlist
- Manual trading
- Identifying market themes

**Best for**: Pre-market analysis, strategy selection

---

## 🔒 Risk Management

### Per-Symbol Limits
- Max 2% position size per symbol
- Options liquidity filtering active
- Confidence threshold (50%+)

### Global Limits
- Max $5k daily loss (across all symbols)
- Max 10 open positions
- Emergency stop on large drawdown

### Diversification
- Max 5-15 symbols recommended
- Avoid concentration in one sector
- Mix directional + volatility + range-bound

---

## 📊 Monitoring

### Check Scanner Output
```bash
# Generate scan report
python main.py scan-opportunities --output scan_$(date +%Y%m%d_%H%M%S).json

# Review top opportunities
cat scan_*.json | jq '.opportunities[] | {symbol, score, type, direction}'
```

### Monitor Multi-Symbol Trading
The loop shows per-symbol activity:
- Trade ideas generated per symbol
- Orders executed per symbol
- Portfolio value and position count
- Upcoming re-scan countdown

### Alpaca Dashboard
https://app.alpaca.markets/paper/dashboard/overview
- View all positions across symbols
- Check order history
- Monitor P&L per symbol

---

## 🎓 Best Practices

### 1. Start Small
- Begin with 3-5 symbols
- Validate scanner accuracy
- Ensure good fill rates

### 2. Monitor Performance
- Track which symbols perform best
- Identify profitable opportunity types
- Adjust weights based on results

### 3. Adapt Scan Frequency
- Fast markets: Scan every 2-3 minutes
- Slow markets: Scan every 10-15 minutes
- Volatile open: Scan every 1 minute

### 4. Use Appropriate Intervals
- Day trading: 30-60 second trade intervals
- Swing trading: 5-10 minute trade intervals
- Position trading: 30+ minute trade intervals

### 5. Diversify Opportunity Types
- Mix: 40% directional + 30% volatility + 30% range-bound
- Don't chase all directional or all volatility
- Balance risk across strategies

---

## 🚀 Next Steps

1. **Test Scanner**:
   ```bash
   python main.py scan-opportunities --universe "SPY,QQQ,AAPL,TSLA,NVDA" --min-score 0.0
   ```

2. **Dry-Run Multi-Symbol**:
   ```bash
   python main.py multi-symbol-loop --top 3 --dry-run
   ```

3. **Start Small Live**:
   ```bash
   python main.py multi-symbol-loop --top 3 --universe "SPY,QQQ,IWM"
   ```

4. **Scale Up Gradually**:
   ```bash
   python main.py multi-symbol-loop --top 10
   ```

---

**You now have a complete multi-symbol trading system powered by DHPE physics!** 🎯
