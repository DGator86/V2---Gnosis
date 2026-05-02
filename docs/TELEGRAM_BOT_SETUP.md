# Telegram Bot Setup Guide

## Overview

The **Super Gnosis V2 Telegram Bot** provides real-time monitoring and control of your autonomous trading system from your phone.

## Features

### 📊 Monitoring
- **Real-time portfolio** - Current value, P&L, positions
- **System status** - Trading active/inactive, configuration
- **Position tracking** - Detailed position information with P&L
- **Performance metrics** - Returns, win rate, analytics

### 🔍 Analytics
- **Top opportunities** - Current ranked opportunities from scanner
- **Force scan** - Trigger universe re-scan on demand
- **Health checks** - System diagnostics and connectivity

### ⚙️ Control
- **Settings** - Change top N, scan interval, trade interval
- **Start/Stop** - Enable/disable autonomous trading (coming soon)

### 📱 User Experience
- **Inline buttons** - Quick access to all features
- **Real-time updates** - Instant notifications (coming soon)
- **Clean interface** - Markdown formatting, emojis

---

## Setup Instructions

### Step 1: Create Telegram Bot

1. **Open Telegram** and search for `@BotFather`

2. **Create new bot:**
   ```
   /newbot
   ```

3. **Choose a name:**
   ```
   Super Gnosis Trading Bot
   ```

4. **Choose a username** (must end in 'bot'):
   ```
   SuperGnosisV2_bot
   ```

5. **Copy your token:**
   ```
   Use this token to access the HTTP API:
   1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
   ```
   
   ⚠️ **Keep this token secret!**

### Step 2: Install Dependencies

```bash
cd /home/user/webapp

# Install Telegram bot library
pip install -r telegram_bot/requirements.txt
```

This installs:
- `python-telegram-bot` v20.7 (latest stable)
- Callback data support

### Step 3: Set Environment Variable

```bash
# Set your bot token
export TELEGRAM_BOT_TOKEN='1234567890:ABCdefGHIjklMNOpqrsTUVwxyz'

# Verify it's set
echo $TELEGRAM_BOT_TOKEN
```

**Permanent Setup** (add to `~/.bashrc`):
```bash
echo 'export TELEGRAM_BOT_TOKEN="your-token-here"' >> ~/.bashrc
source ~/.bashrc
```

### Step 4: Run the Bot

```bash
cd /home/user/webapp
python telegram_bot/bot.py
```

Expected output:
```
2025-11-18 18:00:00 - __main__ - INFO - Starting Telegram bot...
2025-11-18 18:00:01 - telegram.ext.Application - INFO - Application started
```

### Step 5: Start Chatting

1. **Open Telegram** and search for your bot username
2. **Click "Start"** or send `/start`
3. **See the main menu** with inline buttons
4. **Try commands** like `/status`, `/portfolio`, `/opportunities`

---

## Available Commands

### Monitoring Commands

| Command | Description | Example Output |
|---------|-------------|----------------|
| `/start` | Show main menu | Interactive buttons |
| `/status` | System status | Trading active, portfolio value, config |
| `/portfolio` | Portfolio overview | Value, cash, positions, P&L |
| `/positions` | Detailed positions | Each position with entry, current, P&L |
| `/performance` | Performance metrics | Total return, win rate, Sharpe ratio |
| `/health` | System health check | Broker, data, config status |

### Control Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/scan` | Force universe scan | Scans 67 symbols, ranks opportunities |
| `/opportunities` | Show top opportunities | Top 25 with scores |
| `/settings` | Change configuration | Top N, scan interval, trade interval |
| `/help` | Show help message | All commands explained |

### Information Commands

| Command | Description |
|---------|-------------|
| `/help` | Show all commands |
| `/start` | Return to main menu |

---

## Example Usage

### Check System Status

```
You: /status

Bot:
🟢 System Status

Trading: 🟢 Active
Mode: Paper Trading
Broker: Alpaca

Configuration:
• Top N Symbols: 25
• Scan Interval: 300s (5 min)
• Trade Interval: 60s

Account:
• Portfolio Value: $30,245.67
• Buying Power: $90,736.01
• Cash: $15,123.45

⏰ Last update: 2025-11-18 18:05:23 UTC
```

### View Portfolio

