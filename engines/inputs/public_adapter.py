"""
Public.com API Adapter for Real-Time Market Data

Provides high-quality, real-time market data using Public.com API.
Requires authentication via access token.
"""

from __future__ import annotations

import requests
import polars as pl
import pandas as pd
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, List
import logging
import os

logger = logging.getLogger(__name__)


class PublicAPIClient:
    """Client for Public.com API with authentication."""
    
    BASE_URL = "https://api.public.com"
    
    def __init__(self):
        self.access_token = None
        self.token_expiry = None
        self._authenticate()
    
    def _authenticate(self):
        """Get access token from Public.com API."""
        # Try to get credentials from environment variables
        secret = os.environ.get('PUBLIC_API_SECRET')
        
        if not secret:
            # No credentials - this will cause the adapter to fail
            # and fallback to Yahoo Finance in main.py
            logger.debug("PUBLIC_API_SECRET not set in environment")
            raise ValueError("PUBLIC_API_SECRET environment variable required")
        
        try:
            url = f"{self.BASE_URL}/userapiauthservice/personal/access-tokens"
            headers = {"Content-Type": "application/json"}
            request_body = {
                "validityInMinutes": 60,  # 1 hour tokens
                "secret": secret
            }
            
            response = requests.post(url, headers=headers, json=request_body)
            response.raise_for_status()
            
            data = response.json()
            self.access_token = data.get('accessToken')
            self.token_expiry = datetime.now(timezone.utc) + timedelta(minutes=60)
            
            logger.info("✓ Authenticated with Public.com API")
            
        except Exception as e:
            logger.warning(f"Failed to authenticate with Public.com: {e}")
            self.access_token = None
    
    def _ensure_authenticated(self):
        """Ensure we have a valid access token."""
        if not self.access_token:
            self._authenticate()
            return
        
        # Refresh token if expired or close to expiry (5 min buffer)
        if self.token_expiry and datetime.now(timezone.utc) >= self.token_expiry - timedelta(minutes=5):
            logger.info("Refreshing Public.com access token...")
            self._authenticate()
    
    def get_quotes(self, symbols: List[str]) -> Dict[str, Dict]:
        """
        Get real-time quotes for multiple symbols.
        
        Args:
            symbols: List of ticker symbols
        
        Returns:
            Dict mapping symbol to quote data
        """
        self._ensure_authenticated()
        
        if not self.access_token:
            logger.warning("No access token available")
            return {}
        
        try:
            url = f"{self.BASE_URL}/userapigateway/marketdata/default/quotes"
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            params = {
                "symbols": ",".join(symbols)
            }
            
            response = requests.get(url, headers=headers, params=params)
            
            if response.status_code == 401:
                logger.warning("Public.com API auth failed, re-authenticating...")
                self._authenticate()
                # Retry once
                response = requests.get(url, headers=headers, params=params)
            
            response.raise_for_status()
            
            data = response.json()
            return data.get('quotes', {})
            
        except Exception as e:
            logger.warning(f"Public.com API request failed: {e}")
            return {}


class PublicMarketAdapter:
    """Market data adapter using Public.com API."""
    
    def __init__(self):
        self.client = PublicAPIClient()
        self.cache = {}
        self.cache_duration = 60  # Cache for 60 seconds
    
    def get_quote(self, symbol: str) -> Dict:
        """Get current quote for a symbol."""
        try:
            quotes = self.client.get_quotes([symbol])
            
            if not quotes or symbol not in quotes:
                logger.debug(f"No quote data returned for {symbol}")
                return {}
            
            quote_data = quotes[symbol]
            
            # Convert to standard format
            quote = {
                'symbol': symbol,
                'last': float(quote_data.get('last', 0)),
                'close': float(quote_data.get('last', 0)),
                'open': float(quote_data.get('open', 0)),
                'high': float(quote_data.get('high', 0)),
                'low': float(quote_data.get('low', 0)),
                'volume': int(quote_data.get('volume', 0)),
                'bid': float(quote_data.get('bid', 0)),
                'ask': float(quote_data.get('ask', 0)),
                'timestamp': datetime.now(timezone.utc),
            }
            
            return quote
            
        except Exception as e:
            logger.warning(f"Failed to get quote for {symbol}: {e}")
            return {}
    
    def get_historical(
        self,
        symbol: str,
        days: int = 30,
        interval: str = "1d"
    ) -> pl.DataFrame:
        """
        Get historical OHLCV data.
        Fallback to Yahoo Finance for historical data.
        """
        try:
            import yfinance as yf
            
            ticker = yf.Ticker(symbol)
            
            # Map days to period
            if days <= 7:
                period = f"{days}d"
            elif days <= 60:
                period = "60d"
            else:
                period = "max"
            
            hist = ticker.history(period=period, interval=interval)
            
            if hist.empty:
                return pl.DataFrame()
            
            # Convert to Polars
            df = pl.DataFrame({
                'timestamp': hist.index,
                'open': hist['Open'].values,
                'high': hist['High'].values,
                'low': hist['Low'].values,
                'close': hist['Close'].values,
                'volume': hist['Volume'].values,
            })
            
            return df
            
        except Exception as e:
            logger.warning(f"Failed to get historical data for {symbol}: {e}")
            return pl.DataFrame()
    
    def get_intraday(self, symbol: str, minutes: int = 60) -> pl.DataFrame:
        """Get recent intraday data."""
        return self.get_historical(symbol, days=1, interval="1m")
    
    def fetch_ohlcv(self, symbol: str, now: datetime, lookback_days: int = 30) -> pl.DataFrame:
        """Fetch OHLCV data (interface method for engines)."""
        if not isinstance(lookback_days, int):
            lookback_days = 30
        return self.get_historical(symbol, days=lookback_days, interval="1d")


