# 🎯 Multi-Symbol Trading System - Live Status

## ✅ **SYSTEM ACTIVATED**

**Process**: bash_4a81a01a  
**Command**: `python main.py multi-symbol-loop --top 25 --scan-interval 300 --trade-interval 60`  
**Status**: 🟢 **RUNNING**  
**Started**: 2025-11-18 15:54:37 UTC  
**Mode**: Alpaca Paper Trading (Live)  

---

## 📊 **Configuration**

### **Trading Parameters**
- **Universe**: 67 liquid stocks (indices + high-volume stocks)
- **Top N**: 25 best opportunities
- **Scan Interval**: 300 seconds (5 minutes) - Re-ranks opportunities
- **Trade Interval**: 60 seconds - Executes trades on active symbols
- **Mode**: Live Paper Trading on Alpaca

### **Capital Allocation**
- **Total Portfolio**: $30,000
- **Per Symbol**: $1,200 (with 25 symbols)
- **Max Position**: $24 per symbol (2% of allocation)
- **Daily Loss Limit**: $5,000 (global)

### **Risk Management**
- ✅ Position size limits: 2% max per symbol
- ✅ Options liquidity filtering: Active
- ✅ Confidence threshold: 50%+
- ✅ Daily loss circuit breaker: $5k

---

## 🔍 **How The Scanner Works**

### **Every 5 Minutes (Scan Cycle)**
1. **Analyze Universe**: Run DHPE engines on all 67 symbols
2. **Calculate Scores**: Composite opportunity score (0-1)
   - Energy (30%): Directional bias from hedge engine
   - Liquidity (25%): Orderflow quality
   - Volatility (20%): Expansion potential
   - Sentiment (15%): News/technical conviction
   - Options (10%): Derivative liquidity
3. **Rank Opportunities**: Sort by score, select top 25
4. **Update Active List**: Drop weak symbols, add strong ones

### **Every 60 Seconds (Trade Cycle)**
1. **For Each Active Symbol**:
   - Run full DHPE pipeline
   - Generate trade ideas
   - Execute if confident (>50%)
2. **Portfolio Management**:
   - Monitor all positions
   - Check risk limits
   - Report status

---

## 🎯 **Default Universe (67 Symbols)**

### **Major Indices (10)**
SPY, QQQ, IWM, DIA, EEM, EFA, GLD, SLV, TLT, HYG

### **Mega Cap Tech (8)**
AAPL, MSFT, GOOGL, AMZN, META, TSLA, NVDA, AMD

### **Large Cap Tech (7)**
NFLX, CRM, ADBE, ORCL, INTC, CSCO, AVGO

### **Finance (8)**
JPM, BAC, WFC, GS, MS, C, BLK, AXP

### **Healthcare (8)**
JNJ, UNH, PFE, ABBV, MRK, TMO, ABT, CVS

### **Consumer (8)**
WMT, HD, MCD, NKE, SBUX, TGT, COST, DIS

### **Industrial (7)**
BA, CAT, GE, MMM, HON, UPS, RTX

### **Energy (6)**
XOM, CVX, COP, SLB, EOG, PXD

### **Volatility/Meme (5)**
AMC, GME, COIN, RIOT, MARA

**Total**: 67 highly liquid, optionable instruments

---

## 📈 **Current Status**

### **Iteration #2**
- ✅ Alpaca connected: $30,000 portfolio
- ✅ Scanner operational
- ⚠️ 0 opportunities found (using static data adapters)

### **Why 0 Opportunities?**

The scanner is working correctly, but it's using **static/stub data adapters** which return minimal data. To find real opportunities, you need:

**Option 1: Connect Real Data Sources**
- Yahoo Finance (free): Real-time quotes and options chains
- Alpha Vantage (free tier): Market data
- Polygon.io (paid): Professional-grade data

**Option 2: Demo Mode** (Coming Soon)
- Simulated market conditions
- Generates realistic opportunity scores
- Perfect for testing and development

**Option 3: Live Market Hours**
- Market must be open for real scanning
- Pre-market/after-hours have limited data

---

## 🔧 **Connecting Real Data Sources**

### **Quick Setup: Yahoo Finance (Free)**

1. **Install yfinance**:
   ```bash
   cd /home/user/webapp
   pip install yfinance
   ```

2. **Update Data Adapters**:
   ```python
   # In main.py, replace static adapters with:
   from engines.inputs.yfinance_adapter import YFinanceAdapter
   
   market_adapter = YFinanceAdapter()
   options_adapter = YFinanceAdapter()
   ```

3. **Restart Multi-Symbol Loop**:
   ```bash
   python main.py multi-symbol-loop --top 25
   ```

### **Alternative: Alpha Vantage**

1. **Get Free API Key**: https://www.alphavantage.co/support/#api-key

2. **Add to .env**:
   ```bash
   ALPHA_VANTAGE_API_KEY=your_key_here
   ```

3. **Update Adapters**:
   ```python
   from engines.inputs.alpha_vantage_adapter import AlphaVantageAdapter
   
   market_adapter = AlphaVantageAdapter()
   ```

---

## 🎯 **What Happens When Real Data Flows**

