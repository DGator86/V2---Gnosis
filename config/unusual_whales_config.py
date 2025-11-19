"""
Unusual Whales Primary Data Source Configuration
=================================================

This configuration makes Unusual Whales the PRIMARY data source for:
- Market quotes and OHLCV data
- Options chains with full Greeks
- Options flow and unusual activity
- Market sentiment and tide
- Congressional and insider trades

All other data sources become SECONDARY fallbacks.
"""

import os
from typing import Dict, Any, Optional
from loguru import logger

from engines.inputs.unusual_whales_primary_adapter import (
    UnusualWhalesPrimaryAdapter,
    create_primary_adapter,
    replace_all_adapters
)


class UnusualWhalesConfig:
    """
    Configuration for Unusual Whales as primary data source.
    """
    
    # API Configuration
    API_KEY = os.getenv("UNUSUAL_WHALES_API_KEY")
    USE_TEST_KEY = os.getenv("UW_USE_TEST_KEY", "false").lower() == "true"
    
    # Data Source Priority
    PRIMARY_SOURCE = "unusual_whales"
    FALLBACK_SOURCES = ["alpaca", "public", "yahoo"]  # In order of preference
    
    # Cache Settings
    QUOTE_CACHE_TTL = 60  # seconds
    CHAIN_CACHE_TTL = 120  # seconds
    FLOW_CACHE_TTL = 30  # seconds
    SENTIMENT_CACHE_TTL = 60  # seconds
    
    # Flow Thresholds
    MIN_FLOW_PREMIUM = 100000  # Minimum premium for significant flow
    MIN_UNUSUAL_PREMIUM = 500000  # Minimum for unusual activity alerts
    MIN_BLOCK_SIZE = 1000000  # Minimum for block trades
    
    # Scanning Configuration
    DEFAULT_SCAN_SYMBOLS = [
        # Major Indices
        "SPY", "QQQ", "IWM", "DIA",
        # Mega Cap Tech
        "AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "NVDA",
        # High Options Volume
        "AMD", "NFLX", "BABA", "NIO", "PLTR", "SOFI",
        # Volatility
        "AMC", "GME", "COIN", "RIOT"
    ]
    
    # Alert Thresholds
    ALERT_THRESHOLDS = {
        "extreme_bullish": 0.8,  # 80%+ bullish flow
        "extreme_bearish": 0.8,  # 80%+ bearish flow
        "high_gamma": 1000000,  # Gamma exposure threshold
        "unusual_volume": 5,  # Volume vs average ratio
        "congressional_trade": True,  # Alert on any congressional trade
        "insider_cluster": 3  # Alert if 3+ insiders trade same stock
    }
    
    # Real-time Monitoring
    MONITOR_INTERVAL = 60  # seconds between scans
    FLOW_UPDATE_INTERVAL = 30  # seconds between flow updates
    SENTIMENT_UPDATE_INTERVAL = 60  # seconds between sentiment updates
    
    @classmethod
    def validate(cls) -> bool:
        """
        Validate configuration.
        
        Returns:
            True if configuration is valid
        """
        if not cls.API_KEY and not cls.USE_TEST_KEY:
            logger.warning(
                "No Unusual Whales API key configured. "
                "Set UNUSUAL_WHALES_API_KEY or enable test mode."
            )
            return False
        
        if cls.USE_TEST_KEY:
            logger.warning("Using Unusual Whales test key - limited rate limits!")
        
        return True
    
    @classmethod
    def get_adapter(cls) -> UnusualWhalesPrimaryAdapter:
        """
        Get configured Unusual Whales adapter.
        
        Returns:
            Primary adapter instance
        """
        return create_primary_adapter(
            api_key=cls.API_KEY,
            use_test_key=cls.USE_TEST_KEY
        )
    
    @classmethod
    def get_config_dict(cls) -> Dict[str, Any]:
        """
        Get configuration as dictionary.
        
        Returns:
            Configuration dictionary
        """
        return {
            "primary_source": cls.PRIMARY_SOURCE,
            "api_configured": bool(cls.API_KEY),
            "use_test_key": cls.USE_TEST_KEY,
            "fallback_sources": cls.FALLBACK_SOURCES,
            "cache_ttl": {
                "quote": cls.QUOTE_CACHE_TTL,
                "chain": cls.CHAIN_CACHE_TTL,
                "flow": cls.FLOW_CACHE_TTL,
                "sentiment": cls.SENTIMENT_CACHE_TTL
            },
            "thresholds": {
                "min_flow_premium": cls.MIN_FLOW_PREMIUM,
                "min_unusual_premium": cls.MIN_UNUSUAL_PREMIUM,
                "min_block_size": cls.MIN_BLOCK_SIZE
            },
            "alerts": cls.ALERT_THRESHOLDS,
            "monitoring": {
                "interval": cls.MONITOR_INTERVAL,
                "flow_update": cls.FLOW_UPDATE_INTERVAL,
                "sentiment_update": cls.SENTIMENT_UPDATE_INTERVAL
            },
            "default_symbols": cls.DEFAULT_SCAN_SYMBOLS
        }


