# Alpaca Live-Loop Quickstart Guide

## 🎯 What You're About to Do

You're enabling **autonomous paper trading** on Alpaca with Super Gnosis V2. The system will:
- Run every 60 seconds (configurable)
- Analyze SPY using DHPE engines (hedge, liquidity, sentiment, elasticity)
- Generate probabilistic multi-timeframe forecasts
- Create trade ideas (spreads, iron condors, etc.)
- Execute trades on Alpaca Paper Trading
- Track predictions and self-optimize

## ⚡ 5-Minute Setup

### Step 1: Verify Alpaca Credentials

Your `.env` file should already contain:
```bash
ALPACA_API_KEY=PKJ5QEKACMXVZO2Q6AHG2WIXSB
ALPACA_SECRET_KEY=amFC3iYdA7mrAiKivTpMVecM9F9VUcgHL2xPNhUtYau
ALPACA_BASE_URL=https://paper-api.alpaca.markets
```

**Test Connection**:
```bash
python3 << 'EOF'
import sys
sys.path.insert(0, '/home/user/webapp')
from dotenv import load_dotenv
load_dotenv('/home/user/webapp/.env')
from execution.broker_adapters.alpaca_adapter import AlpacaBrokerAdapter

broker = AlpacaBrokerAdapter(paper=True)
account = broker.get_account()
print(f"✅ Connected! Portfolio: ${account.portfolio_value:,.2f}")
EOF
```

### Step 2: Check Configuration

Your `config/config.yaml` is already configured:
```yaml
execution:
  broker: "alpaca_paper"      # Using Alpaca Paper Trading
  mode: "paper"                # Paper mode (not live)
  risk_per_trade_pct: 1.0      # 1% risk per trade
  max_position_size_pct: 2.0   # Max 2% per position
  max_daily_loss_usd: 5000.0   # $5k daily loss limit
  loop_interval_seconds: 60    # 60-second cycle
  enable_trading: true         # Trading enabled
```

### Step 3: Test Dry-Run (Preview Mode)

**Single Iteration**:
```bash
cd /home/user/webapp
python main.py run-once --symbol SPY --dry-run
```

**Continuous Loop (No Execution)**:
```bash
cd /home/user/webapp
python main.py live-loop --symbol SPY --dry-run
# Press Ctrl+C to stop
```

### Step 4: Start Live Paper Trading 🚀

```bash
cd /home/user/webapp
python main.py live-loop --symbol SPY
```

**What Happens**:
```
================================================================================
🚀 AUTONOMOUS TRADING LOOP STARTED
================================================================================
   Symbol: SPY
   Mode: LIVE PAPER TRADING
   Interval: 60 seconds
   Press Ctrl+C to stop
================================================================================

[2025-11-18 15:30:00] Iteration #1
--------------------------------------------------------------------------------
   ✓ Generated 5 trade ideas
   🎯 Top Idea: iron_condor
      Confidence: 72%
   📊 Executed 2 orders
      SPY: FILLED
   💰 Portfolio: $30,250.00 | Cash: $28,750.00
   ⏳ Next iteration in 60 seconds...

[2025-11-18 15:31:00] Iteration #2
...
```

**To Stop**:
- Press `Ctrl+C` to gracefully shutdown
- System shows final portfolio value and P&L

## 🎛️ Commands Reference

### Dry-Run Commands (Preview Only)
```bash
# Single iteration (no execution)
python main.py run-once --symbol SPY --dry-run

# Continuous loop (no execution)
python main.py live-loop --symbol SPY --dry-run

# Custom interval (5 minutes)
python main.py live-loop --symbol SPY --dry-run --interval 300
```

### Live Paper Trading Commands
```bash
# Standard 60-second loop
python main.py live-loop --symbol SPY

# Custom interval (2 minutes)
python main.py live-loop --symbol SPY --interval 120

# Different symbol
python main.py live-loop --symbol QQQ
```

### Alternative: Use Existing Script
```bash
# Dry-run
python scripts/run_daily_spy_paper.py --broker alpaca

# Execute trades
python scripts/run_daily_spy_paper.py --broker alpaca --execute

# Custom capital
python scripts/run_daily_spy_paper.py --broker alpaca --execute --capital 50000
```

## 📊 Monitoring Your Paper Account

### Check Account in Code
```python
from execution.broker_adapters.alpaca_adapter import AlpacaBrokerAdapter

broker = AlpacaBrokerAdapter(paper=True)
account = broker.get_account()

print(f"Portfolio Value: ${account.portfolio_value:,.2f}")
print(f"Cash: ${account.cash:,.2f}")
print(f"P&L: ${account.portfolio_value - 30000:+,.2f}")

# Check positions
positions = broker.get_positions()
for pos in positions:
    print(f"{pos.symbol}: {pos.quantity} @ ${pos.avg_entry_price:.2f}")
    print(f"  P&L: ${pos.unrealized_pnl:+,.2f}")
```

