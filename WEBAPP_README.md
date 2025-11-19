# 🚀 Super Gnosis Web Dashboard

## Production-Grade Real-Time Trading Brain Monitor

Your Gnosis framework now has a **professional-grade web dashboard** that shows exactly what your AI trading system is thinking in real-time!

## ✨ Features

### Live Dashboard (http://localhost:8000)
- **🧠 Real-time Agent Thoughts**: See what each agent is voting (LONG/SHORT/NEUTRAL) with confidence scores
- **📊 Live Positions & PnL**: Track open positions, unrealized P&L, and portfolio performance
- **🔄 Regime Detection**: Current market regime (Trending/Range/Volatile) with confidence
- **📜 Trade History**: Last 20 trades with entry/exit prices and reasons
- **💰 Portfolio Stats**: Capital, equity, daily P&L, win rate
- **🔴 WebSocket Live Feed**: Real-time updates without page refresh

### Health Monitoring (http://localhost:8000/health)
Perfect for monitoring tools like Grafana, UptimeRobot, or custom dashboards:
```json
{
    "status": "HEALTHY 🟢",
    "version": "Super Gnosis v3.0",
    "timestamp_utc": "2025-11-19T02:45:00Z",
    "uptime_seconds": 3600,
    "active_positions": 2,
    "total_pnl_pct": 2.5,
    "current_regime": "trending_up",
    "regime_confidence": 0.82,
    "memory_episodes_stored": 150
}
```

## 🚀 Quick Start (One Command!)

```bash
# Run the web app with integrated trading bot
python webapp.py
```

That's it! Open http://localhost:8000 to see your trading brain in action.

## 📦 Installation

### 1. Clone & Setup
```bash
git clone https://github.com/DGator86/V2---Gnosis.git
cd V2---Gnosis
pip install -r requirements.txt
```

### 2. Configure API Keys
```bash
cp .env.example .env
# Edit .env and add your Alpaca API keys (get free paper trading keys)
```

### 3. Run the Dashboard
```bash
python webapp.py
```

## 🎮 Usage Modes

### Dashboard-Only Mode (No Trading)
Perfect for monitoring without placing trades:
```bash
# In .env, set:
ENABLE_TRADING=false
python webapp.py
```

### Paper Trading Mode (Default)
Trade with fake money to test strategies:
```bash
# In .env, set:
PAPER_TRADING=true
ENABLE_TRADING=true
python webapp.py
```

### Live Trading Mode (Real Money)
⚠️ **USE WITH CAUTION** - This trades real money!
```bash
# In .env, set:
PAPER_TRADING=false
ENABLE_TRADING=true
python webapp.py
```

## 🌐 Cloud Deployment (Free!)

Deploy to the internet in 2 minutes:

### Option 1: Railway.app
1. Push your code to GitHub
2. Go to [railway.app](https://railway.app)
3. New Project → Deploy from GitHub Repo
4. Select your repo
5. Add environment variables from .env
6. Deploy! You'll get `https://your-gnosis.up.railway.app`

### Option 2: Render.com
1. Push to GitHub
2. Go to [render.com](https://render.com)
3. New → Web Service
4. Connect GitHub repo
5. Build Command: `pip install -r requirements.txt`
6. Start Command: `python webapp.py`
7. Add environment variables
8. Deploy! Get `https://gnosis-dashboard.onrender.com`

### Option 3: Docker (Self-Hosted)
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
EXPOSE 8000
CMD ["python", "webapp.py"]
```

```bash
docker build -t gnosis-webapp .
docker run -p 8000:8000 --env-file .env gnosis-webapp
```

## ⚙️ Configuration

Edit `.env` file to configure:

```bash
# Trading Settings
TRADING_SYMBOL=SPY          # Symbol to trade
BAR_INTERVAL=1Min           # Bar interval
PAPER_TRADING=true          # Paper vs Live mode
ENABLE_TRADING=false        # Enable order placement
ENABLE_MEMORY=true          # Use memory system

# Risk Management
MAX_POSITION_SIZE_PCT=2.0   # Max 2% per position
MAX_DAILY_LOSS_USD=5000     # Daily loss limit
DEFAULT_CAPITAL=30000       # Starting capital
```

## 🛠️ Advanced Features

### Custom Health Checks
```python
# Add to webapp.py for custom monitoring
@dashboard_app.get("/metrics")
async def metrics():
    return {
        "custom_metric": calculate_custom_metric(),
        "alert_threshold": check_alert_conditions()
    }
```

### Webhook Notifications
```python
# Send alerts to Discord/Slack
async def send_alert(message):
    webhook_url = os.getenv("DISCORD_WEBHOOK")
    requests.post(webhook_url, json={"content": message})
```

### Database Persistence
```python
# Add PostgreSQL for trade history
DATABASE_URL = os.getenv("DATABASE_URL")
# Use SQLAlchemy for ORM
```

## 📊 Dashboard Components

The dashboard (`gnosis/dashboard/dashboard_server.py`) includes:
- **FastAPI Backend**: REST API + WebSocket server
- **Real-time Updates**: WebSocket streaming for live data
- **HTML/JS Frontend**: Clean, responsive UI
- **State Management**: In-memory state shared with trading bot

## 🔧 Troubleshooting

### "Port 8000 already in use"
```bash
# Find and kill the process
lsof -i :8000
kill <PID>
```

### "No Alpaca API keys"
Get free paper trading API keys from:
https://app.alpaca.markets/paper/dashboard/overview

### "Module not found" errors
```bash
pip install -r requirements.txt
```

### Dashboard shows no data
- Check if trading bot is running (needs Alpaca API keys)
- Verify WebSocket connection (check browser console)
- Market might be closed (runs 24/7 but only trades during market hours)

## 🚨 Production Checklist

- [ ] Configure proper API keys in `.env`
- [ ] Set appropriate risk limits
- [ ] Test thoroughly in paper mode first
- [ ] Set up monitoring (use `/health` endpoint)
- [ ] Configure alerts for critical events
- [ ] Implement proper logging
- [ ] Set up automated backups
- [ ] Use process manager (PM2/systemd) for reliability
- [ ] Configure SSL/HTTPS for public deployment
- [ ] Rate limit public endpoints

## 💡 Pro Tips

1. **Monitor Health Endpoint**: Set up UptimeRobot to ping `/health` every 5 minutes
2. **Use Paper Mode First**: Always test strategies with paper trading
3. **Watch the Agents**: If agents disagree, the system won't trade (2-of-3 consensus required)
4. **Memory System**: The bot learns from past trades - keep it running for better performance
5. **Regime Matters**: The system adapts strategy based on detected market regime

## 📝 Summary

You now have a **hedge-fund-grade monitoring platform** for your Gnosis trading system. The combination of:
- Real-time agent visualization
- Live position tracking
- Health monitoring
- WebSocket streaming
- One-command deployment

...makes this a professional-grade solution that rivals commercial trading platforms.

**Just run `python webapp.py` and watch your AI think!** 🧠✨

---

## Need Help?

- Check existing documentation in `/docs`
- Review code in `/gnosis/dashboard/`
- Look at examples in `/examples`
- Check logs in `/logs` directory

Happy Trading! 🚀📈