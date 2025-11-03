#!/usr/bin/env python3
"""
Diagnostic tool to examine individual agent votes before consensus filtering.
This helps us understand why no trades were generated.
"""
import sys
import pandas as pd
from datetime import datetime
from pathlib import Path
from gnosis.feature_store.store import FeatureStore
from gnosis.agents.hedge_agent import HedgeAgent
from gnosis.agents.liquidity_agent import LiquidityAgent
from gnosis.agents.sentiment_agent import SentimentAgent
from gnosis.engines.wyckoff_v0 import compute_wyckoff_v0
from gnosis.engines.markov_regime_v0 import compute_markov_regime_v0, SimpleHMM

def analyze_agent_votes(date: str, symbol: str = "SPY"):
    """Analyze individual agent votes for a specific date."""
    
    print(f"\n{'='*80}")
    print(f"DIAGNOSTIC: Individual Agent Votes for {symbol} on {date}")
    print(f"{'='*80}\n")
    
    # Load L1 data
    l1_file = f"data_l1/l1_{date}.parquet"
    if not Path(l1_file).exists():
        print(f"⚠ No L1 data found for {date}")
        return
    
    l1 = pd.read_parquet(l1_file)
    l1 = l1[l1["symbol"] == symbol].sort_values("t_event").reset_index(drop=True)
    
    print(f"Loaded {len(l1)} L1 bars")
    print(f"Price range: ${l1.price.min():.2f} - ${l1.price.max():.2f}")
    print(f"Intraday move: {((l1.price.max() - l1.price.min()) / l1.price.min() * 100):.2f}%\n")
    
    # Load L3 features
    fs = FeatureStore(root="data")
    try:
        features_df = fs.read(symbol=symbol, start_date=date, end_date=date)
        if features_df.empty:
            print(f"⚠ No L3 features found for {date}")
            return
    except Exception as e:
        print(f"⚠ Error loading features: {e}")
        return
    
    print(f"Loaded {len(features_df)} L3 feature rows\n")
    
    # Initialize agents
    hedge_agent = HedgeAgent(threshold=0.6)
    liq_agent = LiquidityAgent(threshold=0.6)
    sent_agent = SentimentAgent(threshold=0.6)
    hmm = SimpleHMM()
    
    # Sample a few representative bars (beginning, middle, end, highest volatility)
    indices = [0, len(l1)//2, len(l1)-1]
    
    # Find highest volatility bar (largest price move in 5-minute window)
    l1['volatility'] = l1['price'].rolling(5).std()
    max_vol_idx = l1['volatility'].idxmax()
    indices.append(max_vol_idx)
    
    print("Analyzing representative time points:\n")
    
    for idx in sorted(set(indices)):
        if idx >= len(l1):
            continue
            
        t = l1.loc[idx, 't_event']
        price = l1.loc[idx, 'price']
        
        # Get recent window
        df_recent = l1.iloc[max(0, idx-60):idx+1].copy()
        
        if len(df_recent) < 20:
            continue
        
        print(f"\n{'─'*80}")
        print(f"Time: {t} | Price: ${price:.2f} | Position in day: {idx}/{len(l1)}")
        print(f"{'─'*80}")
        
        # Get L3 features if available
        features = features_df[features_df['bar'] == t]
        if not features.empty:
            feat = features.iloc[0]
            
            # Hedge agent
            hedge_vote = hedge_agent.vote(feat['hedge'])
            print(f"  [Hedge]     Position: {hedge_vote.position:+2d} | Confidence: {hedge_vote.confidence:.3f}")
            print(f"              Skew: {feat['hedge'].get('skew_metric', 'N/A'):.3f} | "
                  f"Gamma: {feat['hedge'].get('gamma_exposure', 'N/A'):.3f}")
            
            # Liquidity agent
            liq_vote = liq_agent.vote(feat['liquidity'])
            print(f"  [Liquidity] Position: {liq_vote.position:+2d} | Confidence: {liq_vote.confidence:.3f}")
            print(f"              Spread: {feat['liquidity'].get('spread_bps', 'N/A'):.1f} bps | "
                  f"Amihud: {feat['liquidity'].get('amihud', 'N/A'):.2e}")
            
            # Sentiment agent
            sent_vote = sent_agent.vote(feat['sentiment'])
            print(f"  [Sentiment] Position: {sent_vote.position:+2d} | Confidence: {sent_vote.confidence:.3f}")
            print(f"              Momentum: {feat['sentiment'].get('momentum_5m', 'N/A'):.3f} | "
                  f"Volatility: {feat['sentiment'].get('volatility_z', 'N/A'):.2f}")
        
        # Compute Wyckoff
        wyckoff = compute_wyckoff_v0(symbol, t, df_recent)
        print(f"  [Wyckoff]   Phase: {wyckoff['phase']} | Confidence: {wyckoff['confidence']:.3f}")
        print(f"              Volume Divergence: {wyckoff['volume_divergence']:.3f} | "
              f"Spring: {wyckoff['spring_detected']}")
        
        # Compute Markov
        markov = compute_markov_regime_v0(symbol, t, df_recent, hmm)
        print(f"  [Markov]    State: {markov['current_state']} | Confidence: {markov['confidence']:.3f}")
        probs = markov['state_probabilities']
        top_state = max(probs.items(), key=lambda x: x[1])
        print(f"              Top State: {top_state[0]} ({top_state[1]:.1%})")
        
        # Consensus check
        print(f"\n  Consensus Analysis:")
        if not features.empty:
            votes = [
                (hedge_vote.position, hedge_vote.confidence, "Hedge"),
                (liq_vote.position, liq_vote.confidence, "Liquidity"),
                (sent_vote.position, sent_vote.confidence, "Sentiment")
            ]
            
            high_conf_votes = [(pos, name) for pos, conf, name in votes if conf >= 0.6]
            
            if len(high_conf_votes) >= 2:
                positions = [pos for pos, _ in high_conf_votes]
                if len(set(positions)) == 1 and positions[0] != 0:
                    print(f"    ✓ TRADE SIGNAL: {len(high_conf_votes)} agents agree on {positions[0]:+d}")
                    print(f"      Agents: {', '.join([name for _, name in high_conf_votes])}")
                else:
                    print(f"    ✗ No alignment: {len(high_conf_votes)} high-conf votes but disagree on position")
            else:
                print(f"    ✗ Insufficient high-confidence votes: {len(high_conf_votes)}/2 required")
                if high_conf_votes:
                    print(f"      High-conf agents: {', '.join([name for _, name in high_conf_votes])}")
    
    print(f"\n{'='*80}\n")

def main():
    if len(sys.argv) < 2:
        print("Usage: python diagnostic_agent_votes.py <date> [symbol]")
        print("Example: python diagnostic_agent_votes.py 2025-10-29 SPY")
        return 1
    
    date = sys.argv[1]
    symbol = sys.argv[2] if len(sys.argv) > 2 else "SPY"
    
    analyze_agent_votes(date, symbol)
    return 0

if __name__ == '__main__':
    sys.exit(main())