### Check Account in Dashboard
Visit: https://app.alpaca.markets/paper/dashboard/overview

## 🔧 Configuration Options

### Adjust Risk Parameters
Edit `config/config.yaml`:
```yaml
execution:
  risk_per_trade_pct: 2.0      # Increase to 2% per trade
  max_position_size_pct: 5.0   # Allow up to 5% per position
  max_daily_loss_usd: 10000.0  # Increase daily loss limit
  loop_interval_seconds: 30    # Faster 30-second cycle
```

### Change Broker Mode
```yaml
execution:
  broker: "simulated"  # Use simulated broker (no Alpaca)
  # OR
  broker: "alpaca_paper"  # Use Alpaca Paper (default)
  # OR
  broker: "alpaca_live"  # ⚠️ USE WITH EXTREME CAUTION - REAL MONEY
```

## 🎯 What to Watch

### Good Signs ✅
- Alpaca connection successful
- Trade ideas generated consistently
- Orders filled successfully
- Portfolio value growing or stable
- Prediction accuracy improving over time

### Warning Signs ⚠️
- Frequent connection errors
- Orders rejected (insufficient funds, invalid strikes)
- Portfolio value dropping rapidly
- All predictions showing low confidence (<50%)

### Emergency Actions 🚨
1. **Stop Trading**: Press `Ctrl+C`
2. **Disable Trading**: Set `enable_trading: false` in config
3. **Review Logs**: Check `logs/gnosis.log`
4. **Reset Paper Account**: https://app.alpaca.markets/paper/dashboard/settings

## 📈 Performance Tracking

The system automatically tracks:
- **Predictions**: Multi-timeframe forecast accuracy
- **Trades**: Win rate, average P&L, max drawdown
- **Optimization**: Self-adjusting parameters based on performance

View performance:
```bash
# Daily report
python scripts/analysis/daily_report.py --days 7

# Regime correlation
python scripts/analysis/regime_correlation.py --days 14

# Exit analysis
python scripts/analysis/exit_tracker.py --days 7
```

## 🔒 Safety Features

### Built-in Protections
- ✅ Max 2% position size (configurable)
- ✅ $5k daily loss limit (configurable)
- ✅ Options liquidity filtering (spread < 5%, OI > 100)
- ✅ Paper trading mode (no real money)
- ✅ Graceful shutdown on Ctrl+C
- ✅ Automatic error handling and retry

### Risk Management
The system respects:
- Position size limits from config
- Daily loss limits from config
- Alpaca account buying power
- Options liquidity thresholds
- Confidence minimums (50%+)

## 🚀 Next Steps

### Phase 1: Validate Paper Trading (Current)
- [x] Enable Alpaca connection
- [ ] Run for 1-2 weeks in dry-run mode
- [ ] Run for 2-4 weeks in paper mode
- [ ] Validate strategy selection and fills
- [ ] Document any unexpected behavior

### Phase 2: Multi-Symbol Paper (Future)
- [ ] Expand to SPY, QQQ, IWM
- [ ] Validate regime adaptation across symbols
- [ ] Compare performance vs single-symbol

### Phase 3: Live Trading (⚠️ Extreme Caution)
- [ ] Complete 4+ weeks successful paper trading
- [ ] 100% fill rate validation
- [ ] Fund live Alpaca account
- [ ] Start with minimum capital ($25k-$50k)
- [ ] Gradually scale up after validation

## 💡 Pro Tips

### Optimization
1. **Let it Run**: System self-optimizes after 50+ predictions
2. **Review Daily**: Check `logs/gnosis.log` for insights
3. **Track Patterns**: Note which regimes perform best
4. **Adjust Parameters**: Tune based on performance data

### Debugging
```bash
# Verbose logging
export LOG_LEVEL=DEBUG
python main.py live-loop --symbol SPY --dry-run

# Check configuration
python -c "from config import load_config; print(load_config().execution)"

# Test individual components
python examples/test_options_liquidity.py
python examples/options_validation_workflow.py
```

### Best Practices
- Start with dry-run mode
- Monitor for at least 1 week before enabling execution
- Review trades daily in Alpaca dashboard
- Keep paper capital realistic ($25k-$100k)
- Document edge cases and failures
- Don't skip validation phases

## 📞 Support

### Documentation
- `ALPACA_SETUP.md`: Detailed Alpaca configuration
- `OPERATIONS_RUNBOOK.md`: Operations and monitoring
- `ARCHITECTURE_OVERVIEW.md`: System architecture
- `DEV_GUIDE.md`: Development guide

### Issues
- GitHub: https://github.com/DGator86/V2---Gnosis/issues
- Alpaca Support: support@alpaca.markets
- Alpaca Forum: https://forum.alpaca.markets/

---

**You're now ready to run autonomous paper trading on Alpaca! 🚀**

Start with:
```bash
cd /home/user/webapp
python main.py live-loop --symbol SPY --dry-run  # Test first
python main.py live-loop --symbol SPY            # Then go live
```