class PublicOptionsAdapter:
    """
    Options adapter - Public.com doesn't provide options data.
    Fallback to Yahoo Finance for options chains.
    """
    
    def __init__(self):
        pass
    
    def fetch_chain(self, symbol: str, now: datetime) -> pl.DataFrame:
        """Fetch options chain (fallback to Yahoo Finance)."""
        return self.get_chain(symbol, days_to_expiry=30)
    
    def get_chain(
        self,
        symbol: str,
        days_to_expiry: Optional[int] = None
    ) -> pl.DataFrame:
        """Get options chain using Yahoo Finance."""
        try:
            import yfinance as yf
            
            ticker = yf.Ticker(symbol)
            expirations = ticker.options
            
            if not expirations:
                return pl.DataFrame()
            
            # Find closest expiration
            target_date = datetime.now() + timedelta(days=days_to_expiry or 30)
            closest_exp = min(
                expirations,
                key=lambda x: abs((datetime.strptime(x, '%Y-%m-%d') - target_date).days)
            )
            
            # Get options chain
            opt_chain = ticker.option_chain(closest_exp)
            
            calls = opt_chain.calls.copy()
            calls['option_type'] = 'call'
            
            puts = opt_chain.puts.copy()
            puts['option_type'] = 'put'
            
            # Combine with type conversion for NaN values
            all_options = pl.DataFrame({
                'strike': list(calls['strike']) + list(puts['strike']),
                'option_type': list(calls['option_type']) + list(puts['option_type']),
                'expiry': [closest_exp] * (len(calls) + len(puts)),
                'bid': list(calls['bid']) + list(puts['bid']),
                'ask': list(calls['ask']) + list(puts['ask']),
                'last': list(calls['lastPrice']) + list(puts['lastPrice']),
                'volume': [int(v) if not pd.isna(v) else 0 for v in list(calls['volume']) + list(puts['volume'])],
                'open_interest': [int(oi) if not pd.isna(oi) else 0 for oi in list(calls['openInterest']) + list(puts['openInterest'])],
                'implied_volatility': list(calls['impliedVolatility'].fillna(0)) + list(puts['impliedVolatility'].fillna(0)),
            })
            
            return all_options
            
        except Exception as e:
            logger.warning(f"Failed to get options chain for {symbol}: {e}")
            return pl.DataFrame()
    
    def get_current_price(self, symbol: str) -> float:
        """Get current underlying price."""
        try:
            import yfinance as yf
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="1d")
            
            if hist.empty:
                return 0.0
            
            return float(hist['Close'].iloc[-1])
            
        except Exception as e:
            logger.warning(f"Failed to get price for {symbol}: {e}")
            return 0.0


class PublicNewsAdapter:
    """
    News adapter - Public.com doesn't provide news.
    Fallback to Yahoo Finance for news.
    """
    
    def __init__(self):
        pass
    
    def fetch_news(self, symbol: str, now: datetime, lookback_hours: int = 24) -> List[Dict]:
        """Fetch news (fallback to Yahoo Finance)."""
        if not isinstance(lookback_hours, int):
            lookback_hours = 24
        return self.get_recent_news(symbol, hours=lookback_hours)
    
    def get_recent_news(
        self,
        symbol: str,
        hours: int = 24
    ) -> List[Dict]:
        """Get recent news using Yahoo Finance."""
        try:
            import yfinance as yf
            
            ticker = yf.Ticker(symbol)
            news = ticker.news
            
            if not news:
                return []
            
            cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
            
            formatted_news = []
            for item in news[:10]:
                try:
                    pub_time = datetime.fromtimestamp(
                        item.get('providerPublishTime', 0),
                        tz=timezone.utc
                    )
                    
                    if pub_time > cutoff:
                        formatted_news.append({
                            'title': item.get('title', ''),
                            'published_at': pub_time,
                            'source': item.get('publisher', 'Unknown'),
                            'url': item.get('link', ''),
                        })
                except:
                    continue
            
            return formatted_news
            
        except Exception as e:
            logger.warning(f"Failed to get news for {symbol}: {e}")
            return []


def create_public_adapters():
    """Create all three Public.com adapters."""
    return (
        PublicMarketAdapter(),
        PublicOptionsAdapter(),
        PublicNewsAdapter(),
    )