```
You: /portfolio

Bot:
💰 Portfolio Overview

Total Value: $30,245.67
Cash: $15,123.45
Equity: $30,245.67

P&L: +$245.67 (+0.82%)

Positions: 3

📊 Open Positions:

🟢 TSLA: 10 @ $245.30
  Value: $2,478.00
  P&L: +$25.00 (+1.02%)

🟢 SPY: 5 @ $658.24
  Value: $3,301.50
  P&L: +$10.50 (+0.32%)

🔴 NVDA: 8 @ $875.40
  Value: $6,984.00
  P&L: -$23.20 (-0.33%)

⏰ 18:05:30 UTC
```

### Check Top Opportunities

```
You: /opportunities

Bot:
🔍 Top Opportunities

1. TSLA - range_bound (0.337)
   Range-bound, premium selling

2. MARA - range_bound (0.332)
   Range-bound, strong sentiment

3. MRK - range_bound (0.330)
   Excellent liquidity

... (22 more)

Use /scan to force new scan
⏰ 18:05:45 UTC
```

### Force Universe Scan

```
You: /scan

Bot:
🔍 Force Scan

Starting universe scan...
This may take 60-90 seconds.

Bot (2 seconds later):
✅ Scan Complete

Scanned 67 symbols in 1.2s
Found 25 opportunities

Use /opportunities to view results
```

### View Performance

```
You: /performance

Bot:
📈 Performance Metrics

Returns:
• Total: +$245.67 (+0.82%)
• Starting Capital: $30,000.00
• Current Equity: $30,245.67

Account:
• Day Trade Count: 0
• Pattern Day Trader: No

More detailed analytics coming soon...
⏰ 18:06:12 UTC
```

### Check System Health

```
You: /health

Bot:
❤️ System Health Check

🟢 All systems operational

✅ Broker Connection
  Alpaca connected

✅ Data Adapters
  Yahoo Finance ready

✅ Configuration
  Config loaded

⏰ 18:06:30 UTC
```

---

## Inline Buttons

The bot includes interactive inline buttons for quick access:

**Main Menu:**
```
┌──────────────────────────────┐
│  📊 Status    💰 Portfolio   │
│  🔍 Opportunities 📈 Performance │
│  🎯 Positions   ⚙️ Settings  │
│  ❤️ Health     ❓ Help       │
└──────────────────────────────┘
```

Just tap any button for instant access!

---

## Running as Service

### Option 1: Background Process

```bash
# Start in background
nohup python telegram_bot/bot.py > logs/telegram_bot.log 2>&1 &

# Check if running
ps aux | grep telegram_bot

# View logs
tail -f logs/telegram_bot.log

# Stop
pkill -f telegram_bot
```

### Option 2: Systemd Service

Create `/etc/systemd/system/gnosis-telegram-bot.service`:

```ini
[Unit]
Description=Super Gnosis V2 Telegram Bot
After=network.target

[Service]
Type=simple
User=user
WorkingDirectory=/home/user/webapp
Environment="TELEGRAM_BOT_TOKEN=your-token-here"
Environment="ALPACA_API_KEY=your-alpaca-key"
Environment="ALPACA_SECRET_KEY=your-alpaca-secret"
ExecStart=/usr/bin/python3 telegram_bot/bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable gnosis-telegram-bot
sudo systemctl start gnosis-telegram-bot
sudo systemctl status gnosis-telegram-bot
```

### Option 3: PM2 (Node.js Process Manager)

```bash
# Install PM2
npm install -g pm2

# Start bot
pm2 start telegram_bot/bot.py --name gnosis-telegram-bot --interpreter python3

# Auto-start on reboot
pm2 startup
pm2 save

# Monitor
pm2 status
pm2 logs gnosis-telegram-bot

# Stop
pm2 stop gnosis-telegram-bot
```

---

## Security Best Practices

### 1. Keep Token Secret

⚠️ **Never commit your bot token to Git!**

```bash
# Add to .gitignore
echo "telegram_bot/config.json" >> .gitignore
echo ".env" >> .gitignore
```

### 2. Restrict Access

By default, anyone can message your bot. To restrict:

1. **Get your Telegram user ID:**
   - Message `@userinfobot` on Telegram
   - Copy your numeric ID

2. **Add whitelist to bot.py:**
   ```python
   ALLOWED_USERS = [123456789]  # Your user ID
   
   async def start_command(self, update, context):
       user_id = update.effective_user.id
       if user_id not in ALLOWED_USERS:
           await update.message.reply_text("Unauthorized")
           return
       # ... rest of code
   ```

### 3. Use Environment Variables

Don't hardcode sensitive data:

```bash
# .env file
TELEGRAM_BOT_TOKEN=your-token
ALPACA_API_KEY=your-key
ALPACA_SECRET_KEY=your-secret
```

