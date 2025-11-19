#!/usr/bin/env python3
"""
webapp_uw.py — Super Gnosis with Unusual Whales Primary Data Source

Enhanced web dashboard that uses UNUSUAL WHALES as the PRIMARY data source for:
- Real-time options flow
- Market sentiment and tide
- Congressional and insider trades
- Unusual activity alerts
- Gamma exposure monitoring

All market data now comes from Unusual Whales API.
"""

import threading
import asyncio
import uvicorn
from datetime import datetime
import sys
from pathlib import Path
import os
from typing import Optional, Dict, Any, List
import json

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Global startup time for uptime calculation
startup_time = datetime.utcnow()

# Import dashboard app
from gnosis.dashboard.dashboard_server import app as dashboard_app, dashboard_state

# Import Unusual Whales configuration
from config.unusual_whales_config import (
    UnusualWhalesConfig,
    setup_unusual_whales_primary,
    monitor_unusual_activity,
    get_unusual_whales_status
)

# Global adapter reference
uw_adapter = None

# ------------------------------------------------------------------
# Unusual Whales Monitoring Thread
# ------------------------------------------------------------------
async def monitor_unusual_whales():
    """
    Background thread that monitors Unusual Whales data and updates dashboard.
    """
    global uw_adapter
    
    logger.info("🐋 Starting Unusual Whales monitoring thread")
    
    while True:
        try:
            if uw_adapter:
                # Get current symbol
                symbol = os.getenv("TRADING_SYMBOL", "SPY")
                
                # Update market sentiment
                sentiment = uw_adapter.get_market_sentiment()
                dashboard_state.regime_state = {
                    "primary": sentiment.get("tide", "unknown"),
                    "confidence": abs(sentiment.get("tide_score", 0)),
                    "trend_strength": sentiment.get("net_premium", 0) / 1000000,  # In millions
                    "volatility": sentiment.get("put_call_ratio", 1.0),
                    "overall_sentiment": sentiment.get("overall", "neutral"),
                    "bullish_flow_pct": sentiment.get("bullish_flow_pct", 0),
                    "bearish_flow_pct": sentiment.get("bearish_flow_pct", 0)
                }
                
                # Update options flow for symbol
                flow_data = uw_adapter.get_options_flow(ticker=symbol, limit=20)
                flow_records = flow_data.get("data", [])
                
                # Convert flow to agent votes (simulated from flow sentiment)
                agent_votes = {
                    "agents": [],
                    "timestamp": datetime.now().isoformat()
                }
                
                # Analyze flow for different "agents"
                bullish_count = sum(1 for f in flow_records if f.get("sentiment") == "bullish")
                bearish_count = sum(1 for f in flow_records if f.get("sentiment") == "bearish")
                total_count = len(flow_records)
                
                # Flow Agent (based on options flow)
                flow_signal = 1 if bullish_count > bearish_count else -1 if bearish_count > bullish_count else 0
                agent_votes["agents"].append({
                    "name": "Flow Agent (UW)",
                    "signal": flow_signal,
                    "confidence": max(bullish_count, bearish_count) / max(total_count, 1),
                    "reasoning": f"Options flow: {bullish_count} bullish, {bearish_count} bearish"
                })
                
                # Gamma Agent (based on gamma exposure)
                try:
                    gamma_data = uw_adapter.get_gamma_exposure(symbol)
                    gamma_signal = -1 if gamma_data.get("gamma_flip", False) else 1
                    agent_votes["agents"].append({
                        "name": "Gamma Agent (UW)",
                        "signal": gamma_signal,
                        "confidence": min(abs(gamma_data.get("net_gamma", 0)) / 1000000, 1.0),
                        "reasoning": f"Net gamma: {gamma_data.get('net_gamma', 0):.0f}, Flip: {gamma_data.get('gamma_flip', False)}"
                    })
                except:
                    pass
                
                # Insider Agent (based on congressional/insider trades)
                insider_signals = uw_adapter.get_insider_signals(symbol=symbol, days_back=7)
                if insider_signals:
                    bullish_insiders = sum(1 for s in insider_signals if s.get("signal") == "bullish")
                    bearish_insiders = sum(1 for s in insider_signals if s.get("signal") == "bearish")
                    insider_signal = 1 if bullish_insiders > bearish_insiders else -1 if bearish_insiders > bullish_insiders else 0
                    agent_votes["agents"].append({
                        "name": "Insider Agent (UW)",
                        "signal": insider_signal,
                        "confidence": 0.8 if insider_signals else 0.1,
                        "reasoning": f"Recent trades: {bullish_insiders} bullish, {bearish_insiders} bearish"
                    })
                
                dashboard_state.agent_votes = agent_votes
                
                # Check for unusual activity alerts
                unusual = uw_adapter.scan_unusual_activity(min_premium=500000, limit=10)
                
                # Add unusual activities as "trades" in dashboard
                for activity in unusual[:5]:  # Show top 5
                    trade_record = {
                        "symbol": activity.get("ticker", "Unknown"),
                        "side": 1 if activity.get("sentiment") == "bullish" else -1,
                        "entry_price": activity.get("strike", 0),
                        "entry_time": datetime.now().isoformat(),
                        "exit_price": 0,
                        "exit_time": None,
                        "exit_reason": activity.get("description", "Unusual Activity"),
                        "realized_pnl": 0,
                        "bars_held": 0,
                        "premium": activity.get("premium", 0)
                    }
                    
                    # Only add if not already in trades
                    if not any(t.get("symbol") == trade_record["symbol"] and 
                              t.get("entry_time") == trade_record["entry_time"] 
                              for t in dashboard_state.trades):
                        dashboard_state.trades.appendleft(trade_record)
                
                # Update portfolio stats with flow data
                dashboard_state.portfolio_stats.update({
                    "flow_sentiment": sentiment.get("overall", "neutral"),
                    "put_call_ratio": sentiment.get("put_call_ratio", 1.0),
                    "call_premium": sentiment.get("call_premium", 0),
                    "put_premium": sentiment.get("put_premium", 0),
                    "unusual_activities": len(unusual)
                })
                
            # Sleep before next update
            await asyncio.sleep(30)  # Update every 30 seconds
            
        except Exception as e:
            logger.error(f"Error in Unusual Whales monitor: {e}")
            await asyncio.sleep(60)  # Wait longer on error


