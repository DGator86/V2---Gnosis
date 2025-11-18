# Public.com API Setup Guide

## Overview

The system now supports **Public.com API** for real-time market data with automatic fallback to Yahoo Finance.

## Why Public.com?

- ✅ **Real-time quotes** - Better quality than Yahoo Finance
- ✅ **Professional-grade data** - Used by trading platforms
- ✅ **Reliable** - Consistent data feed
- ✅ **Graceful fallback** - Automatically uses Yahoo Finance if unavailable

## Authentication

Public.com API uses **access tokens** generated from your secret.

### 1. Get Your Secret

You need a Public.com API secret. Contact Public.com support or check your account settings.

### 2. Set Environment Variable

```bash
# Set the secret in your environment
export PUBLIC_API_SECRET='your-secret-here'

# Verify it's set
echo $PUBLIC_API_SECRET
```

### 3. Run Multi-Symbol Trading

```bash
# The system will automatically use Public.com
cd /home/user/webapp
python main.py multi-symbol-loop --top 25 --scan-interval 300 --trade-interval 60
```

You should see:
```
✓ Using Public.com for real-time market data
```

## How It Works

### With PUBLIC_API_SECRET Set:

1. **System tries Public.com first**
   - Generates access token (valid for 60 minutes)
   - Auto-refreshes tokens before expiry
   - Uses Bearer token authentication

2. **Data Sources:**
   - **Quotes**: Public.com real-time API ✓
   - **Historical OHLCV**: Yahoo Finance (fallback)
   - **Options Chains**: Yahoo Finance (fallback)
   - **News**: Yahoo Finance (fallback)

### Without PUBLIC_API_SECRET:

1. **System automatically falls back to Yahoo Finance**
   - No authentication needed
   - Free tier data
   - Slightly delayed quotes

2. **You'll see:**
   ```
   ✓ Using Yahoo Finance for real market data (Public.com unavailable)
   ```

## API Details

### Token Generation

```python
import requests

url = "https://api.public.com/userapiauthservice/personal/access-tokens"
headers = {"Content-Type": "application/json"}
request_body = {
  "validityInMinutes": 60,
  "secret": "your-secret-here"
}

response = requests.post(url, headers=headers, json=request_body)
data = response.json()

# Use the access token
access_token = data['accessToken']
```

### Quote Request

```python
url = "https://api.public.com/userapigateway/marketdata/default/quotes"
headers = {
    "Authorization": f"Bearer {access_token}",
    "Content-Type": "application/json"
}
params = {"symbols": "SPY,QQQ,AAPL"}

response = requests.get(url, headers=headers, params=params)
quotes = response.json()['quotes']
```

## Architecture

```
Multi-Symbol Scanner
    ↓
Try: Public.com Adapter
    ├─ ✓ PUBLIC_API_SECRET set → Use Public.com
    └─ ✗ No secret → ValueError
            ↓
        Catch Exception
            ↓
    Fallback: Yahoo Finance Adapter
            ↓
        Continue Trading
```

## Permanent Setup

To make PUBLIC_API_SECRET permanent across sessions:

### Option 1: Shell Profile

```bash
# Add to ~/.bashrc or ~/.zshrc
echo 'export PUBLIC_API_SECRET="your-secret-here"' >> ~/.bashrc
source ~/.bashrc
```

### Option 2: Systemd Service

```bash
# Create /etc/systemd/system/gnosis-trading.service
[Service]
Environment="PUBLIC_API_SECRET=your-secret-here"
ExecStart=/usr/bin/python3 /home/user/webapp/main.py multi-symbol-loop
```

### Option 3: Docker

```yaml
# docker-compose.yml
services:
  gnosis:
    environment:
      - PUBLIC_API_SECRET=your-secret-here
```

## Testing

### 1. Test with Public.com

```bash
export PUBLIC_API_SECRET='your-secret-here'
python main.py scan-opportunities --universe "SPY,QQQ,AAPL" --top 3
```

Should show:
```
✓ Using Public.com for real-time market data
```

### 2. Test Fallback (no secret)

```bash
unset PUBLIC_API_SECRET
python main.py scan-opportunities --universe "SPY,QQQ,AAPL" --top 3
```

Should show:
```
✓ Using Yahoo Finance for real market data (Public.com unavailable)
```

## Monitoring

The adapter logs authentication status:

```
✓ Authenticated with Public.com API
Refreshing Public.com access token...
```

Watch for warnings:
```
PUBLIC_API_SECRET not set in environment
Public.com API request failed: 401 Client Error
```

## Troubleshooting

### Issue: "401 Client Error"

**Cause**: Invalid secret or expired token

**Solution**:
1. Verify PUBLIC_API_SECRET is correct
2. Check token hasn't expired (auto-refreshes every 55 min)
3. Restart the trading loop

### Issue: "Using Yahoo Finance" instead of Public.com

**Cause**: PUBLIC_API_SECRET not in environment

**Solution**:
```bash
# Check if set
echo $PUBLIC_API_SECRET

# If empty, set it
export PUBLIC_API_SECRET='your-secret-here'

# Restart trading
python main.py multi-symbol-loop --top 25
```

### Issue: "Rate limited"

**Cause**: Too many API requests

**Solution**:
- Increase `--scan-interval` (default: 300 seconds)
- Reduce `--top` number of symbols (default: 25)
- The adapter caches quotes for 60 seconds

## Rate Limits

**Public.com API:**
- Unknown specific limits (contact Public.com)
- Adapter caches quotes for 60 seconds
- Tokens valid for 60 minutes

**Scanner defaults:**
- Scans 67 symbols every 5 minutes
- ~13 symbols/minute
- Well within reasonable API limits

## Next Steps

1. **Get your Public.com API secret**
2. **Set PUBLIC_API_SECRET environment variable**
3. **Restart the trading loop**
4. **Verify "Using Public.com" message appears**

The system is **production-ready** with or without Public.com credentials!