Load in code:
```python
from dotenv import load_dotenv
load_dotenv()
```

---

## Troubleshooting

### Issue: Bot Not Responding

**Check if bot is running:**
```bash
ps aux | grep telegram_bot
```

**Check logs:**
```bash
tail -f logs/telegram_bot.log
```

**Restart bot:**
```bash
pkill -f telegram_bot
python telegram_bot/bot.py
```

### Issue: "TELEGRAM_BOT_TOKEN not set"

**Solution:**
```bash
# Set token
export TELEGRAM_BOT_TOKEN='your-token-here'

# Verify
echo $TELEGRAM_BOT_TOKEN

# Make permanent
echo 'export TELEGRAM_BOT_TOKEN="your-token"' >> ~/.bashrc
source ~/.bashrc
```

### Issue: "Error fetching portfolio"

**Cause:** Alpaca credentials not set

**Solution:**
```bash
# Set Alpaca credentials
export ALPACA_API_KEY='your-key'
export ALPACA_SECRET_KEY='your-secret'

# For paper trading
export ALPACA_PAPER=true
```

### Issue: Inline Buttons Not Working

**Cause:** Old python-telegram-bot version

**Solution:**
```bash
pip install --upgrade python-telegram-bot==20.7
```

### Issue: Bot Shows Old Data

**Cause:** Caching or stale connection

**Solution:**
```bash
# Restart bot
pkill -f telegram_bot
python telegram_bot/bot.py
```

---

## Advanced Features (Coming Soon)

### 🚧 Planned Features:

1. **Trade Notifications**
   - Real-time alerts when trades execute
   - Entry/exit notifications with P&L

2. **Performance Charts**
   - Equity curve graphs
   - Win rate visualizations
   - Sharpe ratio trends

3. **Risk Alerts**
   - Max drawdown warnings
   - Position size limit alerts
   - Daily loss limit notifications

4. **Start/Stop Control**
   - Enable/disable trading remotely
   - Emergency stop button
   - Pause/resume functionality

5. **Custom Watchlists**
   - Add/remove symbols
   - Custom universe scanning
   - Symbol-specific alerts

6. **Trade Execution**
   - Manual trade entry
   - Close positions remotely
   - Adjust stops/targets

---

## Integration with Trading System

The bot integrates with your existing system:

```python
# In telegram_bot/bot.py

# Portfolio data from Alpaca
from execution.broker_adapters.alpaca_adapter import AlpacaBrokerAdapter
broker = AlpacaBrokerAdapter(paper=True)
account = broker.get_account()

# Opportunities from scanner
from engines.scanner import OpportunityScanner, DEFAULT_UNIVERSE
scanner = OpportunityScanner(...)
result = scanner.scan(DEFAULT_UNIVERSE, top_n=25)

# Configuration
from config.loader import load_config
config = load_config()

# Performance tracking
from tracking.ledger_store import LedgerStore
ledger = LedgerStore(ledger_path)
```

---

## Support

### Documentation:
- This guide: `docs/TELEGRAM_BOT_SETUP.md`
- Bot code: `telegram_bot/bot.py`
- Main trading system: `SESSION_4B_FINAL_SUMMARY.md`

### Telegram Bot API:
- Official docs: https://core.telegram.org/bots/api
- Python library: https://python-telegram-bot.org/

### Debugging:
```bash
# Check bot process
ps aux | grep telegram_bot

# View logs
tail -f logs/telegram_bot.log

# Test connection
python -c "from telegram import Bot; bot = Bot('your-token'); print(bot.get_me())"
```

---

## Quick Reference

### Essential Commands
```bash
# Set token
export TELEGRAM_BOT_TOKEN='your-token'

# Install dependencies
pip install -r telegram_bot/requirements.txt

# Run bot
python telegram_bot/bot.py

# Run in background
nohup python telegram_bot/bot.py > logs/telegram_bot.log 2>&1 &

# Stop bot
pkill -f telegram_bot
```

### Telegram Commands
```
/start          - Main menu
/status         - System status
/portfolio      - Portfolio overview
/positions      - Position details
/opportunities  - Top opportunities
/scan           - Force scan
/performance    - Metrics
/health         - Health check
/settings       - Configure
/help           - Help message
```

---

**Your Telegram bot is ready to monitor your autonomous trading system!** 🤖📱

Get your bot token from @BotFather, set the environment variable, and start the bot to begin monitoring your trades from anywhere!