# ------------------------------------------------------------------
# Enhanced Health Endpoint with Unusual Whales Status
# ------------------------------------------------------------------
@dashboard_app.get("/health")
async def health():
    """
    Enhanced health check with Unusual Whales integration status.
    """
    uptime_seconds = int((datetime.utcnow() - startup_time).total_seconds())
    
    # Get Unusual Whales status
    uw_status = get_unusual_whales_status()
    
    health_status = {
        "status": "HEALTHY 🐋" if uw_status.get("connected") else "DEGRADED ⚠️",
        "version": "Super Gnosis v3.0 - Unusual Whales Edition",
        "timestamp_utc": datetime.utcnow().isoformat() + "Z",
        "uptime_seconds": uptime_seconds,
        "uptime_human": f"{uptime_seconds // 3600}h {(uptime_seconds % 3600) // 60}m {uptime_seconds % 60}s",
        
        # Data Source Status
        "data_source": {
            "primary": "unusual_whales",
            "connected": uw_status.get("connected", False),
            "using_test_key": uw_status.get("using_test_key", False),
            "market_tide": uw_status.get("market_tide", "unknown"),
            "market_sentiment": uw_status.get("market_sentiment", "unknown"),
            "put_call_ratio": uw_status.get("put_call_ratio", 0)
        },
        
        # Dashboard State
        "dashboard": {
            "active_positions": len(dashboard_state.positions),
            "recent_trades": len(dashboard_state.trades),
            "agent_votes": len(dashboard_state.agent_votes.get("agents", [])) if dashboard_state.agent_votes else 0,
            "unusual_activities": dashboard_state.portfolio_stats.get("unusual_activities", 0)
        },
        
        # Environment
        "environment": {
            "trading_symbol": os.getenv("TRADING_SYMBOL", "SPY"),
            "unusual_whales_configured": bool(os.getenv("UNUSUAL_WHALES_API_KEY")),
            "monitor_interval": UnusualWhalesConfig.MONITOR_INTERVAL
        }
    }
    
    return health_status


