# Sandbox Testing Guide - Comparative Backtest

## 🎯 **The Smart Way: Test Before Integration**

You now have **comparative backtest harness** that lets you A/B test different agent configurations **without touching production code**.

---

## 📊 **What Gets Compared**

### **6 Strategy Variants:**

| # | Strategy | Agents | Voting | Threshold | Purpose |
|---|----------|--------|--------|-----------|---------|
| 1 | **Baseline** | 3 | 2-of-3 | 0.6 | Your current system |
| 2 | **Conservative** | 3 | 3-of-3 | 0.7 | Require unanimous agreement |
| 3 | **Wyckoff Enhanced** | 4 | 3-of-4 | 0.6 | Add smart money signals |
| 4 | **Markov Enhanced** | 4 | 3-of-4 | 0.6 | Add HMM regime detection |
| 5 | **Full 5-Agent** | 5 | 3-of-5 | 0.6 | All perspectives |
| 6 | **Full 5-Agent Strict** | 5 | 4-of-5 | 0.65 | Ultra-high conviction |

---

## 🚀 **Quick Start (2 Minutes)**

### **Run Comparison:**

```bash
# With test data (already generated)
./run_comparison.sh SPY 2025-11-03

# Or with Python directly
python -m gnosis.backtest.comparative_backtest SPY 2025-11-03
```

### **Expected Output:**

```
🔄 Running: 3-Agent Baseline
   Original 2-of-3 system
   ✅ PnL: 0.00, Trades: 0, Win Rate: 0.0%

🔄 Running: 3-Agent Conservative
   Require unanimous agreement with high confidence
   ✅ PnL: 0.00, Trades: 0, Win Rate: 0.0%

🔄 Running: 4-Agent + Wyckoff
   Add Wyckoff for reversal detection
   ✅ PnL: 12.45, Trades: 3, Win Rate: 66.7%

🔄 Running: 4-Agent + Markov
   Add Markov for regime probability
   ✅ PnL: 8.20, Trades: 2, Win Rate: 50.0%

🔄 Running: 5-Agent Full
   All 5 agents with 3-of-5 voting
   ✅ PnL: 15.30, Trades: 2, Win Rate: 100.0%

🔄 Running: 5-Agent Strict
   All 5 agents with 4-of-5 voting (high conviction only)
   ✅ PnL: 10.10, Trades: 1, Win Rate: 100.0%

============================================================
  RESULTS SUMMARY
============================================================

              name    pnl  num_trades  win_rate  avg_win  avg_loss  sharpe  max_dd  rank
    5-Agent Full  15.30           2     1.000     7.65      0.00   2.150    0.00   1.0
 4-Agent Wyckoff  12.45           3     0.667     8.20     -3.50   1.820    4.30   2.0
5-Agent Strict   10.10           1     1.000    10.10      0.00   1.650    0.00   3.0
 4-Agent Markov   8.20           2     0.500     8.20      0.00   1.420    0.00   4.0
  3-Agent Base    0.00           0     0.000     0.00      0.00   0.000    0.00   5.0
   Conservative    0.00           0     0.000     0.00      0.00   0.000    0.00   6.0

🏆 WINNER: 5-Agent Full
   Sharpe: 2.150
   PnL: $15.30
   Trades: 2
   Win Rate: 100.0%
```

**Note:** With synthetic data, expect 0 trades for baseline (as we saw). The enhanced configs with Wyckoff/Markov may catch different signals.

---

## 📈 **Understanding the Results**

### **Key Metrics:**

- **PnL** - Total profit/loss (higher is better)
- **Num Trades** - How many round trips (more signal = more opportunities OR overtrading)
- **Win Rate** - % winning trades (quality of signals)
- **Sharpe** - Risk-adjusted returns (most important!)
- **Max DD** - Largest drawdown (risk metric)
- **Rank** - Overall ranking by Sharpe

### **What to Look For:**

1. **Signal Quality vs Quantity**
   - Fewer trades but higher win rate = good filtering
   - Many trades with low win rate = noisy signals

2. **Sharpe Ratio**
   - > 1.5 = Excellent
   - 1.0-1.5 = Good
   - < 1.0 = Poor risk-adjusted returns

3. **Consistency**
   - Run on multiple dates
   - Best strategy should win consistently

4. **Risk Metrics**
   - Lower max drawdown = safer
   - Higher win rate = more predictable

---

## 🔬 **Testing Protocol**

### **Phase 1: Single Day Test (5 minutes)**

```bash
# Test with your synthetic data
./run_comparison.sh SPY 2025-11-03
```

**What you'll learn:**
- Do Wyckoff/Markov find different signals than baseline?
- Which configuration has best Sharpe?
- Are there too many/too few trades?

---

### **Phase 2: Multi-Day Test (30 minutes)**

```bash
# Generate more test days first
python generate_test_day.py --date 2025-11-04
python generate_test_day.py --date 2025-11-05
python generate_test_day.py --date 2025-11-06

# Run comparison on each
for date in 2025-11-03 2025-11-04 2025-11-05 2025-11-06; do
    echo "Testing $date..."
    ./run_comparison.sh SPY $date
done
```

**What you'll learn:**
- Which strategy is consistently best?
- Does one config work in some regimes but not others?
- Signal stability across different market conditions

---

### **Phase 3: Real Data Test (Once integrated)**

```bash
# After connecting to Polygon.io or your data vendor
./run_comparison.sh SPY 2025-10-15  # Real historical date
./run_comparison.sh SPY 2025-10-16
./run_comparison.sh SPY 2025-10-17
# ... etc
```

**What you'll learn:**
- Real-world performance
- Which agents add value with actual market microstructure
- Production-ready configuration

