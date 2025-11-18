#!/usr/bin/env python3
"""
Debug scanner to see why no opportunities are found.
"""

import logging
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s - %(name)s - %(message)s')

from config.loader import load_config
from engines.inputs.yfinance_adapter import create_yfinance_adapters
from engines.hedge.hedge_engine_v3 import HedgeEngineV3
from engines.liquidity.liquidity_engine_v1 import LiquidityEngineV1
from engines.sentiment.sentiment_engine_v1 import SentimentEngineV1
from engines.sentiment.processors import NewsSentimentProcessor, FlowSentimentProcessor, TechnicalSentimentProcessor
from engines.elasticity.elasticity_engine_v1 import ElasticityEngineV1
from engines.scanner.opportunity_scanner import OpportunityScanner

def main():
    # Load config
    config = load_config()
    
    # Create adapters
    print("\n" + "="*80)
    print("Creating Yahoo Finance adapters...")
    print("="*80)
    market_adapter, options_adapter, news_adapter = create_yfinance_adapters()
    
    # Build engines
    print("\n" + "="*80)
    print("Building engines...")
    print("="*80)
    
    hedge_engine = HedgeEngineV3(options_adapter, config.engines.hedge.model_dump())
    liquidity_engine = LiquidityEngineV1(market_adapter, config.engines.liquidity.model_dump())
    
    sentiment_engine = SentimentEngineV1(
        [
            NewsSentimentProcessor(news_adapter, config.engines.sentiment.model_dump()),
            FlowSentimentProcessor(config.engines.sentiment.model_dump()),
            TechnicalSentimentProcessor(market_adapter, config.engines.sentiment.model_dump()),
        ],
        config.engines.sentiment.model_dump(),
    )
    
    elasticity_engine = ElasticityEngineV1(market_adapter, config.engines.elasticity.model_dump())
    
    # Create scanner
    print("\n" + "="*80)
    print("Creating scanner...")
    print("="*80)
    
    scanner = OpportunityScanner(
        hedge_engine=hedge_engine,
        liquidity_engine=liquidity_engine,
        sentiment_engine=sentiment_engine,
        elasticity_engine=elasticity_engine,
        options_adapter=options_adapter,
        market_adapter=market_adapter,
    )
    
    # Test scan with just SPY
    print("\n" + "="*80)
    print("🔍 DEBUG SCAN: SPY")
    print("="*80)
    print("\nScanning with prefilter thresholds:")
    print("  - min_price: $10.00")
    print("  - max_price: $1000.00")
    print("  - min_volume: 1,000,000")
    print("\n")
    
    result = scanner.scan(
        universe=['SPY'],
        top_n=1,
        min_price=10.0,
        max_price=1000.0,
        min_volume=1_000_000
    )
    
    print("\n" + "="*80)
    print("RESULTS")
    print("="*80)
    print(f"Opportunities found: {len(result.opportunities)}")
    print(f"Scan duration: {result.scan_duration_seconds:.2f}s")
    
    if result.opportunities:
        opp = result.opportunities[0]
        print(f"\n✓ {opp.symbol}")
        print(f"  Score: {opp.score:.3f}")
        print(f"  Type: {opp.opportunity_type}")
        print(f"  Direction: {opp.direction} (confidence: {opp.confidence:.2f})")
        print(f"  Reasoning: {opp.reasoning}")
    else:
        print("\n❌ No opportunities found")
        print("\nTrying scan with RELAXED thresholds (min_volume=100,000)...")
        
        result2 = scanner.scan(
            universe=['SPY'],
            top_n=1,
            min_price=1.0,
            max_price=10000.0,
            min_volume=100_000  # Much lower threshold
        )
        
        print(f"\nWith relaxed thresholds: {len(result2.opportunities)} opportunities")
        
        if result2.opportunities:
            opp = result2.opportunities[0]
            print(f"\n✓ {opp.symbol}")
            print(f"  Score: {opp.score:.3f}")
            print(f"  Type: {opp.opportunity_type}")

if __name__ == "__main__":
    main()
