# System Maintenance & Troubleshooting Guide

## 🔧 System Health Checks

### Daily Health Check Script
```bash
#!/bin/bash
# Save as: health_check.sh

echo "=== Agentic Trading System Health Check ==="
echo "Timestamp: $(date)"
echo ""

# 1. API Health
echo "1. Checking API endpoint..."
curl -s http://localhost:8000/health | jq '.' || echo "❌ API not responding"
echo ""

# 2. Feature Store Integrity
echo "2. Checking feature store..."
python3 << 'EOF'
from pathlib import Path
import pandas as pd

data_dir = Path("data")
if not data_dir.exists():
    print("❌ Feature store directory missing")
else:
    dates = list(data_dir.glob("date=*"))
    print(f"✓ {len(dates)} trading days in feature store")
    
    # Check latest date
    if dates:
        latest = max(dates)
        print(f"  Latest: {latest.name}")
        features = list(latest.rglob("features.parquet"))
        print(f"  {len(features)} symbols tracked")
EOF
echo ""

# 3. L1 Data Availability
echo "3. Checking L1 data..."
ls -lh data_l1/*.parquet 2>/dev/null | tail -5 || echo "❌ No L1 data found"
echo ""

# 4. Disk Usage
echo "4. Checking disk usage..."
du -sh data/ data_l1/ 2>/dev/null
echo ""

# 5. Process Check
echo "5. Checking running processes..."
ps aux | grep -E "uvicorn|python.*app.py" | grep -v grep || echo "⚠️  API server not running"
echo ""

echo "=== Health Check Complete ==="
```

---

## 🗄️ Data Management

### Cleaning Old Data
```python
# clean_old_data.py
from pathlib import Path
from datetime import datetime, timedelta
import shutil

def clean_old_features(days_to_keep: int = 30):
    """Remove feature data older than N days"""
    cutoff_date = datetime.now() - timedelta(days=days_to_keep)
    data_dir = Path("data")
    
    removed = 0
    for date_dir in data_dir.glob("date=*"):
        date_str = date_dir.name.replace("date=", "")
        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            if date_obj < cutoff_date:
                shutil.rmtree(date_dir)
                removed += 1
                print(f"Removed: {date_str}")
        except ValueError:
            print(f"⚠️  Invalid date format: {date_str}")
    
    print(f"✓ Cleaned {removed} old date directories")

def compress_old_l1(days_to_keep: int = 7):
    """Compress L1 parquet files older than N days"""
    import gzip
    cutoff_date = datetime.now() - timedelta(days=days_to_keep)
    l1_dir = Path("data_l1")
    
    for parquet in l1_dir.glob("l1_*.parquet"):
        date_str = parquet.stem.replace("l1_", "")
        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            if date_obj < cutoff_date and not parquet.with_suffix(".parquet.gz").exists():
                # Compress
                with open(parquet, 'rb') as f_in:
                    with gzip.open(f"{parquet}.gz", 'wb') as f_out:
                        f_out.writelines(f_in)
                parquet.unlink()
                print(f"Compressed: {parquet.name}")
        except ValueError:
            print(f"⚠️  Invalid date in filename: {parquet.name}")

if __name__ == "__main__":
    print("Cleaning old feature data (30+ days)...")
    clean_old_features(days_to_keep=30)
    print("\nCompressing old L1 data (7+ days)...")
    compress_old_l1(days_to_keep=7)
```

---

## 🐛 Troubleshooting

### Issue 1: "No features for symbol on date"

**Symptoms:**
```
GET /features/SPY?bar=2025-11-03T15:30:00
→ 404: "No features for SPY on 2025-11-03 (set=v0.1.0)"
```

**Diagnosis:**
```bash
# Check if features exist
ls -la data/date=2025-11-03/symbol=SPY/feature_set_id=v0.1.0/

# Check parquet contents
python3 << 'EOF'
import pandas as pd
df = pd.read_parquet("data/date=2025-11-03/symbol=SPY/feature_set_id=v0.1.0/features.parquet")
print(df[["bar"]].head())
print(f"\nBar range: {df['bar'].min()} to {df['bar'].max()}")
EOF
```

**Solutions:**
1. **Features don't exist:** Run `/run_bar` to generate them
2. **Wrong date format:** Ensure ISO format `YYYY-MM-DDTHH:MM:SS`
3. **Time mismatch:** Bar timestamp must exist in features (point-in-time read)

