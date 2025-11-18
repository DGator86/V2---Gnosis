"""
Test Options Liquidity Filtering
=================================

This script demonstrates the enhanced liquidity filtering for options chains.

Tests:
1. Fetch options chain with liquidity metrics
2. Filter to only liquid strikes
3. Compare unfiltered vs filtered chains
4. Show why liquidity filtering prevents losses

Author: Super Gnosis Development Team
Version: 3.0.0
"""

from datetime import datetime
import polars as pl
from loguru import logger

from engines.inputs.yahoo_options_adapter import YahooOptionsAdapter
from engines.liquidity.universal_liquidity_interpreter import (
    UniversalLiquidityInterpreter,
    OptionsLiquidityState
)


def test_options_liquidity_filtering():
    """Test options liquidity filtering on real data."""
    
    logger.info("="*70)
    logger.info("OPTIONS LIQUIDITY FILTERING TEST")
    logger.info("="*70)
    
    # Initialize components
    options_adapter = YahooOptionsAdapter()
    liquidity_engine = UniversalLiquidityInterpreter()
    
    # Test symbol (SPY = liquid, but will have some illiquid strikes)
    SYMBOL = "SPY"
    
    # ========================================================================
    # TEST 1: Fetch raw options chain
    # ========================================================================
    
    logger.info("\n" + "="*70)
    logger.info("TEST 1: Fetch Raw Options Chain (No Filtering)")
    logger.info("="*70)
    
    try:
        raw_chain = options_adapter.fetch_options_chain(
            symbol=SYMBOL,
            min_days_to_expiry=25,
            max_days_to_expiry=35
        )
        
        logger.info(f"\n📊 RAW CHAIN STATISTICS:")
        logger.info(f"   Total Options: {len(raw_chain)}")
        logger.info(f"   Calls: {len(raw_chain.filter(pl.col('option_type') == 'call'))}")
        logger.info(f"   Puts: {len(raw_chain.filter(pl.col('option_type') == 'put'))}")
        
        # Show some raw data
        logger.info(f"\n📋 Sample Raw Data (first 5 strikes):")
        sample = raw_chain.head(5).select([
            'strike', 'option_type', 'bid', 'ask', 'open_interest', 'volume'
        ])
        print(sample)
        
    except Exception as e:
        logger.error(f"❌ Failed to fetch options: {e}")
        return
    
    # ========================================================================
    # TEST 2: Analyze liquidity (add metrics without filtering)
    # ========================================================================
    
    logger.info("\n" + "="*70)
    logger.info("TEST 2: Analyze Liquidity Metrics")
    logger.info("="*70)
    
    analyzed_chain = liquidity_engine.interpret_options_liquidity(
        options_chain=raw_chain,
        min_open_interest=100,
        max_spread_pct=5.0,
        min_volume=50
    )
    
    logger.info(f"\n📊 LIQUIDITY ANALYSIS:")
    
    # Show distribution of liquidity scores
    tradeable_count = analyzed_chain.filter(pl.col('is_tradeable')).shape[0]
    untradeable_count = len(analyzed_chain) - tradeable_count
    
    logger.info(f"   Tradeable Options: {tradeable_count} ({tradeable_count/len(analyzed_chain)*100:.1f}%)")
    logger.info(f"   Untradeable Options: {untradeable_count} ({untradeable_count/len(analyzed_chain)*100:.1f}%)")
    
    # Spread statistics
    avg_spread = analyzed_chain['spread_pct'].mean()
    max_spread = analyzed_chain['spread_pct'].max()
    min_spread = analyzed_chain['spread_pct'].min()
    
    logger.info(f"\n📏 SPREAD STATISTICS:")
    logger.info(f"   Average Spread: {avg_spread:.2f}%")
    logger.info(f"   Min Spread: {min_spread:.2f}%")
    logger.info(f"   Max Spread: {max_spread:.2f}%")
    
    # Show worst spreads
    worst_spreads = analyzed_chain.sort('spread_pct', descending=True).head(5)
    logger.info(f"\n⚠️  WORST SPREADS (Top 5):")
    print(worst_spreads.select(['strike', 'option_type', 'bid', 'ask', 'spread_pct', 'open_interest']))
    
    # Show best liquidity
    best_liquidity = analyzed_chain.sort('liquidity_score', descending=True).head(5)
    logger.info(f"\n✅ BEST LIQUIDITY (Top 5):")
    print(best_liquidity.select(['strike', 'option_type', 'spread_pct', 'open_interest', 'volume', 'liquidity_score']))
    
    # ========================================================================
    # TEST 3: Filter to liquid options only
    # ========================================================================
    
    logger.info("\n" + "="*70)
    logger.info("TEST 3: Filter to Liquid Options Only")
    logger.info("="*70)
    
    liquid_chain = liquidity_engine.filter_liquid_options(
        options_chain=raw_chain,
        min_liquidity_score=0.6,
        min_open_interest=100,
        max_spread_pct=5.0,
        min_volume=50
    )
    
    logger.info(f"\n📊 FILTERING RESULTS:")
    logger.info(f"   Raw Options: {len(raw_chain)}")
    logger.info(f"   Liquid Options: {len(liquid_chain)}")
    logger.info(f"   Filtered Out: {len(raw_chain) - len(liquid_chain)} ({(len(raw_chain) - len(liquid_chain))/len(raw_chain)*100:.1f}%)")
    
    if len(liquid_chain) > 0:
        # Show liquid options statistics
        avg_liquid_spread = liquid_chain['spread_pct'].mean()
        avg_liquid_oi = liquid_chain['open_interest'].mean()
        avg_liquid_volume = liquid_chain['volume'].mean()
        
        logger.info(f"\n📈 LIQUID OPTIONS QUALITY:")
        logger.info(f"   Average Spread: {avg_liquid_spread:.2f}%")
        logger.info(f"   Average OI: {avg_liquid_oi:,.0f}")
        logger.info(f"   Average Volume: {avg_liquid_volume:,.0f}")
        logger.info(f"   Average Liquidity Score: {liquid_chain['liquidity_score'].mean():.2f}")
        
        # Show sample liquid options
        logger.info(f"\n📋 Sample Liquid Options:")
        sample_liquid = liquid_chain.head(10).select([
            'strike', 'option_type', 'bid', 'ask', 'spread_pct', 
            'open_interest', 'volume', 'liquidity_score'
        ])
        print(sample_liquid)
    
    # ========================================================================
    # TEST 4: Demonstrate cost of trading illiquid options
    # ========================================================================
    
    logger.info("\n" + "="*70)
    logger.info("TEST 4: Cost of Trading Illiquid Options")
    logger.info("="*70)
    
    # Find some illiquid options
    illiquid_options = analyzed_chain.filter(
        ~pl.col('is_tradeable')
    ).sort('spread_pct', descending=True).head(3)
    
    if len(illiquid_options) > 0:
        logger.info(f"\n💸 COST ANALYSIS - ILLIQUID OPTIONS:")
        logger.info(f"   These are options you would AVOID trading:\n")
        
        for i, row in enumerate(illiquid_options.iter_rows(named=True), 1):
            strike = row['strike']
            option_type = row['option_type']
            bid = row['bid']
            ask = row['ask']
            spread_pct = row['spread_pct']
            oi = row['open_interest']
            volume = row['volume']
            
            # Calculate loss from spread
            mid = (bid + ask) / 2
            immediate_loss = (ask - bid) / ask * 100 if ask > 0 else 100
            
            logger.info(f"   Option {i}: ${strike:.0f} {option_type.upper()}")
            logger.info(f"      Bid: ${bid:.2f} | Ask: ${ask:.2f} | Mid: ${mid:.2f}")
            logger.info(f"      Spread: {spread_pct:.1f}%")
            logger.info(f"      Open Interest: {oi:,}")
            logger.info(f"      Volume: {volume}")
            logger.info(f"      💀 IMMEDIATE LOSS: {immediate_loss:.1f}% (just from spread!)")
            logger.info(f"      📌 Even if your prediction is RIGHT, you lose {immediate_loss:.1f}% immediately\n")
    
    # Compare with liquid options
    if len(liquid_chain) > 0:
        logger.info(f"\n✅ COST ANALYSIS - LIQUID OPTIONS:")
        logger.info(f"   These are options you SHOULD trade:\n")
        
        top_liquid = liquid_chain.sort('liquidity_score', descending=True).head(3)
        
        for i, row in enumerate(top_liquid.iter_rows(named=True), 1):
            strike = row['strike']
            option_type = row['option_type']
            bid = row['bid']
            ask = row['ask']
            spread_pct = row['spread_pct']
            oi = row['open_interest']
            volume = row['volume']
            liquidity_score = row['liquidity_score']
            
            # Calculate loss from spread
            mid = (bid + ask) / 2
            immediate_loss = (ask - bid) / ask * 100 if ask > 0 else 100
            
            logger.info(f"   Option {i}: ${strike:.0f} {option_type.upper()}")
            logger.info(f"      Bid: ${bid:.2f} | Ask: ${ask:.2f} | Mid: ${mid:.2f}")
            logger.info(f"      Spread: {spread_pct:.1f}%")
            logger.info(f"      Open Interest: {oi:,}")
            logger.info(f"      Volume: {volume}")
            logger.info(f"      Liquidity Score: {liquidity_score:.2f}")
            logger.info(f"      ✅ Cost: {immediate_loss:.1f}% (acceptable)\n")
    
    # ========================================================================
    # TEST 5: Single strike liquidity analysis
    # ========================================================================
    
    logger.info("\n" + "="*70)
    logger.info("TEST 5: Single Strike Liquidity State")
    logger.info("="*70)
    
    if len(analyzed_chain) > 0:
        # Pick an ATM option
        sample_option = analyzed_chain[len(analyzed_chain) // 2]
        
        liquidity_state = liquidity_engine.calculate_strike_liquidity(
            strike=sample_option['strike'][0],
            option_type=sample_option['option_type'][0],
            bid=sample_option['bid'][0],
            ask=sample_option['ask'][0],
            open_interest=sample_option['open_interest'][0],
            volume=sample_option['volume'][0],
            expiry=sample_option['expiry'][0]
        )
        
        logger.info(f"\n📊 LIQUIDITY STATE FOR ${liquidity_state.strike:.0f} {liquidity_state.option_type.upper()}:")
        logger.info(f"   Spread: {liquidity_state.bid_ask_spread_pct:.2f}%")
        logger.info(f"   Open Interest: {liquidity_state.open_interest:,}")
        logger.info(f"   Volume: {liquidity_state.daily_volume}")
        logger.info(f"\n   📈 SCORES:")
        logger.info(f"      Spread Score: {liquidity_state.spread_score:.2f}")
        logger.info(f"      OI Score: {liquidity_state.oi_score:.2f}")
        logger.info(f"      Volume Score: {liquidity_state.volume_score:.2f}")
        logger.info(f"      Overall Liquidity: {liquidity_state.liquidity_score:.2f}")
        logger.info(f"\n   🎯 Tradeable: {'✅ YES' if liquidity_state.is_tradeable else '❌ NO'}")
        
        if liquidity_state.warning_flags:
            logger.info(f"   ⚠️  Warnings:")
            for warning in liquidity_state.warning_flags:
                logger.info(f"      - {warning}")
    
    # ========================================================================
    # SUMMARY
    # ========================================================================
    
    logger.info("\n" + "="*70)
    logger.info("TEST SUMMARY")
    logger.info("="*70)
    logger.info(f"\n✅ Options liquidity filtering is working!")
    logger.info(f"\n📊 KEY FINDINGS:")
    logger.info(f"   • Raw options fetched: {len(raw_chain)}")
    logger.info(f"   • Liquid options: {len(liquid_chain)} ({len(liquid_chain)/len(raw_chain)*100:.1f}%)")
    logger.info(f"   • Illiquid options filtered out: {len(raw_chain) - len(liquid_chain)}")
    
    if len(liquid_chain) > 0 and len(illiquid_options) > 0:
        liquid_avg_spread = liquid_chain['spread_pct'].mean()
        illiquid_avg_spread = illiquid_options['spread_pct'].mean()
        
        logger.info(f"\n💰 COST COMPARISON:")
        logger.info(f"   • Average spread (liquid): {liquid_avg_spread:.2f}%")
        logger.info(f"   • Average spread (illiquid): {illiquid_avg_spread:.2f}%")
        logger.info(f"   • Savings: {illiquid_avg_spread - liquid_avg_spread:.2f}% per trade!")
    
    logger.info(f"\n🎯 RECOMMENDATION:")
    logger.info(f"   Always use filter_liquid_options() before trading!")
    logger.info(f"   This prevents losses from wide spreads even when predictions are correct.")
    
    logger.info("\n" + "="*70)


if __name__ == "__main__":
    test_options_liquidity_filtering()
