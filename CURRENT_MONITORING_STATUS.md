# 📊 Super Gnosis Monitoring Status

## Current Symbol Coverage

### Active Monitoring (Live Dashboard)
The Super Gnosis Web Dashboard currently monitors **1 symbol in real-time**:
- **SPY** (S&P 500 ETF) - Default configuration

### Configurable via Environment
You can change the monitored symbol by editing `.env`:
```bash
TRADING_SYMBOL=SPY  # Change to QQQ, AAPL, TSLA, etc.
```

## Multi-Symbol Capabilities

### 🎯 Supported Universe (75 Stocks)
The framework includes a **scanner for 75 highly liquid stocks** across sectors:

#### Major Indices & ETFs (10)
- SPY, QQQ, IWM, DIA, EEM, EFA, GLD, SLV, TLT, HYG

#### Mega Cap Tech (8)
- AAPL, MSFT, GOOGL, AMZN, META, TSLA, NVDA, AMD

#### Large Cap Tech (7)
- NFLX, CRM, ADBE, ORCL, INTC, CSCO, AVGO

#### Finance (8)
- JPM, BAC, WFC, GS, MS, C, BLK, AXP

#### Healthcare (8)
- JNJ, UNH, PFE, ABBV, MRK, TMO, ABT, CVS

#### Consumer (8)
- WMT, HD, MCD, NKE, SBUX, TGT, COST, DIS

#### Industrial (7)
- BA, CAT, GE, MMM, HON, UPS, RTX

#### Energy (6)
- XOM, CVX, COP, SLB, EOG, PXD

#### Volatility & Meme (5)
- AMC, GME, COIN, RIOT, MARA

## Current Trading Modes

### 1. **Single Symbol Mode** (Active Now)
- Monitors and trades ONE symbol (SPY by default)
- 100% capital allocation to single symbol
- Real-time agent voting and position management
- Shown in web dashboard at http://localhost:8000

### 2. **Multi-Symbol Scanner** (Available)
The system includes an **Opportunity Scanner** that can:
- Scan 25+ symbols simultaneously
- Rank opportunities using DHPE physics scoring
- Identify trading opportunities across:
  - **DIRECTIONAL**: Strong bias opportunities
  - **VOLATILITY**: Expansion/compression plays
  - **RANGE_BOUND**: Premium selling opportunities
  - **GAMMA_SQUEEZE**: Explosive move potential

### 3. **Multi-Symbol Trading** (Command-Line)
Available via command line (not in web dashboard yet):
```bash
# Scan opportunities across universe
python main.py scan-opportunities

# Trade top 5 opportunities
python main.py multi-symbol-loop --top 5
```

## Opportunity Scoring System

Each symbol is scored (0-1) based on:
- **Energy Score (30%)**: Directional bias strength
- **Liquidity Score (25%)**: Order flow quality
- **Volatility Score (20%)**: Breakout potential
- **Sentiment Score (15%)**: Market conviction
- **Options Score (10%)**: Derivatives activity

## Current Dashboard Features

### Real-Time Monitoring (SPY)
- **Agent Votes**: See what Hedge, Liquidity, and Sentiment agents think
- **Live Positions**: Track open positions with P&L
- **Regime Detection**: Current market regime (Trending/Range/Volatile)
- **Trade History**: Last 20 trades with details
- **Portfolio Stats**: Capital, equity, win rate

### Health Monitoring
- System status and uptime
- Active positions count
- Current P&L percentage
- Market regime detection
- Memory episodes stored

## Roadmap for Enhanced Monitoring

### Phase 1: Multi-Symbol Dashboard (Next)
- [ ] Add symbol selector dropdown
- [ ] Display top 5 opportunities in sidebar
- [ ] Show scanner results in real-time
- [ ] Multi-symbol position tracking

### Phase 2: Advanced Analytics
- [ ] Per-symbol P&L tracking
- [ ] Correlation matrix view
- [ ] Sector rotation indicators
- [ ] Volume/volatility heatmaps

### Phase 3: Full Portfolio Management
- [ ] Portfolio-wide risk metrics
- [ ] Symbol allocation optimizer
- [ ] Performance attribution
- [ ] Trade journal with tags

## How to Expand Symbol Coverage

### Quick Start: Change Active Symbol
```bash
# Edit .env file
TRADING_SYMBOL=QQQ  # or AAPL, TSLA, etc.

# Restart webapp
python webapp.py
```

### Advanced: Multi-Symbol Trading
```bash
# Use command-line scanner
python main.py scan-opportunities --universe "SPY,QQQ,AAPL,TSLA,NVDA"

# Trade multiple symbols
python main.py multi-symbol-loop --top 5
```

## Summary

**Current State**:
- ✅ **1 symbol** actively monitored (SPY)
- ✅ **75 symbols** available for scanning
- ✅ Real-time dashboard for single symbol
- ✅ Opportunity scanner for universe

**Next Steps**:
1. The web dashboard currently shows **single-symbol trading** (SPY by default)
2. Multi-symbol scanning exists but runs via command-line
3. To monitor different symbols, change `TRADING_SYMBOL` in `.env`
4. Full multi-symbol dashboard integration is planned but not yet implemented

The framework is **ready for multi-symbol trading** but the web dashboard currently focuses on **single-symbol clarity** for better real-time decision making.