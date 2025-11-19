#!/usr/bin/env python3
"""
webapp.py — Super Gnosis Real-time Web Dashboard + Health Monitoring

Production-grade, always-on web app that shows:
- Real-time agent thoughts
- Live positions and PnL
- Current regime detection
- Trade history
- Health monitoring endpoint

Run with: python webapp.py
Then access: http://localhost:8000
Health check: http://localhost:8000/health
"""

import threading
import asyncio
import uvicorn
from datetime import datetime
import sys
from pathlib import Path
import os
from typing import Optional, Dict, Any

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Global startup time for uptime calculation
startup_time = datetime.utcnow()

# Import dashboard app
from gnosis.dashboard.dashboard_server import app as dashboard_app

# Import bot components - with graceful fallback
try:
    from gnosis.trading.live_bot import LiveTradingBot
    BOT_AVAILABLE = True
except ImportError as e:
    BOT_AVAILABLE = False
    print(f"⚠️  Trading bot not available: {e}")
    print("   The web dashboard will run in monitoring-only mode.")

# Global references for health monitoring
bot_instance: Optional[Any] = None
position_manager_ref: Optional[Any] = None
detector_ref: Optional[Any] = None
memory_store_ref: Optional[Any] = None

# ------------------------------------------------------------------
# Background thread: runs the trading bot forever
# ------------------------------------------------------------------
def run_bot():
    """Run the trading bot in background thread"""
    global bot_instance, position_manager_ref, detector_ref, memory_store_ref
    
    if not BOT_AVAILABLE:
        print("⚠️  Trading bot not available - running in dashboard-only mode")
        return
    
    try:
        # Create bot instance
        bot_instance = LiveTradingBot(
            symbol=os.getenv("TRADING_SYMBOL", "SPY"),
            bar_interval=os.getenv("BAR_INTERVAL", "1Min"),
            enable_memory=os.getenv("ENABLE_MEMORY", "true").lower() == "true",
            enable_trading=os.getenv("ENABLE_TRADING", "false").lower() == "true",  # Default to paper mode
            paper_mode=os.getenv("PAPER_TRADING", "true").lower() == "true"  # Default to paper trading
        )
        
        # Store references for health monitoring
        if hasattr(bot_instance, 'position_mgr'):
            position_manager_ref = bot_instance.position_mgr
        if hasattr(bot_instance, 'regime_detector'):
            detector_ref = bot_instance.regime_detector
        
        # Hook up dashboard updates (similar to start_with_dashboard.py)
        setup_dashboard_hooks(bot_instance)
        
        print("🤖 Trading bot started successfully")
        print(f"   Symbol: {bot_instance.symbol}")
        print(f"   Paper Mode: {bot_instance.paper_mode}")
        print(f"   Trading Enabled: {bot_instance.enable_trading}")
        
        # Run the bot
        asyncio.run(bot_instance.run())
        
    except Exception as e:
        print(f"❌ Bot error: {e}")
        import traceback
        traceback.print_exc()

def setup_dashboard_hooks(bot):
    """Set up hooks to update dashboard from bot events"""
    from gnosis.dashboard.dashboard_server import (
        update_positions, add_trade, update_agent_votes,
        update_regime, update_bar, update_portfolio_stats
    )
    
    # Monkey-patch bot to send updates to dashboard
    original_process_bar = bot.process_bar
    
    async def process_bar_with_dashboard(bar):
        """Wrapped process_bar that updates dashboard"""
        # Update dashboard with new bar
        update_bar(bar)
        
        # Call original processing
        await original_process_bar(bar)
        
        # After processing, update dashboard with latest state
        if hasattr(bot, 'position_mgr') and bot.position_mgr:
            positions_dict = {
                pos.symbol: {
                    "symbol": pos.symbol,
                    "side": pos.side,
                    "size": pos.size,
                    "entry_price": pos.entry_price,
                    "unrealized_pnl": getattr(pos, 'unrealized_pnl', 0),
                    "bars_held": getattr(pos, 'bars_held', 0)
                }
                for pos in bot.position_mgr.positions.values()
            }
            update_positions(positions_dict)
            
            # Update portfolio stats
            summary = bot.position_mgr.get_portfolio_summary()
            update_portfolio_stats({
                "capital": 30000.0,
                "equity": 30000.0 * (1 + summary.get("total_pnl", 0)),
                "pnl": summary.get("total_pnl", 0),
                "daily_pnl": summary.get("daily_pnl", 0),
                "total_trades": summary.get("total_trades", 0),
                "win_rate": summary.get("win_rate", 0.0)
            })
        
        # Update regime if available
        if hasattr(bot, 'regime_detector') and bot.regime_detector:
            if hasattr(bot.regime_detector, 'current_state'):
                update_regime({
                    "primary": getattr(bot.regime_detector.current_state, 'primary', 'unknown'),
                    "confidence": getattr(bot.regime_detector.current_state, 'confidence', 0),
                    "trend_strength": getattr(bot.regime_detector.current_state, 'trend_strength', 0),
                    "volatility": getattr(bot.regime_detector.current_state, 'volatility', 0)
                })
    
    bot.process_bar = process_bar_with_dashboard
    
    # Monkey-patch evaluate_agents to send votes
    if hasattr(bot, 'evaluate_agents'):
        original_evaluate = bot.evaluate_agents
        
        def evaluate_agents_with_dashboard(features, price):
            """Wrapped evaluate_agents that updates dashboard"""
            agent_views = original_evaluate(features, price)
            
            # Send to dashboard
            update_agent_votes({
                "agents": [
                    {
                        "name": av.agent_name,
                        "signal": av.signal,
                        "confidence": av.confidence,
                        "reasoning": av.reasoning
                    }
                    for av in agent_views
                ],
                "timestamp": str(bot.bars[-1]["t_event"]) if bot.bars else None
            })
            
            return agent_views
        
        bot.evaluate_agents = evaluate_agents_with_dashboard

