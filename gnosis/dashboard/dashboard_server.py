"""
Simple Web Dashboard for Live Trading Bot

FastAPI backend providing:
- Real-time WebSocket updates
- REST API for positions, trades, memory
- Static HTML/JS frontend

Run with: uvicorn gnosis.dashboard.dashboard_server:app --reload --port 8080
"""

from __future__ import annotations
import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
from collections import deque

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# App setup
app = FastAPI(title="Gnosis Trading Dashboard")

# In-memory state (shared with bot)
class DashboardState:
    """Shared state between bot and dashboard"""
    def __init__(self):
        self.positions: Dict[str, Any] = {}
        self.trades: deque = deque(maxlen=50)  # Last 50 trades
        self.agent_votes: Dict[str, Any] = {}
        self.memory_recalls: deque = deque(maxlen=20)
        self.portfolio_stats = {
            "capital": 30000.0,
            "equity": 30000.0,
            "pnl": 0.0,
            "daily_pnl": 0.0,
            "total_trades": 0,
            "win_rate": 0.0
        }
        self.regime_state: Optional[Dict] = None
        self.last_bar: Optional[Dict] = None
        
    def to_dict(self) -> Dict:
        """Serialize state for API"""
        return {
            "positions": self.positions,
            "trades": list(self.trades),
            "agent_votes": self.agent_votes,
            "memory_recalls": list(self.memory_recalls),
            "portfolio_stats": self.portfolio_stats,
            "regime_state": self.regime_state,
            "last_bar": self.last_bar,
            "timestamp": datetime.now().isoformat()
        }

# Global state
dashboard_state = DashboardState()

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
    
    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients"""
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass

manager = ConnectionManager()


# ============================================================================
# REST API Endpoints
# ============================================================================

@app.get("/")
async def root():
    """Serve main dashboard HTML"""
    return HTMLResponse(content=get_dashboard_html())

@app.get("/api/state")
async def get_state():
    """Get current trading state"""
    return dashboard_state.to_dict()

@app.get("/api/positions")
async def get_positions():
    """Get open positions"""
    return {
        "positions": dashboard_state.positions,
        "count": len(dashboard_state.positions)
    }

@app.get("/api/trades")
async def get_trades(limit: int = 20):
    """Get recent trades"""
    trades = list(dashboard_state.trades)[:limit]
    return {
        "trades": trades,
        "count": len(trades)
    }

@app.get("/api/portfolio")
async def get_portfolio():
    """Get portfolio stats"""
    return dashboard_state.portfolio_stats

@app.get("/api/memory")
async def get_memory(limit: int = 10):
    """Get recent memory recalls"""
    recalls = list(dashboard_state.memory_recalls)[:limit]
    return {
        "recalls": recalls,
        "count": len(recalls)
    }

@app.get("/api/regime")
async def get_regime():
    """Get current regime state"""
    return dashboard_state.regime_state or {"primary": "unknown", "confidence": 0.0}


# ============================================================================
# WebSocket Endpoint
# ============================================================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for real-time updates"""
    await manager.connect(websocket)
    
    try:
        # Send initial state
        await websocket.send_json({
            "type": "init",
            "data": dashboard_state.to_dict()
        })
        
        # Keep connection alive and listen for messages
        while True:
            data = await websocket.receive_text()
            # Echo back (for testing)
            await websocket.send_text(f"Echo: {data}")
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# ============================================================================
# Update Functions (called by bot)
# ============================================================================

def update_positions(positions: Dict[str, Any]):
    """Update open positions"""
    dashboard_state.positions = positions
    asyncio.create_task(_broadcast_update("positions", positions))

def add_trade(trade: Dict[str, Any]):
    """Add new trade"""
    dashboard_state.trades.appendleft(trade)
    dashboard_state.portfolio_stats["total_trades"] += 1
    asyncio.create_task(_broadcast_update("trade", trade))

def update_agent_votes(votes: Dict[str, Any]):
    """Update latest agent votes"""
    dashboard_state.agent_votes = votes
    asyncio.create_task(_broadcast_update("agent_votes", votes))

def add_memory_recall(recall: Dict[str, Any]):
    """Add memory recall"""
    dashboard_state.memory_recalls.appendleft(recall)
    asyncio.create_task(_broadcast_update("memory_recall", recall))

