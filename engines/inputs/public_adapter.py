"""
Public.com Data Adapter for Real Market Data

Provides institutional-grade market data using Public.com's trading API.
This replaces Yahoo Finance with more reliable, real-time data.
"""

from __future__ import annotations

import requests
import polars as pl
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, List
import logging
import os

logger = logging.getLogger(__name__)


class PublicAPIClient:
    """
    Base client for Public.com API requests.
    
    Handles authentication and common request patterns.
    """
    
    BASE_URL = "https://api.public.com/userapigateway"
    
    def __init__(self, api_key: str, account_id: Optional[str] = None):
        """
        Initialize Public.com API client.
        
        Args:
            api_key: Public.com API key (Bearer token)
            account_id: Account ID (optional, some endpoints don't require it)
        """
        self.api_key = api_key
        self.account_id = account_id or "default"
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        })
    
    def _request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[Dict] = None,
        params: Optional[Dict] = None
    ) -> Dict:
        """Make authenticated request to Public.com API."""
        url = f"{self.BASE_URL}/{endpoint}"
        
        try:
            response = self.session.request(
                method=method,
                url=url,
                json=json_data,
                params=params,
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Public.com API request failed: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response: {e.response.text}")
            return {}
    
    def get(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """GET request."""
        return self._request('GET', endpoint, params=params)
    
    def post(self, endpoint: str, json_data: Dict) -> Dict:
        """POST request."""
        return self._request('POST', endpoint, json_data=json_data)


class PublicMarketAdapter:
    """
    Market data adapter using Public.com API.
    
    Provides:
    - Real-time quotes with bid/ask spreads
    - Historical OHLCV data with institutional accuracy
    - Volume and liquidity metrics
    """
    
    def __init__(self, api_key: Optional[str] = None, account_id: Optional[str] = None):
        """Initialize with API credentials from environment or arguments."""
        self.api_key = api_key or os.getenv('PUBLIC_API_KEY', '')
        self.account_id = account_id or os.getenv('PUBLIC_ACCOUNT_ID', 'default')
        
        if not self.api_key:
            raise ValueError("PUBLIC_API_KEY environment variable or api_key argument required")
        
        self.client = PublicAPIClient(self.api_key, self.account_id)
        self.cache = {}
        self.cache_duration = 5  # Cache for 5 seconds (more aggressive for real-time)
    
    def get_quote(self, symbol: str) -> Dict:
        """
        Get current real-time quote for a symbol.
        
        Returns:
            Dict with: symbol, last, bid, ask, open, high, low, volume, timestamp
        """
        # Check cache
        cache_key = f"quote_{symbol}"
        if cache_key in self.cache:
            cached_time, cached_data = self.cache[cache_key]
            if (datetime.now() - cached_time).total_seconds() < self.cache_duration:
                return cached_data
        
        try:
            # Public.com quotes endpoint
            response = self.client.post(
                f"marketdata/{self.account_id}/quotes",
                json_data={
                    "instruments": [
                        {"symbol": symbol, "instrument_type": "EQUITY"}
                    ]
                }
            )
            
            if not response or 'quotes' not in response:
                logger.warning(f"No quote data returned for {symbol}")
                return {}
            
            quotes = response.get('quotes', [])
            if not quotes:
                return {}
            
            quote_data = quotes[0]
            
            # Extract quote information
            quote = {
                'symbol': symbol,
                'last': float(quote_data.get('last', 0) or 0),
                'bid': float(quote_data.get('bid', 0) or 0),
                'ask': float(quote_data.get('ask', 0) or 0),
                'open': float(quote_data.get('open', 0) or 0),
                'high': float(quote_data.get('high', 0) or 0),
                'low': float(quote_data.get('low', 0) or 0),
                'close': float(quote_data.get('close', 0) or quote_data.get('last', 0) or 0),
                'volume': int(quote_data.get('volume', 0) or 0),
                'timestamp': datetime.now(timezone.utc),
            }
            
            # Cache the result
            self.cache[cache_key] = (datetime.now(), quote)
            
            return quote
            
        except Exception as e:
            logger.error(f"Failed to get quote for {symbol}: {e}")
            return {}
    
    def get_historical(
        self,
        symbol: str,
        days: int = 30,
        interval: str = "1d"
    ) -> pl.DataFrame:
        """
        Get historical OHLCV data.
        
        Args:
            symbol: Ticker symbol
            days: Number of days of history
            interval: Data interval (1m, 5m, 15m, 1h, 1d)
        
        Returns:
            Polars DataFrame with OHLCV data
        """
        try:
            # Map interval to Public.com timeframe
            timeframe_map = {
                '1m': '1Min',
                '5m': '5Min',
                '15m': '15Min',
                '1h': '1Hour',
                '1d': '1Day',
            }
            
            timeframe = timeframe_map.get(interval, '1Day')
            
            # Calculate start/end times
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(days=days)
            
            # Public.com historical bars endpoint
            response = self.client.post(
                f"marketdata/{self.account_id}/historical-bars",
                json_data={
                    "symbol": symbol,
                    "instrument_type": "EQUITY",
                    "timeframe": timeframe,
                    "start": start_time.isoformat(),
                    "end": end_time.isoformat(),
                }
            )
            
            if not response or 'bars' not in response:
                logger.warning(f"No historical data returned for {symbol}")
                return pl.DataFrame()
            
            bars = response.get('bars', [])
            if not bars:
                return pl.DataFrame()
            
            # Convert to Polars DataFrame
            df = pl.DataFrame({
                'timestamp': [datetime.fromisoformat(bar['time'].replace('Z', '+00:00')) for bar in bars],
                'open': [float(bar['open']) for bar in bars],
                'high': [float(bar['high']) for bar in bars],
                'low': [float(bar['low']) for bar in bars],
                'close': [float(bar['close']) for bar in bars],
                'volume': [int(bar['volume']) for bar in bars],
            })
            
            return df
            
        except Exception as e:
            logger.error(f"Failed to get historical data for {symbol}: {e}")
            return pl.DataFrame()
    
    def get_intraday(self, symbol: str, minutes: int = 60) -> pl.DataFrame:
        """
        Get recent intraday data for liquidity analysis.
        
        Args:
            symbol: Ticker symbol
            minutes: Number of minutes of intraday data
        
        Returns:
            Polars DataFrame with 1-minute bars
        """
        # Calculate days needed (max 1 day for intraday)
        days = max(1, minutes // (60 * 6.5))  # Trading day is 6.5 hours
        return self.get_historical(symbol, days=days, interval="1m")
    
    def fetch_ohlcv(self, symbol: str, now: datetime, lookback_days: int = 30) -> pl.DataFrame:
        """
        Fetch OHLCV data (interface method for engines).
        
        Args:
            symbol: Ticker symbol
            now: Current datetime (ignored, uses current time)
            lookback_days: Number of days of history
        
        Returns:
            Polars DataFrame with OHLCV data
        """
        if not isinstance(lookback_days, int):
            lookback_days = 30
        return self.get_historical(symbol, days=lookback_days, interval="1d")


class PublicOptionsAdapter:
    """
    Options chain adapter using Public.com API.
    
    Provides:
    - Complete options chains with precise strikes
    - Real-time Greeks (delta, gamma, theta, vega)
    - Open interest and volume data
    """
    
    def __init__(self, api_key: Optional[str] = None, account_id: Optional[str] = None):
        """Initialize with API credentials."""
        self.api_key = api_key or os.getenv('PUBLIC_API_KEY', '')
        self.account_id = account_id or os.getenv('PUBLIC_ACCOUNT_ID', 'default')
        
        if not self.api_key:
            raise ValueError("PUBLIC_API_KEY environment variable or api_key argument required")
        
        self.client = PublicAPIClient(self.api_key, self.account_id)
    
    def fetch_chain(self, symbol: str, now: datetime) -> pl.DataFrame:
        """
        Fetch options chain (interface method for HedgeEngine).
        
        Args:
            symbol: Ticker symbol
            now: Current datetime (ignored, uses current time)
        
        Returns:
            Polars DataFrame with options chain
        """
        return self.get_chain(symbol, days_to_expiry=30)
    
    def get_chain(
        self,
        symbol: str,
        days_to_expiry: Optional[int] = None
    ) -> pl.DataFrame:
        """
        Get options chain for a symbol.
        
        Args:
            symbol: Ticker symbol
            days_to_expiry: Target days to expiration (finds closest)
        
        Returns:
            Polars DataFrame with complete options chain
        """
        try:
            # Step 1: Get available expiration dates
            exp_response = self.client.post(
                f"marketdata/{self.account_id}/option-expirations",
                json_data={
                    "symbol": symbol,
                    "instrument_type": "EQUITY"
                }
            )
            
            if not exp_response or 'expirations' not in exp_response:
                logger.warning(f"No option expirations available for {symbol}")
                return pl.DataFrame()
            
            expirations = exp_response.get('expirations', [])
            if not expirations:
                return pl.DataFrame()
            
            # Find closest expiration to target
            target_days = days_to_expiry or 30
            target_date = datetime.now(timezone.utc) + timedelta(days=target_days)
            
            closest_exp = min(
                expirations,
                key=lambda x: abs((datetime.fromisoformat(x.replace('Z', '+00:00')) - target_date).total_seconds())
            )
            
            # Step 2: Get options chain for that expiration
            chain_response = self.client.post(
                f"marketdata/{self.account_id}/options-chain",
                json_data={
                    "symbol": symbol,
                    "expiration": closest_exp,
                    "instrument_type": "EQUITY"
                }
            )
            
            if not chain_response or 'options' not in chain_response:
                logger.warning(f"No options chain data for {symbol} exp {closest_exp}")
                return pl.DataFrame()
            
            options = chain_response.get('options', [])
            if not options:
                return pl.DataFrame()
            
            # Step 3: Get Greeks for each option
            # Public.com provides Greeks in the chain response
            all_options_data = []
            
            for opt in options:
                option_data = {
                    'strike': float(opt.get('strike', 0)),
                    'option_type': opt.get('type', '').lower(),  # 'call' or 'put'
                    'expiry': closest_exp,
                    'bid': float(opt.get('bid', 0) or 0),
                    'ask': float(opt.get('ask', 0) or 0),
                    'last': float(opt.get('last', 0) or 0),
                    'volume': int(opt.get('volume', 0) or 0),
                    'open_interest': int(opt.get('open_interest', 0) or 0),
                    'implied_volatility': float(opt.get('implied_volatility', 0) or 0),
                }
                
                # Add Greeks if available
                greeks = opt.get('greeks', {})
                if greeks:
                    option_data.update({
                        'delta': float(greeks.get('delta', 0) or 0),
                        'gamma': float(greeks.get('gamma', 0) or 0),
                        'theta': float(greeks.get('theta', 0) or 0),
                        'vega': float(greeks.get('vega', 0) or 0),
                    })
                
                all_options_data.append(option_data)
            
            # Convert to Polars DataFrame
            df = pl.DataFrame(all_options_data)
            
            return df
            
        except Exception as e:
            logger.error(f"Failed to get options chain for {symbol}: {e}")
            return pl.DataFrame()
    
    def get_current_price(self, symbol: str) -> float:
        """Get current underlying price."""
        try:
            # Use market adapter to get quote
            market_adapter = PublicMarketAdapter(self.api_key, self.account_id)
            quote = market_adapter.get_quote(symbol)
            return quote.get('last', 0.0)
            
        except Exception as e:
            logger.error(f"Failed to get price for {symbol}: {e}")
            return 0.0


class PublicNewsAdapter:
    """
    News adapter using Public.com API.
    
    Note: Public.com may not have a dedicated news endpoint.
    This is a placeholder that can be enhanced with alternative news sources
    or Public.com's news feed if available.
    """
    
    def __init__(self, api_key: Optional[str] = None, account_id: Optional[str] = None):
        """Initialize adapter."""
        self.api_key = api_key or os.getenv('PUBLIC_API_KEY', '')
        self.account_id = account_id or os.getenv('PUBLIC_ACCOUNT_ID', 'default')
        
        if not self.api_key:
            logger.warning("PUBLIC_API_KEY not set, news adapter will return empty results")
        else:
            self.client = PublicAPIClient(self.api_key, self.account_id)
    
    def fetch_news(self, symbol: str, now: datetime, lookback_hours: int = 24) -> List[Dict]:
        """
        Fetch news (interface method for engines).
        
        Args:
            symbol: Ticker symbol
            now: Current datetime
            lookback_hours: Hours of news history
        
        Returns:
            List of news items
        """
        return self.get_recent_news(symbol, hours=lookback_hours)
    
    def get_recent_news(
        self,
        symbol: str,
        hours: int = 24
    ) -> List[Dict]:
        """
        Get recent news for a symbol.
        
        Note: Public.com API may not have a public news endpoint.
        This returns empty list as placeholder. Consider integrating:
        - NewsAPI.org
        - Finnhub
        - Alpha Vantage News
        - SEC EDGAR filings
        
        Returns:
            List of news items (currently empty)
        """
        # TODO: Integrate external news API or Public.com news feed if available
        logger.debug(f"News not implemented for {symbol}, returning empty list")
        return []


# Convenience function to create all adapters at once
def create_public_adapters(api_key: Optional[str] = None, account_id: Optional[str] = None):
    """
    Create all three adapters using Public.com API.
    
    Args:
        api_key: Public.com API key (defaults to PUBLIC_API_KEY env var)
        account_id: Account ID (defaults to PUBLIC_ACCOUNT_ID env var)
    
    Returns:
        Tuple of (market_adapter, options_adapter, news_adapter)
    """
    return (
        PublicMarketAdapter(api_key, account_id),
        PublicOptionsAdapter(api_key, account_id),
        PublicNewsAdapter(api_key, account_id),
    )