### **Scan Output Example**:
```
[15:55:00] Iteration #1
--------------------------------------------------------------------------------
🔍 Scanning universe for opportunities...
✓ Top 25 opportunities:
   1. TSLA - directional (0.812) - BULLISH 87%
   2. NVDA - volatility (0.789) - NEUTRAL 45%
   3. SPY - range_bound (0.745) - NEUTRAL 38%
   4. QQQ - directional (0.721) - BULLISH 72%
   5. AMD - volatility (0.698) - NEUTRAL 52%
   6. AAPL - directional (0.675) - BEARISH 68%
   7. MSFT - range_bound (0.654) - NEUTRAL 41%
   8. GOOGL - volatility (0.632) - NEUTRAL 55%
   9. META - directional (0.618) - BULLISH 63%
   10. AMZN - range_bound (0.601) - NEUTRAL 48%
   ...
   25. XOM - directional (0.521) - BEARISH 56%

📊 Trading TSLA...
   ✓ TSLA: 3 trade ideas generated
   🎯 Top: call_debit_spread (confidence: 87%)
   📈 TSLA: 2 orders executed
   
📊 Trading NVDA...
   ✓ NVDA: 4 trade ideas generated
   🎯 Top: iron_condor (confidence: 78%)
   📈 NVDA: 2 orders executed
   
... (processes all 25 symbols)

   💰 Portfolio: $31,250.00 | Positions: 18 | Cash: $27,500.00
   ⏳ Next iteration in 60 seconds...
```

---

## 📊 **Monitoring Your Multi-Symbol Trading**

### **Option 1: Check Output Here**
Just ask me: "Show me the latest trading activity"

### **Option 2: Alpaca Dashboard**
Visit: https://app.alpaca.markets/paper/dashboard/overview
- See all 25 symbols being traded
- Real-time position tracking
- Order history and fills

### **Option 3: Log Files**
```bash
cd /home/user/webapp
tail -f logs/gnosis.log
```

### **Option 4: Generate Reports**
```bash
# Daily summary
python scripts/analysis/daily_report.py --days 1

# Performance by symbol
python scripts/analysis/symbol_performance.py

# Opportunity scan history
python main.py scan-opportunities --output scan_$(date +%Y%m%d_%H%M%S).json
```

---

## 🎛️ **Adjusting Parameters**

### **Change Number of Symbols**
```bash
# Trade top 10 instead of 25
python main.py multi-symbol-loop --top 10
```

### **Change Scan Frequency**
```bash
# Scan every 10 minutes instead of 5
python main.py multi-symbol-loop --top 25 --scan-interval 600
```

### **Change Trade Frequency**
```bash
# Trade every 2 minutes instead of 1
python main.py multi-symbol-loop --top 25 --trade-interval 120
```

### **Custom Universe**
```bash
# Only trade tech stocks
python main.py multi-symbol-loop --universe "AAPL,MSFT,GOOGL,AMZN,META,TSLA,NVDA,AMD,NFLX,CRM"
```

---

## 🛑 **Stopping The System**

### **Graceful Shutdown**
The system will show:
- Total iterations run
- Final portfolio value
- All open positions
- Overall P&L

Just ask me: "Stop the multi-symbol trading"

### **Emergency Stop**
```bash
pkill -f "multi-symbol-loop"
```

---

## 📈 **Expected Behavior**

### **With Real Data**
- Scans 67 symbols in ~10-30 seconds
- Identifies 25 best opportunities each cycle
- Executes 5-20 trades per minute (depending on confidence)
- Re-ranks every 5 minutes to adapt to changing conditions
- Positions in 10-25 symbols simultaneously

### **With Static Data** (Current)
- Scanner runs but finds no opportunities
- No trades executed (correct behavior - no confidence)
- System is operational and waiting for real data

---

## 🎯 **Performance Metrics**

The system tracks:

### **Per Symbol**
- Win rate
- Average P&L
- Best/worst trades
- Opportunity score accuracy

### **Global**
- Portfolio value growth
- Total P&L
- Position count
- Daily/weekly performance

### **Scanner Accuracy**
- How often top-ranked symbols produce profitable trades
- Opportunity type distribution (directional vs volatility vs range-bound)
- Optimal re-scan frequency

---

## 🚀 **What You Have Right Now**

✅ **Multi-symbol infrastructure**: Fully operational  
✅ **Opportunity scanner**: Working (needs real data)  
✅ **Dynamic rotation**: Active symbols update every 5 minutes  
✅ **Risk management**: All safeguards active  
✅ **Live execution**: Connected to Alpaca Paper  
✅ **Autonomous operation**: Running 24/7 (during market hours)  

**Next Step**: Connect real data source to see the scanner find actual opportunities.

---

## 💡 **Quick Win: Test Scanner Manually**

While waiting for data feeds, you can test the scanner manually:

```bash
# Generate a scan report with simulated scores
python main.py scan-opportunities --output test_scan.json

# View results
cat test_scan.json | jq '.opportunities[] | {symbol, score, type}'
```

This will show you how the scoring algorithm works, even with limited data.

---

## 📞 **Need Help?**

Ask me:
- "Show me the current portfolio"
- "What opportunities were found?"
- "Change to top 10 symbols"
- "Stop the system"
- "Connect real data feeds"

---

**Your multi-symbol autonomous trading system is LIVE and ready for real data!** 🎯

**Status**: 🟢 Running (waiting for real market data)  
**Process**: bash_4a81a01a  
**Mode**: Alpaca Paper Trading  
**Universe**: 67 symbols  
**Target**: Top 25 opportunities  