def update_portfolio_stats(stats: Dict[str, Any]):
    """Update portfolio statistics"""
    dashboard_state.portfolio_stats.update(stats)
    asyncio.create_task(_broadcast_update("portfolio_stats", stats))

def update_regime(regime: Dict[str, Any]):
    """Update regime state"""
    dashboard_state.regime_state = regime
    asyncio.create_task(_broadcast_update("regime", regime))

def update_bar(bar: Dict[str, Any]):
    """Update latest bar"""
    dashboard_state.last_bar = bar
    asyncio.create_task(_broadcast_update("bar", bar))

async def _broadcast_update(update_type: str, data: Any):
    """Broadcast update to all websocket clients"""
    await manager.broadcast({
        "type": update_type,
        "data": data,
        "timestamp": datetime.now().isoformat()
    })


# ============================================================================
# Frontend HTML
# ============================================================================

def get_dashboard_html() -> str:
    """Generate simple dashboard HTML"""
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Gnosis Trading Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0f0f23;
            color: #e8e8e8;
            padding: 20px;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            border-radius: 12px;
            margin-bottom: 20px;
        }
        .header h1 {
            font-size: 28px;
            margin-bottom: 8px;
        }
        .header .status {
            display: flex;
            gap: 20px;
            font-size: 14px;
            opacity: 0.9;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }
        .card {
            background: #1a1a2e;
            border: 1px solid #2a2a3e;
            border-radius: 12px;
            padding: 20px;
        }
        .card h2 {
            font-size: 18px;
            margin-bottom: 15px;
            color: #a8a8ff;
        }
        .stat {
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid #2a2a3e;
        }
        .stat:last-child { border-bottom: none; }
        .stat-label { opacity: 0.7; }
        .stat-value { font-weight: 600; }
        .positive { color: #4ade80; }
        .negative { color: #f87171; }
        .neutral { color: #fbbf24; }
        table {
            width: 100%;
            border-collapse: collapse;
        }
        th, td {
            padding: 10px;
            text-align: left;
            border-bottom: 1px solid #2a2a3e;
        }
        th {
            color: #a8a8ff;
            font-weight: 600;
            font-size: 14px;
        }
        td { font-size: 13px; }
        .badge {
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
        }
        .badge-long { background: #4ade80; color: #000; }
        .badge-short { background: #f87171; color: #000; }
        .badge-neutral { background: #fbbf24; color: #000; }
        .agent-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
            gap: 12px;
        }
        .agent-card {
            background: #16213e;
            padding: 12px;
            border-radius: 8px;
            border-left: 4px solid #a8a8ff;
        }
        .agent-card.active { border-left-color: #4ade80; }
        .agent-name { font-weight: 600; font-size: 13px; margin-bottom: 6px; }
        .agent-signal { font-size: 12px; opacity: 0.8; }
        .ws-indicator {
            display: inline-block;
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #4ade80;
            margin-right: 6px;
            animation: pulse 2s infinite;
        }
        .ws-indicator.disconnected { background: #f87171; animation: none; }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        .regime-badge {
            display: inline-block;
            padding: 6px 12px;
            border-radius: 6px;
            font-weight: 600;
            font-size: 13px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🤖 Gnosis Trading Dashboard</h1>
        <div class="status">
            <span><span id="ws-indicator" class="ws-indicator"></span>Live</span>
            <span id="timestamp">--:--:--</span>
            <span id="symbol">SPY</span>
        </div>
    </div>

    <div class="grid">
        <div class="card">
            <h2>💼 Portfolio</h2>
            <div class="stat">
                <span class="stat-label">Capital</span>
                <span class="stat-value" id="capital">$30,000</span>
            </div>
            <div class="stat">
                <span class="stat-label">Equity</span>
                <span class="stat-value" id="equity">$30,000</span>
            </div>
            <div class="stat">
                <span class="stat-label">Total PnL</span>
                <span class="stat-value" id="total-pnl">$0.00</span>
            </div>
            <div class="stat">
                <span class="stat-label">Daily PnL</span>
                <span class="stat-value" id="daily-pnl">$0.00</span>
            </div>
            <div class="stat">
                <span class="stat-label">Win Rate</span>
                <span class="stat-value" id="win-rate">0%</span>
            </div>
        </div>

        <div class="card">
            <h2>📊 Regime</h2>
            <div class="stat">
                <span class="stat-label">Current</span>
                <span class="regime-badge" id="regime-primary">unknown</span>
            </div>
            <div class="stat">
                <span class="stat-label">Confidence</span>
                <span class="stat-value" id="regime-conf">0%</span>
            </div>
            <div class="stat">
                <span class="stat-label">Trend Strength</span>
                <span class="stat-value" id="regime-trend">0.00</span>
            </div>
            <div class="stat">
                <span class="stat-label">Volatility</span>
                <span class="stat-value" id="regime-vol">0.00</span>
            </div>
        </div>

        <div class="card">
            <h2>📍 Positions (<span id="position-count">0</span>)</h2>
            <div id="positions-list">
                <p style="opacity: 0.5; text-align: center; padding: 20px;">No open positions</p>
            </div>
        </div>
    </div>

    <div class="card" style="margin-bottom: 20px;">
        <h2>🗳️ Agent Votes</h2>
        <div class="agent-grid" id="agent-votes">
            <p style="opacity: 0.5; grid-column: 1/-1; text-align: center; padding: 20px;">No recent votes</p>
        </div>
    </div>

    <div class="card">
        <h2>📜 Trade History</h2>
        <table id="trades-table">
            <thead>
                <tr>
                    <th>Time</th>
                    <th>Symbol</th>
                    <th>Side</th>
                    <th>Entry</th>
                    <th>Exit</th>
                    <th>PnL</th>
                    <th>Reason</th>
                </tr>
            </thead>
            <tbody>
                <tr><td colspan="7" style="text-align: center; opacity: 0.5;">No trades yet</td></tr>
            </tbody>
        </table>
    </div>

    <script>
        // WebSocket connection
        let ws;
        let wsConnected = false;

        function connectWebSocket() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            ws = new WebSocket(`${protocol}//${window.location.host}/ws`);

            ws.onopen = () => {
                console.log('✅ WebSocket connected');
                wsConnected = true;
                document.getElementById('ws-indicator').classList.remove('disconnected');
            };

            ws.onclose = () => {
                console.log('❌ WebSocket disconnected');
                wsConnected = false;
                document.getElementById('ws-indicator').classList.add('disconnected');
                setTimeout(connectWebSocket, 3000);
            };

            ws.onerror = (error) => {
                console.error('WebSocket error:', error);
            };

            ws.onmessage = (event) => {
                const message = JSON.parse(event.data);
                handleUpdate(message);
            };
        }

        function handleUpdate(message) {
            const { type, data } = message;
            
            if (type === 'init') {
                updateAll(data);
            } else if (type === 'portfolio_stats') {
                updatePortfolio(data);
            } else if (type === 'positions') {
                updatePositions(data);
            } else if (type === 'trade') {
                addTrade(data);
            } else if (type === 'agent_votes') {
                updateAgentVotes(data);
            } else if (type === 'regime') {
                updateRegime(data);
            } else if (type === 'bar') {
                updateBar(data);
            }
        }

        function updateAll(state) {
            updatePortfolio(state.portfolio_stats);
            updatePositions(state.positions);
            updateRegime(state.regime_state);
            if (state.agent_votes) updateAgentVotes(state.agent_votes);
            if (state.trades && state.trades.length > 0) {
                state.trades.forEach(trade => addTrade(trade, false));
            }
        }

        function updatePortfolio(stats) {
            document.getElementById('capital').textContent = `$${stats.capital.toLocaleString()}`;
            document.getElementById('equity').textContent = `$${stats.equity.toLocaleString()}`;
            
            const totalPnl = stats.pnl * stats.capital;
            const el1 = document.getElementById('total-pnl');
            el1.textContent = `$${totalPnl.toFixed(2)}`;
            el1.className = totalPnl >= 0 ? 'stat-value positive' : 'stat-value negative';
            
            const dailyPnl = stats.daily_pnl * stats.capital;
            const el2 = document.getElementById('daily-pnl');
            el2.textContent = `$${dailyPnl.toFixed(2)}`;
            el2.className = dailyPnl >= 0 ? 'stat-value positive' : 'stat-value negative';
            
            document.getElementById('win-rate').textContent = `${(stats.win_rate * 100).toFixed(1)}%`;
        }

        function updatePositions(positions) {
            const count = Object.keys(positions).length;
            document.getElementById('position-count').textContent = count;
            
            const container = document.getElementById('positions-list');
            if (count === 0) {
                container.innerHTML = '<p style="opacity: 0.5; text-align: center; padding: 20px;">No open positions</p>';
                return;
            }
            
            let html = '';
            Object.values(positions).forEach(pos => {
                const pnlClass = pos.unrealized_pnl >= 0 ? 'positive' : 'negative';
                const sideClass = pos.side > 0 ? 'badge-long' : 'badge-short';
                html += `
                    <div class="stat">
                        <div>
                            <span class="badge ${sideClass}">${pos.side > 0 ? 'LONG' : 'SHORT'}</span>
                            ${pos.symbol} @ $${pos.entry_price.toFixed(2)}
                        </div>
                        <span class="${pnlClass}">$${pos.unrealized_pnl.toFixed(2)}</span>
                    </div>
                `;
            });
            container.innerHTML = html;
        }

        function updateRegime(regime) {
            if (!regime) return;
            document.getElementById('regime-primary').textContent = regime.primary || 'unknown';
            document.getElementById('regime-conf').textContent = `${((regime.confidence || 0) * 100).toFixed(0)}%`;
            document.getElementById('regime-trend').textContent = (regime.trend_strength || 0).toFixed(2);
            document.getElementById('regime-vol').textContent = (regime.volatility || 0).toFixed(2);
        }

        function updateAgentVotes(votes) {
            const container = document.getElementById('agent-votes');
            if (!votes.agents || votes.agents.length === 0) return;
            
            let html = '';
            votes.agents.forEach(agent => {
                const active = agent.signal !== 0;
                const signalText = agent.signal > 0 ? '↑ LONG' : agent.signal < 0 ? '↓ SHORT' : '— NEUTRAL';
                html += `
                    <div class="agent-card ${active ? 'active' : ''}">
                        <div class="agent-name">${agent.name}</div>
                        <div class="agent-signal">${signalText}</div>
                        <div class="agent-signal">Conf: ${(agent.confidence * 100).toFixed(0)}%</div>
                    </div>
                `;
            });
            container.innerHTML = html;
        }

        function addTrade(trade, prepend = true) {
            const tbody = document.querySelector('#trades-table tbody');
            if (tbody.rows[0]?.cells[0]?.colSpan === 7) {
                tbody.innerHTML = '';
            }
            
            const row = tbody.insertRow(prepend ? 0 : -1);
            const pnlClass = trade.realized_pnl >= 0 ? 'positive' : 'negative';
            const sideClass = trade.side > 0 ? 'badge-long' : 'badge-short';
            
            row.innerHTML = `
                <td>${new Date(trade.exit_time).toLocaleTimeString()}</td>
                <td>${trade.symbol}</td>
                <td><span class="badge ${sideClass}">${trade.side > 0 ? 'LONG' : 'SHORT'}</span></td>
                <td>$${trade.entry_price.toFixed(2)}</td>
                <td>$${trade.exit_price.toFixed(2)}</td>
                <td class="${pnlClass}">$${trade.realized_pnl.toFixed(2)}</td>
                <td>${trade.exit_reason}</td>
            `;
            
            // Keep only last 20 rows
            while (tbody.rows.length > 20) {
                tbody.deleteRow(-1);
            }
        }

        function updateBar(bar) {
            if (bar.t_event) {
                document.getElementById('timestamp').textContent = 
                    new Date(bar.t_event).toLocaleTimeString();
            }
            if (bar.symbol) {
                document.getElementById('symbol').textContent = bar.symbol;
            }
        }

        // Poll REST API if WebSocket fails
        function pollState() {
            if (!wsConnected) {
                fetch('/api/state')
                    .then(r => r.json())
                    .then(data => updateAll(data))
                    .catch(err => console.error('Poll error:', err));
            }
        }

        // Initialize
        connectWebSocket();
        setInterval(pollState, 5000);
    </script>
</body>
</html>
    """

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
