#!/usr/bin/env python3
"""
Simple diagnostic: Sample a few bars and show raw agent outputs.
"""
import sys
import pandas as pd
from pathlib import Path
from datetime import datetime
from gnosis.feature_store.store import FeatureStore
from gnosis.agents.agents_v1 import agent1_hedge, agent2_liquidity, agent3_sentiment
from gnosis.engines.wyckoff_v0 import compute_wyckoff_v0
from gnosis.engines.markov_regime_v0 import compute_markov_regime_v0, SimpleHMM
from gnosis.backtest.comparative_backtest import agent4_wyckoff, agent5_markov

def analyze_bar(date: str, bar_idx: int, symbol: str = "SPY"):
    """Analyze a specific bar"""
    
    # Load L1 data
    l1_file = f"data_l1/l1_{date}.parquet"
    if not Path(l1_file).exists():
        print(f"⚠ No L1 data for {date}")
        return
    
    l1 = pd.read_parquet(l1_file)
    l1 = l1[l1["symbol"] == symbol].sort_values("t_event").reset_index(drop=True)
    
    if bar_idx >= len(l1):
        print(f"⚠ Bar index {bar_idx} out of range (max: {len(l1)-1})")
        return
    
    t = l1.loc[bar_idx, 't_event']
    price = l1.loc[bar_idx, 'price']
    
    print(f"\n{'='*80}")
    print(f"{symbol} @ {t} (Bar {bar_idx}/{len(l1)})")
    print(f"Price: ${price:.2f}")
    print(f"{'='*80}\n")
    
    # Load L3 features
    fs = FeatureStore(root="data")
    try:
        features_df = fs.read(symbol=symbol, start_date=date, end_date=date)
        feat_row = features_df[features_df['bar'] == t]
        
        if feat_row.empty:
            print("⚠ No L3 features for this bar")
            has_features = False
        else:
            feat = feat_row.iloc[0]
            has_features = True
    except Exception as e:
        print(f"⚠ Error loading features: {e}")
        has_features = False
    
    # Compute Wyckoff and Markov manually
    df_recent = l1.iloc[max(0, bar_idx-60):bar_idx+1].copy()
    
    wyckoff_dict = compute_wyckoff_v0(symbol, t, df_recent)
    hmm = SimpleHMM()
    markov_dict = compute_markov_regime_v0(symbol, t, df_recent, hmm)
    
    # Call agents
    if has_features:
        hedge_view = agent1_hedge(symbol, t, feat['hedge'], {})
        liq_view = agent2_liquidity(symbol, t, feat['liquidity'], {}, price)
        sent_view = agent3_sentiment(symbol, t, feat['sentiment'], {})
        
        print(f"[Hedge]     {hedge_view.dir_bias:+.1f} @ {hedge_view.confidence:.2f} | {hedge_view.thesis}")
        print(f"            {hedge_view.notes}")
        
        print(f"\n[Liquidity] {liq_view.dir_bias:+.1f} @ {liq_view.confidence:.2f} | {liq_view.thesis}")
        print(f"            {liq_view.notes}")
        
        print(f"\n[Sentiment] {sent_view.dir_bias:+.1f} @ {sent_view.confidence:.2f} | {sent_view.thesis}")
        print(f"            {sent_view.notes}")
    
    wyckoff_view = agent4_wyckoff(symbol, t, wyckoff_dict)
    markov_view = agent5_markov(symbol, t, markov_dict)
    
    print(f"\n[Wyckoff]   {wyckoff_view.dir_bias:+.1f} @ {wyckoff_view.confidence:.2f} | {wyckoff_view.thesis}")
    print(f"            {wyckoff_view.notes}")
    
    print(f"\n[Markov]    {markov_view.dir_bias:+.1f} @ {markov_view.confidence:.2f} | {markov_view.thesis}")
    print(f"            {markov_view.notes}")
    
    # Check consensus
    if has_features:
        print(f"\n{'─'*80}")
        print("CONSENSUS CHECK (2-of-3 baseline)")
        print(f"{'─'*80}")
        
        votes = [
            ("Hedge", hedge_view.dir_bias, hedge_view.confidence),
            ("Liquidity", liq_view.dir_bias, liq_view.confidence),
            ("Sentiment", sent_view.dir_bias, sent_view.confidence)
        ]
        
        high_conf = [v for v in votes if v[2] >= 0.6]
        
        print(f"High-confidence agents (≥0.6): {len(high_conf)}/3")
        for name, bias, conf in high_conf:
            print(f"  {name}: {bias:+.1f} @ {conf:.2f}")
        
        if len(high_conf) >= 2:
            positions = [v[1] for v in high_conf]
            pos_counts = {}
            for p in positions:
                if p > 0.1:
                    pos_counts['long'] = pos_counts.get('long', 0) + 1
                elif p < -0.1:
                    pos_counts['short'] = pos_counts.get('short', 0) + 1
                else:
                    pos_counts['neutral'] = pos_counts.get('neutral', 0) + 1
            
            max_align = max(pos_counts.values()) if pos_counts else 0
            
            if max_align >= 2:
                aligned_pos = [k for k, v in pos_counts.items() if v == max_align][0]
                print(f"\n✓ ALIGNMENT: {max_align} agents agree on {aligned_pos.upper()}")
            else:
                print(f"\n✗ NO ALIGNMENT: Agents disagree")
        else:
            print(f"\n✗ INSUFFICIENT: Need 2+ high-confidence votes")
    
    print(f"\n{'='*80}\n")

def main():
    if len(sys.argv) < 2:
        print("Usage: python simple_diagnostic.py <date> [bar_indices...]")
        print("Example: python simple_diagnostic.py 2025-10-29 50 150 250 350")
        return 1
    
    date = sys.argv[1]
    
    # Default to sampling bars across the day
    if len(sys.argv) > 2:
        bar_indices = [int(x) for x in sys.argv[2:]]
    else:
        bar_indices = [50, 150, 250, 350]  # Sample across typical trading day
    
    for idx in bar_indices:
        analyze_bar(date, idx)
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