# ------------------------------------------------------------------
# Health endpoint — perfect for monitoring tools (UptimeRobot, Grafana, etc.)
# ------------------------------------------------------------------
@dashboard_app.get("/health")
async def health():
    """
    Health check endpoint for monitoring
    
    Returns:
        - System status
        - Uptime
        - Active positions
        - Current PnL
        - Regime state
        - Memory episodes
    """
    
    # Calculate uptime
    uptime_seconds = int((datetime.utcnow() - startup_time).total_seconds())
    
    # Build health response
    health_status = {
        "status": "HEALTHY 🟢",
        "version": "Super Gnosis v3.0",
        "timestamp_utc": datetime.utcnow().isoformat() + "Z",
        "uptime_seconds": uptime_seconds,
        "uptime_human": f"{uptime_seconds // 3600}h {(uptime_seconds % 3600) // 60}m {uptime_seconds % 60}s",
        "bot_running": bot_instance is not None and BOT_AVAILABLE,
    }
    
    # Add position manager stats if available
    if position_manager_ref:
        try:
            health_status["active_positions"] = len(position_manager_ref.positions)
            
            # Get portfolio summary if method exists
            if hasattr(position_manager_ref, 'get_portfolio_summary'):
                summary = position_manager_ref.get_portfolio_summary()
                health_status["total_pnl_pct"] = round(summary.get("total_pnl", 0) * 100, 2)
                health_status["daily_pnl_pct"] = round(summary.get("daily_pnl", 0) * 100, 2)
                health_status["total_trades"] = summary.get("total_trades", 0)
                health_status["win_rate_pct"] = round(summary.get("win_rate", 0) * 100, 1)
            
            # Get last trade time if available
            if hasattr(position_manager_ref, 'trades') and position_manager_ref.trades:
                last_trade = position_manager_ref.trades[-1]
                if 'exit_time' in last_trade:
                    health_status["last_trade_timestamp"] = last_trade['exit_time'].isoformat() + "Z"
        except Exception as e:
            health_status["position_manager_error"] = str(e)
    else:
        health_status["active_positions"] = 0
        health_status["total_pnl_pct"] = 0.0
    
    # Add regime detector stats if available
    if detector_ref:
        try:
            if hasattr(detector_ref, 'current_state') and detector_ref.current_state:
                health_status["current_regime"] = detector_ref.current_state.primary
                health_status["regime_confidence"] = round(detector_ref.current_state.confidence, 3)
            else:
                health_status["current_regime"] = "unknown"
        except Exception as e:
            health_status["regime_error"] = str(e)
    else:
        health_status["current_regime"] = "unknown"
    
    # Add memory store stats if available
    if memory_store_ref:
        try:
            if hasattr(memory_store_ref, 'episodes'):
                health_status["memory_episodes_stored"] = len(memory_store_ref.episodes)
        except Exception as e:
            health_status["memory_error"] = str(e)
    else:
        health_status["memory_episodes_stored"] = 0
    
    # Add environment info
    health_status["environment"] = {
        "trading_symbol": os.getenv("TRADING_SYMBOL", "SPY"),
        "paper_trading": os.getenv("PAPER_TRADING", "true").lower() == "true",
        "trading_enabled": os.getenv("ENABLE_TRADING", "false").lower() == "true",
        "memory_enabled": os.getenv("ENABLE_MEMORY", "true").lower() == "true",
        "alpaca_configured": bool(os.getenv("ALPACA_API_KEY")),
    }
    
    return health_status