def setup_unusual_whales_primary() -> Dict[str, Any]:
    """
    Set up Unusual Whales as the primary data source for Super Gnosis.
    
    This function:
    1. Validates configuration
    2. Creates primary adapter
    3. Replaces all data adapters
    4. Returns adapter dictionary
    
    Returns:
        Dictionary with all adapter types using Unusual Whales
    """
    logger.info("🐋 Setting up Unusual Whales as PRIMARY data source")
    
    # Validate configuration
    if not UnusualWhalesConfig.validate():
        logger.error("Invalid Unusual Whales configuration")
        raise ValueError("Unusual Whales configuration invalid")
    
    # Create primary adapter
    adapter = UnusualWhalesConfig.get_adapter()
    
    # Test connection
    if not adapter.uw.test_connection():
        logger.error("Failed to connect to Unusual Whales API")
        raise RuntimeError("Unusual Whales connection failed")
    
    logger.success("✅ Unusual Whales configured as PRIMARY data source")
    
    # Return adapter for all types
    return {
        "market": adapter,
        "options": adapter,
        "news": adapter,
        "flow": adapter,
        "sentiment": adapter,
        "insider": adapter,
        "primary": adapter  # Direct reference
    }


def get_unusual_whales_status() -> Dict[str, Any]:
    """
    Get status of Unusual Whales integration.
    
    Returns:
        Status dictionary
    """
    try:
        adapter = UnusualWhalesConfig.get_adapter()
        connected = adapter.uw.test_connection()
        
        # Get market sentiment
        sentiment = adapter.get_market_sentiment() if connected else {}
        
        return {
            "configured": bool(UnusualWhalesConfig.API_KEY),
            "connected": connected,
            "using_test_key": UnusualWhalesConfig.USE_TEST_KEY,
            "primary_source": True,
            "market_tide": sentiment.get("tide", "unknown"),
            "market_sentiment": sentiment.get("overall", "unknown"),
            "put_call_ratio": sentiment.get("put_call_ratio", 0),
            "config": UnusualWhalesConfig.get_config_dict()
        }
        
    except Exception as e:
        logger.error(f"Error getting Unusual Whales status: {e}")
        return {
            "configured": False,
            "connected": False,
            "error": str(e)
        }


# ============================================================================
# MONITORING FUNCTIONS
# ============================================================================

