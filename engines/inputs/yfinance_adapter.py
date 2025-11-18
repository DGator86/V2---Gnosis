"""
Yahoo Finance Data Adapter for Real Market Data

Provides free, real-time market data and options chains using yfinance.
This replaces the static stub adapters with actual market data.
"""

from __future__ import annotations

import yfinance as yf
import polars as pl
import pandas as pd
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, List
import logging

logger = logging.getLogger(__name__)


class YFinanceMarketAdapter:
    """
    Market data adapter using Yahoo Finance.
    
    Provides:
    - Real-time quotes
    - Historical OHLCV data
    - Volume and liquidity metrics
    """
    
    def __init__(self):
        self.cache = {}
        self.cache_duration = 60  # Cache data for 60 seconds
    
    def get_quote(self, symbol: str) -> Dict:
        """Get current quote for a symbol."""
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            # Get latest price data from intraday
            hist_intraday = ticker.history(period="1d", interval="1m")
            
            # Get daily data for accurate volume
            hist_daily = ticker.history(period="1d", interval="1d")
            
            if hist_intraday.empty and hist_daily.empty:
                # Fallback to multi-day data
                hist_daily = ticker.history(period="5d", interval="1d")
                if hist_daily.empty:
                    return {}
            
            # Use intraday for latest price, daily for volume
            if not hist_intraday.empty:
                latest = hist_intraday.iloc[-1]
                price = float(latest['Close'])
                open_price = float(latest['Open'])
                high = float(latest['High'])
                low = float(latest['Low'])
            elif not hist_daily.empty:
                latest = hist_daily.iloc[-1]
                price = float(latest['Close'])
                open_price = float(latest['Open'])
                high = float(latest['High'])
                low = float(latest['Low'])
            else:
                return {}
            
            # Always use daily volume (sum of all intraday volumes)
            if not hist_daily.empty:
                daily_volume = int(hist_daily.iloc[-1]['Volume'])
            else:
                # Fallback: sum intraday volumes
                daily_volume = int(hist_intraday['Volume'].sum())
            
            quote = {
                'symbol': symbol,
                'last': price,
                'close': price,
                'open': open_price,
                'high': high,
                'low': low,
                'volume': daily_volume,  # Use daily volume, not last minute
                'timestamp': datetime.now(timezone.utc),
            }
            
            # Add bid/ask if available
            if 'bid' in info and info['bid']:
                quote['bid'] = float(info['bid'])
            if 'ask' in info and info['ask']:
                quote['ask'] = float(info['ask'])
            
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
        
        Args:
            symbol: Ticker symbol
            days: Number of days of history
            interval: Data interval (1m, 5m, 15m, 1h, 1d)
        
        Returns:
            Polars DataFrame with OHLCV data
        """
        try:
            ticker = yf.Ticker(symbol)
            
            # Map days to yfinance period
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
        """Get recent intraday data for liquidity analysis."""
        return self.get_historical(symbol, days=1, interval="1m")
    
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
        # Ensure lookback_days is an int
        if not isinstance(lookback_days, int):
            lookback_days = 30
        return self.get_historical(symbol, days=lookback_days, interval="1d")


class YFinanceOptionsAdapter:
    """
    Options chain adapter using Yahoo Finance.
    
    Provides:
    - Complete options chains
    - Greeks (if available)
    - Open interest and volume
    """
    
    def __init__(self):
        pass
    
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
            Polars DataFrame with options chain data
        """
        try:
            ticker = yf.Ticker(symbol)
            
            # Get available expiration dates
            expirations = ticker.options
            
            if not expirations:
                logger.warning(f"No options available for {symbol}")
                return pl.DataFrame()
            
            # Find closest expiration to target
            target_date = datetime.now() + timedelta(days=days_to_expiry or 30)
            
            closest_exp = min(
                expirations,
                key=lambda x: abs((datetime.strptime(x, '%Y-%m-%d') - target_date).days)
            )
            
            # Get options chain for that expiration
            opt_chain = ticker.option_chain(closest_exp)
            
            # Combine calls and puts
            calls = opt_chain.calls.copy()
            calls['option_type'] = 'call'
            
            puts = opt_chain.puts.copy()
            puts['option_type'] = 'put'
            
            # Combine into single DataFrame (convert NaN to 0 and cast to appropriate types)
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
            
            # Add Greeks if available
            if 'delta' in calls.columns:
                all_options = all_options.with_columns([
                    pl.Series('delta', list(calls['delta'].fillna(0)) + list(puts['delta'].fillna(0))),
                ])
            
            if 'gamma' in calls.columns:
                all_options = all_options.with_columns([
                    pl.Series('gamma', list(calls['gamma'].fillna(0)) + list(puts['gamma'].fillna(0))),
                ])
            
            if 'theta' in calls.columns:
                all_options = all_options.with_columns([
                    pl.Series('theta', list(calls['theta'].fillna(0)) + list(puts['theta'].fillna(0))),
                ])
            
            if 'vega' in calls.columns:
                all_options = all_options.with_columns([
                    pl.Series('vega', list(calls['vega'].fillna(0)) + list(puts['vega'].fillna(0))),
                ])
            
            return all_options
            
        except Exception as e:
            logger.warning(f"Failed to get options chain for {symbol}: {e}")
            return pl.DataFrame()
    
    def get_current_price(self, symbol: str) -> float:
        """Get current underlying price."""
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="1d")
            
            if hist.empty:
                return 0.0
            
            return float(hist['Close'].iloc[-1])
            
        except Exception as e:
            logger.warning(f"Failed to get price for {symbol}: {e}")
            return 0.0


class YFinanceNewsAdapter:
    """
    News adapter using Yahoo Finance.
    
    Provides recent news headlines for sentiment analysis.
    """
    
    def __init__(self):
        pass
    
    def fetch_news(self, symbol: str, now: datetime, lookback_hours: int = 24) -> List[Dict]:
        """
        Fetch news (interface method for engines).
        
        Args:
            symbol: Ticker symbol
            now: Current datetime (ignored, uses current time)
            lookback_hours: Hours of news history
        
        Returns:
            List of news items
        """
        # Ensure lookback_hours is an int (sometimes gets datetime)
        if not isinstance(lookback_hours, int):
            lookback_hours = 24
        return self.get_recent_news(symbol, hours=lookback_hours)
    
    def get_recent_news(
        self,
        symbol: str,
        hours: int = 24
    ) -> List[Dict]:
        """
        Get recent news for a symbol.
        
        Returns list of news items with:
        - title
        - published_at
        - source
        """
        try:
            ticker = yf.Ticker(symbol)
            news = ticker.news
            
            if not news:
                return []
            
            # Convert to standard format
            cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
            
            formatted_news = []
            for item in news[:10]:  # Limit to 10 most recent
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


# Convenience function to create all adapters at once
def create_yfinance_adapters():
    """Create all three adapters using Yahoo Finance."""
    return (
        YFinanceMarketAdapter(),
        YFinanceOptionsAdapter(),
        YFinanceNewsAdapter(),
    )
