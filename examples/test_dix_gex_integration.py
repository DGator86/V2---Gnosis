"""
Test DIX/GEX Integration with Options Workflow
===============================================

This script demonstrates how DIX (Dark Index) and GEX (Gamma Exposure)
data enhances the DHPE options validation workflow.

Combined Signals:
-----------------
DHPE Energy State + DIX + GEX = Enhanced Prediction

Example Scenarios:
1. DHPE Bullish + High DIX + Negative GEX = STRONG BULLISH (breakout potential)
2. DHPE Bearish + Low DIX + Large Negative GEX = DANGER (crash risk)
3. DHPE Neutral + High GEX = RANGEBOUND (sell premium strategies)

Author: Super Gnosis Development Team
Version: 3.0.1
"""

from datetime import datetime, date, timedelta
import polars as pl
from loguru import logger

from engines.inputs.dix_gex_adapter import DIXGEXAdapter


def test_dix_gex_fetching():
    """Test DIX/GEX data fetching and interpretation."""
    
    logger.info("="*70)
    logger.info("DIX/GEX INTEGRATION TEST")
    logger.info("="*70)
    
    adapter = DIXGEXAdapter()
    
    # ========================================================================
    # TEST 1: Fetch DIX/GEX Data
    # ========================================================================
    
    logger.info("\n" + "="*70)
    logger.info("TEST 1: Fetch DIX/GEX Historical Data")
    logger.info("="*70)
    
    df = adapter.fetch_dix_gex(lookback_days=30)
    
    logger.info(f"\n📊 DATA FETCHED:")
    logger.info(f"   Records: {len(df)}")
    logger.info(f"   Date Range: {df['date'][0]} to {df['date'][-1]}")
    logger.info(f"   Source: {df['source'][0]}")
    
    logger.info(f"\n📋 Sample Data:")
    print(df.head(5))
    
    # ========================================================================
    # TEST 2: Current Values and Statistics
    # ========================================================================
    
    logger.info("\n" + "="*70)
    logger.info("TEST 2: Current Values and Statistics")
    logger.info("="*70)
    
    if 'dix' in df.columns:
        current_dix = df['dix'][-1]
        avg_dix = df['dix'].mean()
        
        logger.info(f"\n💼 DIX (Dark Index):")
        logger.info(f"   Current: {current_dix:.3f}")
        logger.info(f"   30-Day Average: {avg_dix:.3f}")
        logger.info(f"   Range: {df['dix'].min():.3f} - {df['dix'].max():.3f}")
        
        if current_dix > avg_dix:
            logger.info(f"   📈 Above average → Institutions accumulating")
        else:
            logger.info(f"   📉 Below average → Institutions distributing")
    
    if 'gex' in df.columns:
        current_gex = df['gex'][-1]
        avg_gex = df['gex'].mean()
        
        logger.info(f"\n⚡ GEX (Gamma Exposure):")
        logger.info(f"   Current: ${current_gex:.2f}B")
        logger.info(f"   30-Day Average: ${avg_gex:.2f}B")
        logger.info(f"   Range: ${df['gex'].min():.2f}B - ${df['gex'].max():.2f}B")
        
        if current_gex > 0:
            logger.info(f"   🔒 Positive GEX → Market makers stabilizing")
        else:
            logger.info(f"   💥 Negative GEX → Market makers amplifying moves")
    
    # ========================================================================
    # TEST 3: Market Interpretation
    # ========================================================================
    
    logger.info("\n" + "="*70)
    logger.info("TEST 3: Market Interpretation")
    logger.info("="*70)
    
    if 'dix' in df.columns and 'gex' in df.columns:
        interpretations = adapter.interpret_dix_gex(current_dix, current_gex)
        
        logger.info(f"\n🎯 CURRENT MARKET SIGNAL:")
        logger.info(f"   DIX Interpretation: {interpretations['dix']}")
        logger.info(f"   GEX Interpretation: {interpretations['gex']}")
        logger.info(f"   Combined Signal: {interpretations['combined']}")
    
    # ========================================================================
    # TEST 4: Historical Signal Quality
    # ========================================================================
    
    logger.info("\n" + "="*70)
    logger.info("TEST 4: Historical Signal Patterns")
    logger.info("="*70)
    
    if 'dix' in df.columns and 'gex' in df.columns:
        # Classify each day
        signals = []
        for i in range(len(df)):
            dix_val = df['dix'][i]
            gex_val = df['gex'][i]
            interp = adapter.interpret_dix_gex(dix_val, gex_val)
            signals.append(interp['combined'])
        
        # Count signal types
        from collections import Counter
        signal_counts = Counter(signals)
        
        logger.info(f"\n📊 SIGNAL DISTRIBUTION (last {len(df)} days):")
        for signal, count in signal_counts.most_common():
            pct = count / len(signals) * 100
            logger.info(f"   {signal}: {count} days ({pct:.1f}%)")
    
    # ========================================================================
    # TEST 5: Integration with Options Strategy
    # ========================================================================
    
    logger.info("\n" + "="*70)
    logger.info("TEST 5: Strategy Recommendations")
    logger.info("="*70)
    
    if 'dix' in df.columns and 'gex' in df.columns:
        current_signal = interpretations['combined']
        
        logger.info(f"\n💡 TRADING STRATEGY BASED ON DIX/GEX:")
        
        if "BULLISH" in current_signal and current_gex < 0:
            logger.info(f"   ✅ AGGRESSIVE BULLISH SETUP:")
            logger.info(f"      • Buy slightly OTM calls (1-2 strikes)")
            logger.info(f"      • Expect explosive upside (negative GEX)")
            logger.info(f"      • Set wider stops (high volatility)")
            logger.info(f"      • Target: 20-50% gains")
        
        elif "BULLISH" in current_signal and current_gex > 5.0:
            logger.info(f"   ✅ CONSERVATIVE BULLISH SETUP:")
            logger.info(f"      • Buy ATM or slightly ITM calls")
            logger.info(f"      • Expect slow grind up (positive GEX)")
            logger.info(f"      • Tighter stops (low volatility)")
            logger.info(f"      • Target: 10-20% gains")
        
        elif "BEARISH" in current_signal and current_gex < -3.0:
            logger.info(f"   ⚠️  DANGER - CRASH SETUP:")
            logger.info(f"      • Buy protective puts")
            logger.info(f"      • Consider cash position")
            logger.info(f"      • Avoid selling premium")
            logger.info(f"      • High downside risk")
        
        elif "NEUTRAL" in current_signal and current_gex > 5.0:
            logger.info(f"   🔄 RANGEBOUND SETUP:")
            logger.info(f"      • Sell OTM credit spreads")
            logger.info(f"      • Sell covered calls")
            logger.info(f"      • Iron condors")
            logger.info(f"      • Collect premium in range")
        
        else:
            logger.info(f"   ⏸️  MIXED SIGNALS:")
            logger.info(f"      • Wait for clearer setup")
            logger.info(f"      • Reduce position size")
            logger.info(f"      • Focus on DHPE energy state")
    
    # ========================================================================
    # TEST 6: Calculate GEX from Options
    # ========================================================================
    
    logger.info("\n" + "="*70)
    logger.info("TEST 6: Calculate GEX from Options Chain (Demo)")
    logger.info("="*70)
    
    # Create sample options chain for demonstration
    strikes = [440, 445, 450, 455, 460]
    sample_options = []
    
    for strike in strikes:
        sample_options.append({
            'strike': strike,
            'option_type': 'call',
            'call_gamma': 0.05,
            'put_gamma': 0.03,
            'call_oi': 10000,
            'put_oi': 8000
        })
    
    sample_chain = pl.DataFrame(sample_options)
    spot = 450.0
    
    calculated_gex = adapter.calculate_gex_from_options(sample_chain, spot)
    
    logger.info(f"\n⚡ CALCULATED GEX:")
    logger.info(f"   Spot Price: ${spot:.2f}")
    logger.info(f"   Calculated GEX: ${calculated_gex:.2f}B")
    logger.info(f"   (This is from sample data for demonstration)")
    
    # ========================================================================
    # SUMMARY
    # ========================================================================
    
    logger.info("\n" + "="*70)
    logger.info("TEST SUMMARY")
    logger.info("="*70)
    
    logger.info(f"\n✅ DIX/GEX Integration Tests Complete!")
    
    logger.info(f"\n📊 KEY TAKEAWAYS:")
    logger.info(f"   1. DIX shows institutional sentiment (accumulation/distribution)")
    logger.info(f"   2. GEX shows market maker gamma exposure (volatility regime)")
    logger.info(f"   3. Combined with DHPE energy states = Enhanced predictions")
    logger.info(f"   4. Different signal combinations = Different strategies")
    
    logger.info(f"\n🎯 NEXT STEPS:")
    logger.info(f"   1. Integrate DIX/GEX with options validation workflow")
    logger.info(f"   2. Combine signals: DHPE + DIX + GEX")
    logger.info(f"   3. Adjust position sizing based on volatility regime")
    logger.info(f"   4. Backtest combined strategy accuracy")
    
    logger.info("\n" + "="*70)


if __name__ == "__main__":
    test_dix_gex_fetching()