# ------------------------------------------------------------------
# Unusual Whales API Endpoints
# ------------------------------------------------------------------

@dashboard_app.get("/api/unusual-whales/flow")
async def get_unusual_flow(
    symbol: Optional[str] = None,
    limit: int = 50,
    min_premium: float = 100000
):
    """Get options flow from Unusual Whales."""
    if not uw_adapter:
        return {"error": "Unusual Whales not configured"}
    
    flow = uw_adapter.get_options_flow(
        ticker=symbol,
        limit=limit,
        min_premium=min_premium
    )
    return flow


@dashboard_app.get("/api/unusual-whales/sentiment")
async def get_market_sentiment():
    """Get market sentiment from Unusual Whales."""
    if not uw_adapter:
        return {"error": "Unusual Whales not configured"}
    
    return uw_adapter.get_market_sentiment()


@dashboard_app.get("/api/unusual-whales/unusual")
async def get_unusual_activity(
    min_premium: float = 500000,
    limit: int = 20
):
    """Get unusual activity alerts."""
    if not uw_adapter:
        return {"error": "Unusual Whales not configured"}
    
    return uw_adapter.scan_unusual_activity(
        min_premium=min_premium,
        limit=limit
    )


@dashboard_app.get("/api/unusual-whales/gamma/{symbol}")
async def get_gamma_exposure(symbol: str):
    """Get gamma exposure for a symbol."""
    if not uw_adapter:
        return {"error": "Unusual Whales not configured"}
    
    return uw_adapter.get_gamma_exposure(symbol)


@dashboard_app.get("/api/unusual-whales/insiders")
async def get_insider_trades(
    symbol: Optional[str] = None,
    days_back: int = 30
):
    """Get insider and congressional trades."""
    if not uw_adapter:
        return {"error": "Unusual Whales not configured"}
    
    return uw_adapter.get_insider_signals(
        symbol=symbol,
        days_back=days_back
    )


# ------------------------------------------------------------------
# Enhanced Dashboard Page
# ------------------------------------------------------------------
@dashboard_app.get("/")
async def root():
    """Serve enhanced dashboard with Unusual Whales branding."""
    from gnosis.dashboard.dashboard_server import get_dashboard_html
    
    # Get original HTML
    original_html = get_dashboard_html()
    
    # Add Unusual Whales enhanced header
    enhanced_header = """
    <div style="background: linear-gradient(135deg, #1a237e 0%, #3949ab 50%, #5c6bc0 100%); 
                padding: 25px; 
                border-radius: 12px; 
                margin-bottom: 20px; 
                box-shadow: 0 4px 6px rgba(0,0,0,0.3);">
        <h1 style="font-size: 32px; margin-bottom: 10px; display: flex; align-items: center;">
            🐋 Super Gnosis v3.0 — Powered by Unusual Whales
        </h1>
        <div style="display: flex; gap: 30px; font-size: 14px; opacity: 0.95;">
            <span>🌊 Live Options Flow</span>
            <span>🎯 Market Sentiment & Tide</span>
            <span>👔 Congressional Trades</span>
            <span>⚡ Unusual Activity Alerts</span>
            <span>🎲 Gamma Exposure</span>
            <span style="background: rgba(255,255,255,0.2); padding: 4px 8px; border-radius: 4px;">
                ❤️ Health: <a href="/health" style="color: #4ade80; text-decoration: none;">/health</a> 🐋
            </span>
        </div>
        <div style="margin-top: 10px; font-size: 12px; opacity: 0.8;">
            Data Source: <strong>UNUSUAL WHALES PRIMARY</strong> | 
            Flow Updates: Every 30s | 
            <a href="/api/unusual-whales/flow" style="color: #81c784;">API</a>
        </div>
    </div>
    
    <script>
        // Add auto-refresh for Unusual Whales data
        setInterval(async () => {
            try {
                // Fetch latest sentiment
                const sentiment = await fetch('/api/unusual-whales/sentiment').then(r => r.json());
                console.log('Market sentiment:', sentiment);
                
                // Fetch unusual activity
                const unusual = await fetch('/api/unusual-whales/unusual?limit=5').then(r => r.json());
                console.log('Unusual activities:', unusual.length);
                
            } catch (error) {
                console.error('Error fetching Unusual Whales data:', error);
            }
        }, 30000); // Every 30 seconds
    </script>
    """
    
    # Insert enhanced header
    enhanced_html = original_html.replace(
        '<body>',
        '<body>\n' + enhanced_header
    )
    
    # Update title
    enhanced_html = enhanced_html.replace(
        '<title>Gnosis Trading Dashboard</title>',
        '<title>Super Gnosis v3.0 - Unusual Whales Edition</title>'
    )
    
    from fastapi.responses import HTMLResponse
    return HTMLResponse(content=enhanced_html)