---

### Issue 2: Backtest Returns 0 Trades

**Symptoms:**
```bash
python -m gnosis.backtest --symbol SPY --date 2025-11-03
→ "num_trades": 0
```

**Diagnosis:**
```python
# Debug single bar decision
from gnosis.feature_store.store import FeatureStore
from gnosis.agents.agents_v1 import agent1_hedge, agent2_liquidity, agent3_sentiment, compose
from datetime import datetime

fs = FeatureStore(root="data", read_only=True)
symbol = "SPY"
t = datetime(2025, 11, 3, 15, 30, 0)

# Read features
row = fs.read_pit(symbol, t, "v0.1.0")

# Build views
v1 = agent1_hedge(symbol, t, row["hedge"]["present"], row["hedge"]["future"])
v2 = agent2_liquidity(symbol, t, row["liquidity"]["present"], row["liquidity"]["future"], 451.62)
v3 = agent3_sentiment(symbol, t, row["sentiment"]["present"], row["sentiment"]["future"])

print("Agent Views:")
print(f"  Hedge:     dir={v1.dir_bias:.2f}, conf={v1.confidence:.2f}")
print(f"  Liquidity: dir={v2.dir_bias:.2f}, conf={v2.confidence:.2f}")
print(f"  Sentiment: dir={v3.dir_bias:.2f}, conf={v3.confidence:.2f}")

# Compose
idea = compose(symbol, t, [v1, v2, v3], amihud=row["liquidity"]["present"]["amihud"])
print(f"\nDecision: {idea['take_trade']}")
if not idea["take_trade"]:
    print(f"Reason: {idea['reason']}")
    print(f"Scores: up={idea['scores']['up']:.2f}, down={idea['scores']['down']:.2f}")
```

**Common Causes:**
1. **Insufficient alignment:** Need 2+ agents with conf ≥ 0.6
2. **Mixed signals:** Agents cancel each other out
3. **Synthetic data:** Lacks realistic signal correlation
4. **Low confidence:** All agents below 0.6 threshold

**Solutions:**
- Use real market data (synthetic data is for testing pipeline only)
- Adjust alignment threshold in `compose()`: change `0.6` to `0.5`
- Check if all engines are producing valid features

---

### Issue 3: High Slippage Costs

**Symptoms:**
```
Backtest shows many trades but negative P&L
Slippage eating into profits
```

**Diagnosis:**
```python
# Check Amihud values
import pandas as pd

features = pd.read_parquet("data/date=2025-11-03/symbol=SPY/feature_set_id=v0.1.0/features.parquet")
liq = pd.json_normalize(features["liquidity"])
print(liq["present.amihud"].describe())

# Expected ranges:
# Very liquid (SPY): 1e-11 to 1e-10
# If seeing > 1e-9, data quality issue
```

**Solutions:**
1. **Improve data quality:** Ensure volume and dollar_volume are realistic
2. **Adjust slippage model:** Edit `_slippage()` in `replay_v0.py`
3. **Filter thin markets:** Skip bars with Amihud > threshold

---

### Issue 4: API 500 Internal Server Error

**Symptoms:**
```
POST /run_bar/SPY?price=451.62&bar=2025-11-03T15:30:00
→ 500 Internal Server Error
```

**Diagnosis:**
```bash
# Check server logs
tail -50 uvicorn.log

# Or run server in foreground to see errors
uvicorn app:app --reload --port 8000
```

**Common Errors:**

**a) Validation Error:**
```
pydantic_core._pydantic_core.ValidationError: 1 validation error for L1Thin
price
  Input should be a valid number
```
**Solution:** Ensure all numeric parameters are valid floats

**b) Division by Zero:**
```
ZeroDivisionError: division by zero
```
**Solution:** Check for empty DataFrames in engine calculations. Add guards:
```python
if df.empty or len(df) < 2:
    return default_value
```

**c) Missing Column:**
```
KeyError: 'volume'
```
**Solution:** Ensure L1 data has all required columns. Check transform step.

---

### Issue 5: Feature Store Corruption

**Symptoms:**
```
pyarrow.lib.ArrowInvalid: Parquet file is corrupted
```

