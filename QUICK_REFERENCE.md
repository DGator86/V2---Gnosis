# DHPE Pipeline - Quick Reference Card

## 🚀 Quick Start (3 Commands)

```bash
cd /home/user/webapp
pip install -r requirements.txt  # Optional: adds Polars for 10x speedup
python main.py                    # Run pipeline
```

## 📋 Common Commands

```bash
# Single run (default: SPY)
python main.py

# Different symbol
python main.py --symbol QQQ

# Backtest mode
python main.py --backtest --runs 50

# Verify installation
python verify_integration.py

# Check logs
ls -lh logs/

# Check ledger
cat data/ledger.jsonl | jq .  # Pretty print
```

## 📁 Key Files

| File | Purpose |
|------|---------|
| `main.py` | Run the pipeline |
| `config/config.yaml` | All configuration |
| `data/ledger.jsonl` | Audit trail |
| `logs/*.log` | Structured logs |
| `README.md` | Full documentation |
| `FINAL_SUMMARY.md` | Implementation summary |

## ⚙️ Configuration Quick Tweaks

```yaml
# config/config.yaml

# Change forecast horizons
lookahead:
  horizons: [1, 5, 20, 60]  # bars/minutes

# Change voting method
agents:
  composer:
    voting_method: "weighted_confidence"  # majority, unanimous

# Change reward metric
feedback:
  reward_metric: "sharpe"  # pnl, hit_rate, sortino
  learning_rate: 0.2

# Enable Polars for speed
engines:
  hedge:
    polars_threads: 4

# Adjust memory decay
engines:
  sentiment:
    decay_half_life_days: 7.0
```

## 🔍 Inspecting Results

### View Ledger Entries
```bash
# Count entries
wc -l data/ledger.jsonl

# View suggestions only
grep SUGGESTION data/ledger.jsonl | jq .

# View positions
grep POSITION data/ledger.jsonl | jq .

# View results
grep RESULT data/ledger.jsonl | jq .
```

### View Logs
```bash
# Main execution log
tail -f logs/main_*.log

# Agent decisions
tail -f logs/agents_*.log

# Engine outputs
tail -f logs/engines_*.log
```

### View Checkpoints
```bash
# List checkpoints
ls -lh logs/checkpoints/

# View checkpoint
cat logs/checkpoints/[run_id]_[agent]_step[N].json | jq .
```

## 🔧 Customization Points

### Replace Demo Data
Edit `engines/inputs/demo_inputs_engine.py` or create new input engine

### Add New Agent
1. Copy `agents/primary_hedge/agent.py` as template
2. Implement `step(snapshot, horizons)` method
3. Add to `pipeline_runner.py`

### Add New Engine
1. Create `engines/your_engine/your_engine.py`
2. Return `EngineOutput` with features
3. Add to standardizer

### Change Strategy Mapping
Edit `agents/composer/agent.py`:
```python
self.strategy_map = {
    "long": "your_strategy",
    "short": "your_strategy",
    ...
}
```

## 📊 Metrics & Performance

### Get Metrics Programmatically
```python
from engines.tracking.ledger_engine import LedgerEngine

ledger = LedgerEngine()
metrics = ledger.get_metrics(
    layer="primary_hedge",  # Filter by agent
    symbol="SPY",           # Filter by symbol
    lookback_hours=24       # Recent only
)

print(metrics)
# {
#   "count": 50,
#   "hit_rate": 0.62,
#   "avg_pnl": 1.25,
#   "sharpe": 1.45,
#   ...
# }
```

### Get Learning Summary
```python
from engines.feedback.feedback_engine import FeedbackEngine

feedback = FeedbackEngine()
summary = feedback.get_learning_summary()
print(summary['agent_scores'])
print(summary['best_agent'])
```

## 🐛 Troubleshooting

### Pipeline won't start
```bash
# Check Python version (need 3.8+)
python --version

# Check dependencies
pip list | grep -E "pyyaml|polars"

# Run verification
python verify_integration.py
```

### Polars not found
```bash
# Install Polars (optional, for speed)
pip install polars

# Or continue without (automatic fallback)
```

### Config not loading
```bash
# Check YAML syntax
python -c "import yaml; yaml.safe_load(open('config/config.yaml'))"

# Use absolute path
python main.py --config /absolute/path/to/config.yaml
```

### Logs not writing
```bash
# Check logs directory exists
mkdir -p logs

# Check permissions
chmod 755 logs/
```

## 🎯 Performance Tuning

```yaml
# config/config.yaml

# Speed up hedge engine (if Polars installed)
engines:
  hedge:
    polars_threads: 8  # More threads

# Reduce memory footprint
engines:
  sentiment:
    max_memory_items: 1000  # Fewer items
  
memory:
  long_term_max_items: 5000  # Smaller cache

# Reduce checkpoint storage
runtime:
  enable_checkpointing: false  # Disable if not needed
```

## 📚 Documentation Map

- **README.md** → User guide, architecture, examples
- **FINAL_SUMMARY.md** → Implementation summary, statistics
- **IMPLEMENTATION_COMPLETE.md** → Completion details, verification
- **docs/INTEGRATION_SUMMARY.md** → Technical integration details
- **QUICK_REFERENCE.md** → This file

## 🆘 Getting Help

1. **Read README.md** for full documentation
2. **Check FINAL_SUMMARY.md** for implementation details
3. **Run verify_integration.py** to check setup
4. **View logs/** for runtime issues
5. **Check config/config.yaml** for parameters

## 🔗 Quick Links

| What | Where |
|------|-------|
| Pipeline flow | README.md → Architecture |
| Add real data | README.md → Extending the System |
| Metrics API | README.md → Metrics & Evaluation |
| Config options | config/config.yaml (inline docs) |
| Example output | README.md → Example Output |

---

**Pro Tip**: Run `python verify_integration.py` after any changes to ensure everything still works!