def monitor_unusual_activity(
    symbols: Optional[list] = None,
    min_premium: float = 500000
) -> Dict[str, Any]:
    """
    Monitor unusual options activity using Unusual Whales.
    
    Args:
        symbols: List of symbols to monitor (None = all)
        min_premium: Minimum premium threshold
    
    Returns:
        Monitoring results
    """
    adapter = UnusualWhalesConfig.get_adapter()
    
    results = {
        "timestamp": datetime.now().isoformat(),
        "unusual_activities": [],
        "market_sentiment": {},
        "top_flow": [],
        "alerts": []
    }
    
    # Get unusual activities
    unusual = adapter.scan_unusual_activity(
        min_premium=min_premium,
        limit=50
    )
    results["unusual_activities"] = unusual
    
    # Get market sentiment
    sentiment = adapter.get_market_sentiment()
    results["market_sentiment"] = sentiment
    
    # Check for alerts
    if sentiment.get("bullish_flow_pct", 0) > UnusualWhalesConfig.ALERT_THRESHOLDS["extreme_bullish"]:
        results["alerts"].append({
            "type": "extreme_bullish",
            "message": f"Market extremely bullish: {sentiment['bullish_flow_pct']:.1%}",
            "severity": "high"
        })
    
    if sentiment.get("bearish_flow_pct", 0) > UnusualWhalesConfig.ALERT_THRESHOLDS["extreme_bearish"]:
        results["alerts"].append({
            "type": "extreme_bearish",
            "message": f"Market extremely bearish: {sentiment['bearish_flow_pct']:.1%}",
            "severity": "high"
        })
    
    # Monitor specific symbols if provided
    if symbols:
        for symbol in symbols:
            flow = adapter.get_options_flow(ticker=symbol, limit=10)
            flow_records = flow.get("data", [])
            
            # Check for significant activity
            for record in flow_records:
                if record.get("premium", 0) >= min_premium:
                    results["top_flow"].append({
                        "symbol": symbol,
                        "premium": record.get("premium"),
                        "sentiment": record.get("sentiment"),
                        "type": record.get("trade_type"),
                        "timestamp": record.get("timestamp")
                    })
    
    logger.info(
        f"Monitoring complete: {len(results['unusual_activities'])} unusual, "
        f"{len(results['alerts'])} alerts"
    )
    
    return results


# ============================================================================
# INTEGRATION WITH WEBAPP
# ============================================================================

def integrate_with_webapp() -> Dict[str, Any]:
    """
    Integrate Unusual Whales with the Super Gnosis webapp.
    
    Returns:
        Integration status
    """
    try:
        # Setup primary adapter
        adapters = setup_unusual_whales_primary()
        
        # Get initial market state
        market_state = adapters["primary"].get_market_sentiment()
        
        # Get flow for default symbol
        default_symbol = os.getenv("TRADING_SYMBOL", "SPY")
        flow = adapters["primary"].get_options_flow(
            ticker=default_symbol,
            limit=20
        )
        
        return {
            "status": "integrated",
            "primary_source": "unusual_whales",
            "market_tide": market_state.get("tide"),
            "market_sentiment": market_state.get("overall"),
            "default_symbol_flow": len(flow.get("data", [])),
            "adapters_configured": list(adapters.keys())
        }
        
    except Exception as e:
        logger.error(f"Failed to integrate with webapp: {e}")
        return {
            "status": "failed",
            "error": str(e)
        }


if __name__ == "__main__":
    from datetime import datetime
    
    print("="*60)
    print("🐋 UNUSUAL WHALES PRIMARY CONFIGURATION")
    print("="*60)
    
    # Check configuration
    print("\n1. Configuration Status:")
    status = get_unusual_whales_status()
    for key, value in status.items():
        if key != "config":
            print(f"   {key}: {value}")
    
    # Setup primary adapter
    print("\n2. Setting up primary adapter...")
    try:
        adapters = setup_unusual_whales_primary()
        print("   ✅ Primary adapter configured")
        print(f"   Adapter types: {list(adapters.keys())}")
    except Exception as e:
        print(f"   ❌ Setup failed: {e}")
        exit(1)
    
    # Test monitoring
    print("\n3. Testing monitoring...")
    monitor_result = monitor_unusual_activity(
        symbols=["SPY", "QQQ"],
        min_premium=100000
    )
    print(f"   Unusual activities: {len(monitor_result['unusual_activities'])}")
    print(f"   Alerts: {len(monitor_result['alerts'])}")
    print(f"   Market sentiment: {monitor_result['market_sentiment'].get('overall')}")
    
    # Test webapp integration
    print("\n4. Testing webapp integration...")
    integration = integrate_with_webapp()
    print(f"   Status: {integration.get('status')}")
    print(f"   Market tide: {integration.get('market_tide')}")
    
    print("\n" + "="*60)
    print("✅ Unusual Whales is now the PRIMARY data source!")
    print("="*60)