**Diagnosis:**
```bash
# Verify parquet file integrity
python3 << 'EOF'
import pyarrow.parquet as pq

try:
    table = pq.read_table("data/date=2025-11-03/symbol=SPY/feature_set_id=v0.1.0/features.parquet")
    print(f"✓ File OK: {table.num_rows} rows")
except Exception as e:
    print(f"❌ Corrupted: {e}")
EOF
```

**Solutions:**
1. **Delete corrupted file:** `rm <file>.parquet` and regenerate
2. **Restore from backup:** Copy from backup directory
3. **Regenerate features:** Re-run `/run_bar` for all bars that day

---

## 📊 Performance Monitoring

### Latency Tracking
```python
# Add to app.py
import time
from fastapi import Request

@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    
    # Log slow requests
    if process_time > 0.5:  # 500ms threshold
        print(f"⚠️  SLOW: {request.url.path} took {process_time:.2f}s")
    
    return response
```

### Memory Usage
```python
# memory_profile.py
import psutil
import os

def check_memory():
    process = psutil.Process(os.getpid())
    mem_info = process.memory_info()
    
    print(f"Memory Usage:")
    print(f"  RSS: {mem_info.rss / 1024 / 1024:.1f} MB")
    print(f"  VMS: {mem_info.vms / 1024 / 1024:.1f} MB")
    
    # Check feature store size
    import pandas as pd
    from pathlib import Path
    
    parquet_files = list(Path("data").rglob("*.parquet"))
    total_size = sum(f.stat().st_size for f in parquet_files)
    print(f"  Feature Store: {total_size / 1024 / 1024:.1f} MB")

if __name__ == "__main__":
    check_memory()
```

---

## 🔄 Upgrading Feature Versions

### When to Upgrade
- Changed engine calculation logic
- Modified feature schema
- Bug fixes that affect feature values

### Upgrade Process
```python
# Step 1: Update feature_set_id
# In schemas/base.py:
class L3Canonical(BaseModel):
    feature_set_id: str = "v0.2.0"  # Increment version

# Step 2: Maintain backward compatibility
# Create version-specific readers if needed
def read_features_v0_1_0(path):
    # Legacy format
    pass

def read_features_v0_2_0(path):
    # New format
    pass

# Step 3: Regenerate features for critical dates
# regenerate_features.py
from app import app
import pandas as pd
from datetime import datetime

dates_to_regenerate = ["2025-11-01", "2025-11-02", "2025-11-03"]
symbols = ["SPY", "QQQ"]

for date in dates_to_regenerate:
    l1_df = pd.read_parquet(f"data_l1/l1_{date}.parquet")
    for symbol in symbols:
        symbol_data = l1_df[l1_df["symbol"] == symbol]
        for _, row in symbol_data.iterrows():
            # Call /run_bar for each bar
            pass
```

---

## 🔐 Security Hardening

### API Key Authentication
```python
# Add to app.py
from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader

API_KEY = "your-secret-key-here"  # Move to env var
api_key_header = APIKeyHeader(name="X-API-Key")

def verify_api_key(api_key: str = Security(api_key_header)):
    if api_key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key"
        )
    return api_key

# Protect endpoints
@app.post("/run_bar/{symbol}")
def run_bar(symbol: str, price: float, bar: str, 
            api_key: str = Security(verify_api_key)):
    # ... existing logic
```

### Rate Limiting
```python
# rate_limit.py
from fastapi import Request, HTTPException
from collections import defaultdict
import time

request_counts = defaultdict(list)
RATE_LIMIT = 10  # requests per minute

async def rate_limit_middleware(request: Request, call_next):
    client_ip = request.client.host
    now = time.time()
    
    # Clean old requests
    request_counts[client_ip] = [
        req_time for req_time in request_counts[client_ip]
        if now - req_time < 60
    ]
    
    # Check limit
    if len(request_counts[client_ip]) >= RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    request_counts[client_ip].append(now)
    return await call_next(request)

# Add to app.py
app.middleware("http")(rate_limit_middleware)
```

---

## 📦 Backup & Disaster Recovery

