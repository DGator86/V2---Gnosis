"""
Super Gnosis Enhanced Real-Time Dashboard

Features:
- Real-time P&L tracking
- Composer Agent decisions with confidence levels
- Trade execution feed with strategy details
- Live options positions with leg details
- Auto-refresh every 3 seconds
- Beautiful gradient UI with live updates

Author: Super Gnosis AI Developer
Created: 2025-11-19
"""

from flask import Flask, render_template, jsonify, request
import json
import os
from datetime import datetime
from collections import defaultdict
import threading
import time

app = Flask(__name__)

# Auto-find the ledger file (works whether you're in project root or web/)
LEDGER_PATH = os.path.join(os.path.dirname(__file__), "../data/ledger.jsonl")
POSITIONS_PATH = os.path.join(os.path.dirname(__file__), "../data/positions.json")
ADAPTATION_STATE_PATH = os.path.join(os.path.dirname(__file__), "../data/adaptation_state.json")
if not os.path.exists(LEDGER_PATH):
    LEDGER_PATH = "data/ledger.jsonl"
if not os.path.exists(POSITIONS_PATH):
    POSITIONS_PATH = "data/positions.json"
if not os.path.exists(ADAPTATION_STATE_PATH):
    ADAPTATION_STATE_PATH = "data/adaptation_state.json"

# In-memory cache for live updates
cache = {
    "last_update": None,
    "entries": [],
    "positions": {},
    "pnl_total": 0.0,
    "stats": {"trades": 0, "winning": 0, "losing": 0, "win_rate": 0},
    "adaptive_learning": {
        "enabled": False,
        "bandit_top_strategies": [],
        "adaptive_thresholds": {},
        "calibration_metrics": {},
        "lookahead_metrics": {}
    }
}

lock = threading.Lock()

def load_ledger():
    """Load all ledger entries from JSONL file"""
    entries = []
    if os.path.exists(LEDGER_PATH):
        try:
            with open(LEDGER_PATH, "r") as f:
                for line in f:
                    if line.strip():
                        entries.append(json.loads(line))
        except Exception as e:
            print(f"Error loading ledger: {e}")
    entries.reverse()  # newest first
    return entries

def load_positions():
    """Load current positions from JSON file"""
    if os.path.exists(POSITIONS_PATH):
        try:
            with open(POSITIONS_PATH, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading positions: {e}")
    return {}

def calculate_pnl():
    """Calculate total P&L from positions"""
    positions = load_positions()
    total_pnl = 0.0
    for sym, pos in positions.items():
        if "unrealized_pnl" in pos:
            total_pnl += float(pos["unrealized_pnl"])
        if "realized_pnl" in pos:
            total_pnl += float(pos["realized_pnl"])
    return round(total_pnl, 2)

def load_adaptation_state():
    """Load adaptive learning state for dashboard metrics"""
    if not os.path.exists(ADAPTATION_STATE_PATH):
        return {
            "enabled": False,
            "bandit_top_strategies": [],
            "adaptive_thresholds": {},
            "calibration_metrics": {},
            "lookahead_metrics": {}
        }
    
    try:
        with open(ADAPTATION_STATE_PATH, "r") as f:
            state = json.load(f)
        
        # Extract bandit statistics - top 10 strategies by expected reward
        bandit_stats = state.get("bandit", {}).get("global_stats", {})
        strategy_probs = []
        for strat_id_str, stats in bandit_stats.items():
            try:
                strat_id = int(strat_id_str)
                alpha = stats.get("alpha", 1.0)
                beta = stats.get("beta", 1.0)
                expected_reward = alpha / (alpha + beta)  # Mean of Beta distribution
                count = stats.get("count", 0)
                strategy_probs.append({
                    "strategy_id": strat_id,
                    "expected_reward": round(expected_reward, 3),
                    "count": count,
                    "alpha": round(alpha, 2),
                    "beta": round(beta, 2)
                })
            except (ValueError, TypeError):
                continue
        
        # Sort by expected reward and take top 10
        strategy_probs.sort(key=lambda x: x["expected_reward"], reverse=True)
        top_10 = strategy_probs[:10]
        
        # Extract adaptive thresholds comparison
        thresholds_state = state.get("thresholds", {}).get("thresholds", {})
        adaptive_thresholds = {
            key: round(val, 3) for key, val in thresholds_state.items()
        }
        
        # Extract calibration metrics
        calibrator = state.get("calibrator", {})
        calibration_metrics = {
            "samples_count": calibrator.get("samples_count", 0),
            "model_ready": calibrator.get("model_ready", False)
        }
        
        # Extract lookahead metrics
        lookahead = state.get("lookahead", {})
        lookahead_metrics = {
            "training_samples": lookahead.get("training_samples", 0),
            "last_mae": round(lookahead.get("last_mae", 0.0), 4) if lookahead.get("last_mae") else None,
            "last_direction_accuracy": round(lookahead.get("last_direction_accuracy", 0.0), 3) if lookahead.get("last_direction_accuracy") else None
        }
        
        return {
            "enabled": True,
            "bandit_top_strategies": top_10,
            "adaptive_thresholds": adaptive_thresholds,
            "calibration_metrics": calibration_metrics,
            "lookahead_metrics": lookahead_metrics
        }
    except Exception as e:
        print(f"Error loading adaptation state: {e}")
        return {
            "enabled": False,
            "bandit_top_strategies": [],
            "adaptive_thresholds": {},
            "calibration_metrics": {},
            "lookahead_metrics": {}
        }

def update_cache():
    """Update the in-memory cache with latest data"""
    global cache
    with lock:
        cache["entries"] = load_ledger()[:100]  # last 100 events
        cache["positions"] = load_positions()
        cache["pnl_total"] = calculate_pnl()
        cache["last_update"] = datetime.now().strftime("%H:%M:%S")
        
        # Calculate stats
        trades = [e for e in cache["entries"] if e.get("event_type") == "TRADE_EXECUTED"]
        winning = sum(1 for t in trades if t.get("pnl", 0) > 0 and t.get("status") == "closed")
        losing = sum(1 for t in trades if t.get("pnl", 0) < 0 and t.get("status") == "closed")
        total_closed = winning + losing
        
        cache["stats"] = {
            "trades": len(trades),
            "winning": winning,
            "losing": losing,
            "win_rate": round(winning / max(1, total_closed) * 100, 1) if total_closed > 0 else 0
        }
        
        # Load adaptive learning metrics
        cache["adaptive_learning"] = load_adaptation_state()

# Background updater thread
def background_updater():
    """Background thread that updates cache every 3 seconds"""
    while True:
        update_cache()
        time.sleep(3)

# Start background updater
threading.Thread(target=background_updater, daemon=True).start()

@app.route("/")
def index():
    """Main dashboard page"""
    return render_template("gnosis_dashboard.html")

@app.route("/api/data")
def api_data():
    """API endpoint for dashboard data"""
    return jsonify(cache)

@app.route("/api/refresh")
def api_refresh():
    """Manual refresh endpoint"""
    update_cache()
    return jsonify({"status": "refreshed"})

if __name__ == "__main__":
    print("=" * 70)
    print("🚀 Super Gnosis Enhanced Dashboard LIVE")
    print("=" * 70)
    print("📊 Dashboard URL: http://127.0.0.1:5000")
    print("🔄 Auto-refresh: Every 3 seconds")
    print("💰 Live P&L tracking enabled")
    print("📈 Options strategies displayed with full leg details")
    print("=" * 70)
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