---

## 🎯 **Decision Framework**

### **If Baseline Wins:**
- ✅ Keep current 3-agent system
- ✅ Wyckoff/Markov don't add value (yet)
- 💡 Maybe need better calibration or different parameters

### **If Wyckoff Enhanced Wins:**
- ✅ Integrate Wyckoff as Agent 4
- ✅ Use 3-of-4 voting
- 💡 Smart money signals are valuable

### **If Markov Enhanced Wins:**
- ✅ Integrate Markov as Agent 4
- ✅ Use 3-of-4 voting
- 💡 Probabilistic regime detection helps

### **If Full 5-Agent Wins:**
- ✅ Integrate both Wyckoff + Markov
- ✅ Use 3-of-5 or 4-of-5 voting (test both)
- 💡 Multiple perspectives improve signals

### **If Conservative Wins:**
- ✅ Tighten existing system (3-of-3 voting)
- ✅ Raise confidence threshold to 0.7
- 💡 You have signal quality issues, not quantity issues

---

## 🛠️ **Customizing Strategy Configs**

Edit `gnosis/backtest/comparative_backtest.py`:

```python
STRATEGIES = {
    "my_custom": StrategyConfig(
        name="My Custom Strategy",
        agents=["hedge", "liquidity", "wyckoff"],  # Pick agents
        alignment_threshold=2,  # How many must agree
        high_conf_threshold=0.65,  # Confidence cutoff
        reliability_weights={
            "hedge": 1.0,
            "liquidity": 1.2,  # Trust liquidity more
            "wyckoff": 1.1
        },
        description="Trust liquidity + Wyckoff reversal signals"
    ),
}
```

Then run:
```bash
python -m gnosis.backtest.comparative_backtest SPY 2025-11-03
```

---

## 📊 **Interpreting with Synthetic Data**

**Important:** Synthetic data is **random walks**, so:
- Baseline may get 0 trades (correct - no real signals)
- Enhanced configs may find spurious patterns
- **Don't trust absolute P&L numbers yet**

**What you CAN learn:**
- How each config behaves differently
- Trade frequency differences
- Confidence calibration
- Agent agreement patterns

**What you CANNOT learn:**
- Actual edge (need real data)
- Real win rates (need real market dynamics)
- Production profitability (need realistic signals)

---

## 🚀 **Next Steps After Testing**

### **Option A: Wyckoff/Markov Win → Integrate**

Follow `WYCKOFF_MARKOV_INTEGRATION.md` to wire them in permanently.

### **Option B: Baseline Wins → Keep As-Is**

Focus on Option A (TP/SL from zones) or Option B (real data) instead.

### **Option C: Mixed Results → Regime-Dependent**

Implement **adaptive agent selection**:
```python
# In production, toggle agents based on market regime
if vix > 25:  # High volatility
    use_agents = ["hedge", "liquidity", "markov"]  # Probabilistic works better
else:  # Normal volatility
    use_agents = ["hedge", "liquidity", "sentiment", "wyckoff"]
```

---

## 🔄 **Continuous Testing**

**Recommended cadence:**
1. **Before integrating Wyckoff/Markov:** Run comparison on 5+ days
2. **After integration:** Run weekly on new data to validate
3. **On edge degradation:** Re-run comparison to diagnose which agent is broken
4. **On parameter changes:** Always compare before/after

---

## 🎓 **Advanced: Calibration Loop**

Once you have the winner, fine-tune it:

```python
# Test different confidence thresholds
for thresh in [0.5, 0.55, 0.6, 0.65, 0.7]:
    config = StrategyConfig(
        name=f"Wyckoff_conf_{thresh}",
        agents=["hedge", "liquidity", "sentiment", "wyckoff"],
        alignment_threshold=3,
        high_conf_threshold=thresh,
        reliability_weights={...}
    )
    result = backtest_strategy("SPY", "2025-11-03", config)
    # Track which threshold gives best Sharpe
```

---

## 📝 **Output Files**

Each run creates:
```
comparative_backtest_SPY_2025-11-03.json
```

Contains:
- Full results for all strategies
- Trade-by-trade details
- Equity curves
- Agent view logs

**Use this to:**
- Debug why a strategy won/lost
- See which agents agreed/disagreed on each bar
- Identify patterns (e.g., Wyckoff always right at reversals)

---

## 🏆 **Success Criteria**

**Green Light to Integrate:**
- ✅ Wyckoff/Markov config wins on 3+ different days
- ✅ Sharpe improvement > 20% vs baseline
- ✅ Win rate improvement > 10%
- ✅ Consistent behavior across market conditions

**Yellow Light (Calibrate First):**
- ⚠️ Wins on some days, loses on others
- ⚠️ Marginal improvement (< 10%)
- ⚠️ High trade count suggests overfitting

**Red Light (Don't Integrate):**
- ❌ Baseline wins consistently
- ❌ No improvement in Sharpe
- ❌ More trades but lower win rate

---

## 🎯 **Your Decision Point**

Based on your comparative backtest results:

1. **If Enhanced Configs Win:**
   → Proceed with full integration (30-45 min)
   → Use `WYCKOFF_MARKOV_INTEGRATION.md` as guide

2. **If Baseline Wins:**
   → Keep current system
   → Focus on Option A (TP/SL) or Option B (real data) instead

3. **If Results Are Mixed:**
   → Test on more days
   → Try adjusting reliability weights
   → Consider regime-dependent agent selection

---

**You're taking the professional approach: measure twice, cut once.** 🎯

Run the comparison now to see which path forward is best for your system!

```bash
./run_comparison.sh SPY 2025-11-03
```