### Automated Backup Script
```bash
#!/bin/bash
# backup.sh - Run daily via cron

BACKUP_DIR="/backups/agentic-trading"
DATE=$(date +%Y%m%d)

echo "Starting backup: $DATE"

# Create backup directory
mkdir -p "$BACKUP_DIR/$DATE"

# Backup feature store (compressed)
echo "Backing up feature store..."
tar -czf "$BACKUP_DIR/$DATE/features.tar.gz" data/

# Backup L1 data (last 7 days only)
echo "Backing up L1 data..."
find data_l1 -name "*.parquet" -mtime -7 -exec tar -czf "$BACKUP_DIR/$DATE/l1_recent.tar.gz" {} +

# Backup code
echo "Backing up code..."
tar -czf "$BACKUP_DIR/$DATE/code.tar.gz" --exclude='.venv' --exclude='__pycache__' .

# Clean old backups (keep 30 days)
echo "Cleaning old backups..."
find "$BACKUP_DIR" -type d -mtime +30 -exec rm -rf {} +

echo "Backup complete: $DATE"
```

### Restore Process
```bash
#!/bin/bash
# restore.sh <backup_date>

BACKUP_DIR="/backups/agentic-trading"
DATE=$1

if [ -z "$DATE" ]; then
    echo "Usage: ./restore.sh YYYYMMDD"
    exit 1
fi

echo "Restoring from backup: $DATE"

# Restore features
tar -xzf "$BACKUP_DIR/$DATE/features.tar.gz"

# Restore L1
tar -xzf "$BACKUP_DIR/$DATE/l1_recent.tar.gz"

# Restore code (optional, use with caution)
# tar -xzf "$BACKUP_DIR/$DATE/code.tar.gz"

echo "Restore complete"
```

---

## 🧪 Testing Checklist

### Before Deploying Changes

```bash
# 1. Unit tests (when available)
pytest tests/ -v

# 2. Smoke test API
curl http://localhost:8000/health

# 3. Test single bar processing
curl -X POST "http://localhost:8000/run_bar/SPY?price=451.62&bar=2025-11-03T15:30:00"

# 4. Test feature retrieval
curl "http://localhost:8000/features/SPY?bar=2025-11-03T15:30:00"

# 5. Test backtest
python -m gnosis.backtest --symbol SPY --date 2025-11-03

# 6. Check logs for errors
tail -100 uvicorn.log | grep -i error

# 7. Memory check
ps aux | grep uvicorn | awk '{print $6/1024 " MB"}'
```

---

## 📝 Operational Runbook

### Daily Operations

**Morning Checklist (Pre-Market):**
1. Run health check script
2. Verify API is responding
3. Check disk space (`df -h`)
4. Review overnight logs for errors
5. Test with sample data

**During Trading Hours:**
1. Monitor API latency (< 70ms per bar)
2. Watch for error spikes in logs
3. Track trade idea generation rate
4. Monitor memory usage

**Evening Checklist (Post-Market):**
1. Run backtest on today's data
2. Archive logs
3. Compress old L1 data
4. Run backup script
5. Review P&L and metrics

---

## 🚨 Emergency Procedures

### System Crash
```bash
# 1. Check if process is running
ps aux | grep uvicorn

# 2. Check logs for crash reason
tail -200 uvicorn.log

# 3. Restart API server
pkill -f "uvicorn app:app"
nohup uvicorn app:app --host 0.0.0.0 --port 8000 > uvicorn.log 2>&1 &

# 4. Verify health
curl http://localhost:8000/health
```

### Data Corruption
```bash
# 1. Identify corrupted files
find data -name "*.parquet" -exec python3 -c "
import sys
import pyarrow.parquet as pq
try:
    pq.read_table(sys.argv[1])
except:
    print(sys.argv[1])
" {} \;

# 2. Restore from backup
./restore.sh <backup_date>

# 3. Regenerate missing days
python regenerate_features.py --start-date 2025-11-01 --end-date 2025-11-03
```

### High Memory Usage
```bash
# 1. Identify memory hog
ps aux --sort=-%mem | head -10

# 2. Restart with memory limit
pkill -f "uvicorn app:app"
ulimit -v 2000000  # Limit to 2GB virtual memory
uvicorn app:app --host 0.0.0.0 --port 8000

# 3. Consider moving to read-only mode for backtest
# This avoids DuckDB connection overhead
```

---

*For architecture details, see `ARCHITECTURE_REPORT.md`*  
*For quick commands, see `QUICK_START.md`*  
*For decision flow, see `DECISION_FLOW.md`*