# ------------------------------------------------------------------
# Enhanced dashboard page with health status
# ------------------------------------------------------------------
@dashboard_app.get("/")
async def root():
    """Serve enhanced dashboard HTML with header"""
    from gnosis.dashboard.dashboard_server import get_dashboard_html
    
    # Get original HTML
    original_html = get_dashboard_html()
    
    # Add our enhanced header
    enhanced_header = """
    <div style="background: linear-gradient(135deg, #1e3c72 0%, #2a5298 50%, #667eea 100%); 
                padding: 25px; 
                border-radius: 12px; 
                margin-bottom: 20px; 
                box-shadow: 0 4px 6px rgba(0,0,0,0.3);">
        <h1 style="font-size: 32px; margin-bottom: 10px; display: flex; align-items: center;">
            🧠 Super Gnosis v3.0 — Live Brain Monitor
        </h1>
        <div style="display: flex; gap: 30px; font-size: 14px; opacity: 0.95;">
            <span>📊 Real-time agent thoughts</span>
            <span>💰 Positions &amp; PnL</span>
            <span>🔄 Regime detection</span>
            <span>🧬 Memory system</span>
            <span style="background: rgba(255,255,255,0.2); padding: 4px 8px; border-radius: 4px;">
                ❤️ Health: <a href="/health" style="color: #4ade80; text-decoration: none;">/health</a> 🟢
            </span>
        </div>
    </div>
    """
    
    # Insert our header after the <body> tag
    enhanced_html = original_html.replace(
        '<body>',
        '<body>\n' + enhanced_header
    )
    
    # Also update the title
    enhanced_html = enhanced_html.replace(
        '<title>Gnosis Trading Dashboard</title>',
        '<title>Super Gnosis v3.0 - Live Trading Brain</title>'
    )
    
    from fastapi.responses import HTMLResponse
    return HTMLResponse(content=enhanced_html)

# ------------------------------------------------------------------
# Start everything
# ------------------------------------------------------------------
def main():
    """Main entry point"""
    print("=" * 60)
    print("🚀 Super Gnosis Web App booting up...")
    print("=" * 60)
    print("\n📊 Configuration:")
    print(f"   Symbol: {os.getenv('TRADING_SYMBOL', 'SPY')}")
    print(f"   Paper Trading: {os.getenv('PAPER_TRADING', 'true')}")
    print(f"   Trading Enabled: {os.getenv('ENABLE_TRADING', 'false')}")
    print(f"   Memory System: {os.getenv('ENABLE_MEMORY', 'true')}")
    print(f"   Alpaca Configured: {'✅' if os.getenv('ALPACA_API_KEY') else '❌ (set ALPACA_API_KEY)'}")
    print("\n🌐 Web Endpoints:")
    print("   Live Dashboard  → http://localhost:8000")
    print("   Health Check    → http://localhost:8000/health")
    print("   WebSocket Feed  → ws://localhost:8000/ws")
    print("\n⚡ Controls:")
    print("   Stop with Ctrl+C")
    print("=" * 60)
    print()
    
    # Start the trading bot in background thread (if available)
    if BOT_AVAILABLE and os.getenv("ALPACA_API_KEY"):
        bot_thread = threading.Thread(target=run_bot, daemon=True, name="TradingBot")
        bot_thread.start()
        print("🤖 Trading bot thread started\n")
    else:
        if not BOT_AVAILABLE:
            print("⚠️  Trading bot not available - running dashboard only")
        if not os.getenv("ALPACA_API_KEY"):
            print("⚠️  No Alpaca API key - set ALPACA_API_KEY and ALPACA_SECRET_KEY in .env")
        print()
    
    # Start the web server (this blocks)
    try:
        uvicorn.run(
            dashboard_app, 
            host="0.0.0.0", 
            port=8000,
            log_level="info",
            access_log=False,  # Reduce console noise
            server_header=False,
            date_header=False
        )
    except KeyboardInterrupt:
        print("\n\n👋 Shutting down gracefully...")
        print("=" * 60)

if __name__ == "__main__":
    main()