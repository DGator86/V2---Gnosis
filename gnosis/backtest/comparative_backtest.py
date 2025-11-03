"""
Comparative Backtest - Run multiple composer strategies side-by-side

This lets you A/B test different agent configurations:
- Baseline: 3-agent system (Hedge, Liquidity, Sentiment)
- Enhanced: 5-agent system (+ Wyckoff, Markov)
- Hybrid variants

No code changes to production. Pure analysis.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Any, Callable
from pathlib import Path
from datetime import datetime
import pandas as pd
import numpy as np
import json

from gnosis.feature_store.store import FeatureStore
from gnosis.agents.agents_v1 import (
    agent1_hedge, agent2_liquidity, agent3_sentiment, compose
)

# Import new engines (will add agents below)
from gnosis.engines.wyckoff_v0 import compute_wyckoff_v0
from gnosis.engines.markov_regime_v0 import compute_markov_regime_stateful

@dataclass
class StrategyConfig:
    """Configuration for a trading strategy variant"""
    name: str
    agents: List[str]  # Which agents to include
    alignment_threshold: int  # How many must agree
    high_conf_threshold: float  # Confidence cutoff
    reliability_weights: Dict[str, float]
    description: str

@dataclass
class StrategyResult:
    """Results for a strategy variant"""
    config: StrategyConfig
    pnl: float
    num_trades: int
    win_rate: float
    avg_win: float
    avg_loss: float
    sharpe: float
    max_drawdown: float
    trades: List[Dict]
    equity_curve: pd.DataFrame
    
    def summary(self) -> Dict[str, Any]:
        return {
            "name": self.config.name,
            "pnl": round(self.pnl, 2),
            "num_trades": self.num_trades,
            "win_rate": round(self.win_rate, 3),
            "avg_win": round(self.avg_win, 2),
            "avg_loss": round(self.avg_loss, 2),
            "sharpe": round(self.sharpe, 3),
            "max_dd": round(self.max_drawdown, 2)
        }

# Define strategy variants
STRATEGIES = {
    "baseline": StrategyConfig(
        name="3-Agent Baseline",
        agents=["hedge", "liquidity", "sentiment"],
        alignment_threshold=2,
        high_conf_threshold=0.6,
        reliability_weights={"hedge": 1.0, "liquidity": 1.0, "sentiment": 1.0},
        description="Original 2-of-3 system"
    ),
    
    "conservative": StrategyConfig(
        name="3-Agent Conservative",
        agents=["hedge", "liquidity", "sentiment"],
        alignment_threshold=3,  # Require all 3
        high_conf_threshold=0.7,  # Higher confidence
        reliability_weights={"hedge": 1.0, "liquidity": 1.0, "sentiment": 1.0},
        description="Require unanimous agreement with high confidence"
    ),
    
    "wyckoff_enhanced": StrategyConfig(
        name="4-Agent + Wyckoff",
        agents=["hedge", "liquidity", "sentiment", "wyckoff"],
        alignment_threshold=3,  # 3-of-4
        high_conf_threshold=0.6,
        reliability_weights={
            "hedge": 1.0, 
            "liquidity": 1.0, 
            "sentiment": 1.0,
            "wyckoff": 1.1  # Slightly favor Wyckoff signals
        },
        description="Add Wyckoff for reversal detection"
    ),
    
    "markov_enhanced": StrategyConfig(
        name="4-Agent + Markov",
        agents=["hedge", "liquidity", "sentiment", "markov"],
        alignment_threshold=3,  # 3-of-4
        high_conf_threshold=0.6,
        reliability_weights={
            "hedge": 1.0, 
            "liquidity": 1.0, 
            "sentiment": 1.0,
            "markov": 0.9  # Slightly discount probabilistic model
        },
        description="Add Markov for regime probability"
    ),
    
    "full_5agent": StrategyConfig(
        name="5-Agent Full",
        agents=["hedge", "liquidity", "sentiment", "wyckoff", "markov"],
        alignment_threshold=3,  # 3-of-5
        high_conf_threshold=0.6,
        reliability_weights={
            "hedge": 1.0, 
            "liquidity": 1.0, 
            "sentiment": 1.0,
            "wyckoff": 1.1,
            "markov": 0.9
        },
        description="All 5 agents with 3-of-5 voting"
    ),
    
    "full_5agent_strict": StrategyConfig(
        name="5-Agent Strict",
        agents=["hedge", "liquidity", "sentiment", "wyckoff", "markov"],
        alignment_threshold=4,  # 4-of-5 (very conservative)
        high_conf_threshold=0.65,
        reliability_weights={
            "hedge": 1.0, 
            "liquidity": 1.0, 
            "sentiment": 1.0,
            "wyckoff": 1.1,
            "markov": 0.9
        },
        description="All 5 agents with 4-of-5 voting (high conviction only)"
    ),
}

def agent4_wyckoff(symbol: str, bar: datetime, wyckoff: Dict) -> Any:
    """Wyckoff agent implementation"""
    from gnosis.agents.agents_v1 import AgentView
    
    phase = wyckoff.get("phase", "unknown")
    conf = float(wyckoff.get("confidence", 0.5))
    spring = wyckoff.get("spring_detected", False)
    upthrust = wyckoff.get("upthrust_detected", False)
    vol_div = float(wyckoff.get("volume_divergence", 0.0))
    
    if spring:
        dir_bias = 1.0
        thesis = "spring_breakout"
        conf = max(conf, 0.85)
    elif upthrust:
        dir_bias = -1.0
        thesis = "upthrust_reversal"
        conf = max(conf, 0.85)
    elif phase == "accumulation":
        dir_bias = 1.0
        thesis = "accumulation_long"
        conf *= 0.9
    elif phase == "markup":
        dir_bias = 1.0
        thesis = "markup_follow"
    elif phase == "distribution":
        dir_bias = -1.0
        thesis = "distribution_short"
        conf *= 0.9
    elif phase == "markdown":
        dir_bias = -1.0
        thesis = "markdown_follow"
    else:
        dir_bias = 0.0
        thesis = "wyckoff_neutral"
        conf *= 0.5
    
    if abs(vol_div) > 0.7:
        conf = min(1.0, conf * 1.2)
    
    return AgentView(
        symbol=symbol, bar=bar, agent="wyckoff",
        dir_bias=dir_bias, confidence=max(0.0, min(1.0, conf)),
        thesis=thesis,
        notes=f"phase={phase}, spring={spring}, upthrust={upthrust}, vol_div={vol_div:.2f}"
    )

def agent5_markov(symbol: str, bar: datetime, markov: Dict) -> Any:
    """Markov HMM agent implementation"""
    from gnosis.agents.agents_v1 import AgentView
    
    current_state = markov.get("current_state", "ranging")
    conf = float(markov.get("confidence", 0.5))
    state_probs = markov.get("state_probabilities", {})
    
    prob_trend_up = state_probs.get("trending_up", 0.0)
    prob_trend_down = state_probs.get("trending_down", 0.0)
    prob_accum = state_probs.get("accumulation", 0.0)
    prob_distrib = state_probs.get("distribution", 0.0)
    
    bullish_prob = prob_trend_up + prob_accum
    bearish_prob = prob_trend_down + prob_distrib
    
    if bullish_prob > bearish_prob * 1.5:
        dir_bias = 1.0
        thesis = f"markov_{current_state}_bullish"
    elif bearish_prob > bullish_prob * 1.5:
        dir_bias = -1.0
        thesis = f"markov_{current_state}_bearish"
    else:
        dir_bias = 0.0
        thesis = f"markov_{current_state}_neutral"
    
    if conf < 0.5:
        conf *= 0.7
    
    return AgentView(
        symbol=symbol, bar=bar, agent="markov",
        dir_bias=dir_bias, confidence=conf, thesis=thesis,
        notes=f"state={current_state}, conf={conf:.2f}, bull_p={bullish_prob:.2f}, bear_p={bearish_prob:.2f}"
    )

def compose_with_config(
    symbol: str,
    bar: datetime,
    views: List[Any],
    amihud: float,
    config: StrategyConfig
) -> Dict:
    """Modified composer that uses strategy config"""
    
    # Filter views to only included agents
    views = [v for v in views if v.agent in config.agents]
    
    if len(views) == 0:
        return {
            "take_trade": False,
            "reason": "no_agents",
            "scores": {"up": 0, "down": 0}
        }
    
    # Normalize and weight
    for v in views:
        v.confidence = float(max(0.0, min(1.0, v.confidence)))
    
    w = {v.agent: v.confidence * config.reliability_weights.get(v.agent, 1.0) for v in views}
    
    # Directional scores
    up_score = sum(w[v.agent] for v in views if v.dir_bias > 0)
    down_score = sum(w[v.agent] for v in views if v.dir_bias < 0)
    
    # Alignment check with config threshold
    align_up = sum(1 for v in views 
                  if v.dir_bias > 0 and v.confidence >= config.high_conf_threshold) >= config.alignment_threshold
    align_down = sum(1 for v in views 
                    if v.dir_bias < 0 and v.confidence >= config.high_conf_threshold) >= config.alignment_threshold
    
    # Decision
    take = False
    direction = None
    conf = 0.0
    
    if align_up and up_score > down_score * 1.2:
        take = True
        direction = "long"
        conf = min(1.0, up_score / (up_score + down_score + 1e-9))
    elif align_down and down_score > up_score * 1.2:
        take = True
        direction = "short"
        conf = min(1.0, down_score / (up_score + down_score + 1e-9))
    
    if not take:
        return {
            "take_trade": False,
            "reason": "no_alignment" if not (align_up or align_down) else "insufficient_edge",
            "scores": {"up": round(up_score, 3), "down": round(down_score, 3)},
            "views": [v.model_dump() for v in views]
        }
    
    # Position sizing (same as original)
    log_amihud = np.log10(max(amihud, 1e-15))
    if log_amihud <= -12:
        size_mult = 1.0
    elif log_amihud >= -8:
        size_mult = 0.25
    else:
        size_mult = 1.0 - 0.75 * (log_amihud + 12) / 4
    
    size_mult *= min(1.0, 0.5 + conf)
    
    # Time stop (extract from sentiment or default)
    flip_prob = 0.3
    for v in views:
        if v.agent == "sentiment" and v.notes and "flip_prob=" in v.notes:
            try:
                flip_prob = float(v.notes.split("flip_prob=")[1].split(",")[0])
            except:
                pass
    
    eta_bars = int(max(4, min(12, 10 * (1 - flip_prob))))
    
    return {
        "take_trade": True,
        "symbol": symbol,
        "bar": bar.isoformat(),
        "direction": direction,
        "confidence": round(conf, 3),
        "position_sizing_hint": round(size_mult, 3),
        "time_stop_bars": eta_bars,
        "scores": {"up": round(up_score, 3), "down": round(down_score, 3)},
        "views": [v.model_dump() for v in views]
    }

def backtest_strategy(
    symbol: str,
    date: str,
    config: StrategyConfig,
    l1_path: str = "data_l1",
    feature_set_id: str = "v0.1.0"
) -> StrategyResult:
    """Run backtest for a specific strategy configuration"""
    
    fs = FeatureStore(root="data", read_only=True)
    
    # Load L1 data
    l1_fn = Path(l1_path) / f"l1_{date}.parquet"
    if not l1_fn.exists():
        raise FileNotFoundError(f"No L1 data: {l1_fn}")
    
    l1 = pd.read_parquet(l1_fn)
    l1 = l1[l1["symbol"] == symbol].sort_values("t_event").reset_index(drop=True)
    
    if l1.empty:
        raise ValueError(f"No data for {symbol} on {date}")
    
    bars = l1["t_event"].tolist()
    
    # Trading state
    position = None
    trades = []
    equity_curve = []
    cash = 0.0
    size = 1.0
    
    # For Markov stateful tracking
    markov_hmm = None
    
    # Replay loop
    for i, t in enumerate(bars[:-1]):
        try:
            row = fs.read_pit(symbol, t, feature_set_id)
        except (FileNotFoundError, ValueError):
            mtm = 0.0
            if position:
                px_now = float(l1.loc[i, "price"])
                mtm = (px_now - position["entry_px"]) * position["direction"] * position["size"]
            equity_curve.append({"t": t, "equity": cash + mtm})
            continue
        
        hedge = row.get("hedge") or {}
        liq = row.get("liquidity") or {}
        sent = row.get("sentiment") or {}
        
        if not (hedge and liq and sent):
            mtm = 0.0
            if position:
                px_now = float(l1.loc[i, "price"])
                mtm = (px_now - position["entry_px"]) * position["direction"] * position["size"]
            equity_curve.append({"t": t, "equity": cash + mtm})
            continue
        
        px_now = float(l1.loc[i, "price"])
        
        # Build agent views (always compute all, filter in composer)
        views = [
            agent1_hedge(symbol, t, hedge["present"], hedge["future"]),
            agent2_liquidity(symbol, t, liq["present"], liq["future"], px_now),
            agent3_sentiment(symbol, t, sent["present"], sent["future"])
        ]
        
        # Add Wyckoff if requested
        if "wyckoff" in config.agents:
            # Compute Wyckoff features on-the-fly
            df_recent = l1.loc[max(0, i-50):i].copy()
            wyckoff = compute_wyckoff_v0(symbol, t, df_recent)
            views.append(agent4_wyckoff(symbol, t, wyckoff))
        
        # Add Markov if requested
        if "markov" in config.agents:
            df_recent = l1.loc[max(0, i-50):i].copy()
            markov = compute_markov_regime_stateful(symbol, t, df_recent)
            views.append(agent5_markov(symbol, t, markov))
        
        # Compose with config
        idea = compose_with_config(
            symbol, t, views,
            amihud=float(liq["present"]["amihud"]),
            config=config
        )
        
        # Get next bar price and slippage
        px_next = float(l1.loc[i + 1, "price"])
        amihud = float(liq["present"]["amihud"])
        log_amihud = np.log10(max(amihud, 1e-15))
        bps = max(1.0, min(15.0, 1.0 + 14.0 * (log_amihud + 11) / 3))
        slip = px_now * (bps / 1e4)
        
        # Manage position
        if position:
            position["time_stop_bars"] -= 1
            exit_reason = None
            
            if idea.get("take_trade"):
                new_dir = 1 if idea["direction"] == "long" else -1
                if new_dir != position["direction"]:
                    exit_reason = "direction_flip"
            
            if position["time_stop_bars"] <= 0 and not exit_reason:
                exit_reason = "time_stop"
            
            if exit_reason:
                exit_px = px_next - slip if position["direction"] > 0 else px_next + slip
                pnl = (exit_px - position["entry_px"]) * position["direction"] * position["size"]
                
                trade = {
                    "t_entry": position["t_entry"],
                    "t_exit": l1.loc[i + 1, "t_event"],
                    "direction": position["direction"],
                    "entry_px": position["entry_px"],
                    "exit_px": exit_px,
                    "size": position["size"],
                    "pnl": pnl,
                    "exit_reason": exit_reason
                }
                
                cash += pnl
                trades.append(trade)
                position = None
        
        # Open new position
        if not position and idea.get("take_trade"):
            direction = 1 if idea["direction"] == "long" else -1
            size_mult = float(idea.get("position_sizing_hint", 1.0))
            entry_px = px_next + slip if direction > 0 else px_next - slip
            
            position = {
                "t_entry": l1.loc[i + 1, "t_event"],
                "direction": direction,
                "entry_px": entry_px,
                "size": size * size_mult,
                "time_stop_bars": int(idea.get("time_stop_bars", 8))
            }
        
        # MTM
        mtm = 0.0
        if position:
            mtm = (px_now - position["entry_px"]) * position["direction"] * position["size"]
        equity_curve.append({"t": t, "equity": cash + mtm})
    
    # Close open position
    if position:
        last_px = float(l1.iloc[-1]["price"])
        exit_px = last_px - slip if position["direction"] > 0 else last_px + slip
        pnl = (exit_px - position["entry_px"]) * position["direction"] * position["size"]
        
        trade = {
            "t_entry": position["t_entry"],
            "t_exit": l1.iloc[-1]["t_event"],
            "direction": position["direction"],
            "entry_px": position["entry_px"],
            "exit_px": exit_px,
            "size": position["size"],
            "pnl": pnl,
            "exit_reason": "end_of_day"
        }
        
        cash += pnl
        trades.append(trade)
    
    # Calculate stats
    eq_df = pd.DataFrame(equity_curve)
    
    if len(eq_df) > 10 and len(trades) > 0:
        ret = eq_df["equity"].diff().fillna(0.0)
        sharpe = (ret.mean() / (ret.std() + 1e-9)) * np.sqrt(390)
        max_dd = float((eq_df["equity"].cummax() - eq_df["equity"]).max())
        
        winning = [t for t in trades if t["pnl"] > 0]
        win_rate = len(winning) / len(trades)
        avg_win = np.mean([t["pnl"] for t in winning]) if winning else 0.0
        losing = [t for t in trades if t["pnl"] <= 0]
        avg_loss = np.mean([t["pnl"] for t in losing]) if losing else 0.0
    else:
        sharpe = 0.0
        max_dd = 0.0
        win_rate = 0.0
        avg_win = 0.0
        avg_loss = 0.0
    
    return StrategyResult(
        config=config,
        pnl=float(cash),
        num_trades=len(trades),
        win_rate=float(win_rate),
        avg_win=float(avg_win),
        avg_loss=float(avg_loss),
        sharpe=float(sharpe),
        max_drawdown=max_dd,
        trades=trades,
        equity_curve=eq_df
    )

def compare_strategies(
    symbol: str,
    date: str,
    strategy_names: List[str] = None
) -> pd.DataFrame:
    """Run comparative backtest across multiple strategies"""
    
    if strategy_names is None:
        strategy_names = list(STRATEGIES.keys())
    
    results = []
    
    for name in strategy_names:
        config = STRATEGIES[name]
        print(f"\n🔄 Running: {config.name}")
        print(f"   {config.description}")
        
        try:
            result = backtest_strategy(symbol, date, config)
            results.append(result.summary())
            print(f"   ✅ PnL: {result.pnl:.2f}, Trades: {result.num_trades}, Win Rate: {result.win_rate:.1%}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
            continue
    
    # Create comparison DataFrame
    df = pd.DataFrame(results)
    
    if not df.empty:
        # Rank strategies
        df["rank"] = df["sharpe"].rank(ascending=False)
        df = df.sort_values("sharpe", ascending=False)
    
    return df

if __name__ == "__main__":
    import sys
    
    symbol = sys.argv[1] if len(sys.argv) > 1 else "SPY"
    date = sys.argv[2] if len(sys.argv) > 2 else "2025-11-03"
    
    print(f"\n{'='*70}")
    print(f"  COMPARATIVE BACKTEST: {symbol} on {date}")
    print(f"{'='*70}")
    
    results_df = compare_strategies(symbol, date)
    
    print(f"\n{'='*70}")
    print("  RESULTS SUMMARY")
    print(f"{'='*70}\n")
    print(results_df.to_string(index=False))
    
    # Save results
    output_file = f"comparative_backtest_{symbol}_{date}.json"
    with open(output_file, 'w') as f:
        json.dump(results_df.to_dict(orient='records'), f, indent=2, default=str)
    
    print(f"\n💾 Results saved to: {output_file}")
    
    # Highlight winner
    if not results_df.empty:
        winner = results_df.iloc[0]
        print(f"\n🏆 WINNER: {winner['name']}")
        print(f"   Sharpe: {winner['sharpe']:.3f}")
        print(f"   PnL: ${winner['pnl']:.2f}")
        print(f"   Trades: {winner['num_trades']}")
        print(f"   Win Rate: {winner['win_rate']:.1%}")