# ------------------------------------------------------------------
# Start everything with Unusual Whales
# ------------------------------------------------------------------
def main():
    """Main entry point with Unusual Whales integration."""
    global uw_adapter
    
    print("=" * 60)
    print("🐋 Super Gnosis Web App - UNUSUAL WHALES EDITION")
    print("=" * 60)
    
    # Setup Unusual Whales as primary data source
    print("\n🐋 Configuring Unusual Whales as PRIMARY data source...")
    try:
        adapters = setup_unusual_whales_primary()
        uw_adapter = adapters["primary"]
        print("✅ Unusual Whales configured successfully!")
        
        # Get initial market state
        sentiment = uw_adapter.get_market_sentiment()
        print(f"\n📊 Market Status:")
        print(f"   Tide: {sentiment.get('tide', 'Unknown')}")
        print(f"   Sentiment: {sentiment.get('overall', 'Unknown')}")
        print(f"   Put/Call Ratio: {sentiment.get('put_call_ratio', 0):.2f}")
        print(f"   Bullish Flow: {sentiment.get('bullish_flow_pct', 0):.1%}")
        print(f"   Bearish Flow: {sentiment.get('bearish_flow_pct', 0):.1%}")
        
    except Exception as e:
        print(f"⚠️  Unusual Whales setup failed: {e}")
        print("   Running in degraded mode without primary data source")
        print("   Set UNUSUAL_WHALES_API_KEY in .env file")
    
    print("\n📊 Configuration:")
    print(f"   Primary Data Source: UNUSUAL WHALES")
    print(f"   Symbol: {os.getenv('TRADING_SYMBOL', 'SPY')}")
    print(f"   API Key Configured: {'✅' if os.getenv('UNUSUAL_WHALES_API_KEY') else '❌'}")
    print(f"   Using Test Key: {'Yes' if UnusualWhalesConfig.USE_TEST_KEY else 'No'}")
    
    print("\n🌐 Web Endpoints:")
    print("   Live Dashboard     → http://localhost:8000")
    print("   Health Check       → http://localhost:8000/health")
    print("   Options Flow API   → http://localhost:8000/api/unusual-whales/flow")
    print("   Market Sentiment   → http://localhost:8000/api/unusual-whales/sentiment")
    print("   Unusual Activity   → http://localhost:8000/api/unusual-whales/unusual")
    print("   Gamma Exposure     → http://localhost:8000/api/unusual-whales/gamma/{symbol}")
    print("   Insider Trades     → http://localhost:8000/api/unusual-whales/insiders")
    
    print("\n⚡ Controls:")
    print("   Stop with Ctrl+C")
    print("=" * 60)
    print()
    
    # Start Unusual Whales monitoring thread
    if uw_adapter:
        import logging
        logging.basicConfig(level=logging.INFO)
        logger = logging.getLogger(__name__)
        
        monitor_thread = threading.Thread(
            target=lambda: asyncio.run(monitor_unusual_whales()),
            daemon=True,
            name="UnusualWhalesMonitor"
        )
        monitor_thread.start()
        print("🐋 Unusual Whales monitoring thread started\n")
    
    # Start the web server
    try:
        uvicorn.run(
            dashboard_app,
            host="0.0.0.0",
            port=8000,
            log_level="info",
            access_log=False,
            server_header=False,
            date_header=False
        )
    except KeyboardInterrupt:
        print("\n\n👋 Shutting down gracefully...")
        print("=" * 60)


if __name__ == "__main__":
    import logging
    logger = logging.getLogger(__name__)
    main()