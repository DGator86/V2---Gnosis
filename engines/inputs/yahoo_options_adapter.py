"""Yahoo Finance options chain adapter (FREE options data).

Based on: https://github.com/c0001/optiondata
Uses yfinance to fetch real options chains with calculated Greeks.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional, List
import polars as pl
import numpy as np
from loguru import logger

try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False
    yf = None

try:
    from scipy.stats import norm
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    norm = None


class YahooOptionsAdapter:
    """Fetch options chains from Yahoo Finance (FREE).
    
    Provides:
    - Real options chains for any symbol
    - Strike prices, expiries, bid/ask, volume, open interest
    - Calculated Greeks (using Black-Scholes)
    - 15-minute delay (adequate for non-HFT trading)
    
    This is your FREE alternative to CBOE DataShop, Tradier, or Polygon.
    """
    
    def __init__(self):
        """Initialize Yahoo options adapter."""
        if not YFINANCE_AVAILABLE:
            raise ImportError("yfinance not installed. Install with: pip install yfinance")
        
        if not SCIPY_AVAILABLE:
            raise ImportError("scipy not installed. Install with: pip install scipy")
        
        logger.info("YahooOptionsAdapter initialized (FREE tier - 15min delay)")
    
    def fetch_options_chain(
        self,
        symbol: str,
        expiry_date: Optional[str] = None,
        min_days_to_expiry: int = 7,
        max_days_to_expiry: int = 60,
    ) -> pl.DataFrame:
        """Fetch options chain from Yahoo Finance.
        
        Args:
            symbol: Stock symbol (e.g., "SPY", "AAPL")
            expiry_date: Specific expiry date (YYYY-MM-DD) or None for auto-select
            min_days_to_expiry: Minimum days to expiry for auto-select
            max_days_to_expiry: Maximum days to expiry for auto-select
            
        Returns:
            Polars DataFrame with options chain and calculated Greeks
        """
        try:
            ticker = yf.Ticker(symbol)
            
            # Get available expiry dates
            expiry_dates = ticker.options
            
            if not expiry_dates:
                raise ValueError(f"No options available for {symbol}")
            
            # Select expiry date
            if expiry_date is None:
                expiry_date = self._select_expiry_date(
                    expiry_dates,
                    min_days_to_expiry,
                    max_days_to_expiry,
                )
            
            logger.info(f"Fetching options chain for {symbol} expiring {expiry_date}")
            
            # Fetch options chain
            options = ticker.option_chain(expiry_date)
            
            # Get current spot price
            hist = ticker.history(period="1d", interval="1m")
            if hist.empty:
                raise ValueError(f"Could not fetch spot price for {symbol}")
            spot = float(hist["Close"].iloc[-1])
            
            # Convert to Polars and calculate Greeks
            chain = self._process_options_chain(
                calls=options.calls,
                puts=options.puts,
                spot=spot,
                expiry_date=expiry_date,
                symbol=symbol,
            )
            
            logger.info(
                f"Fetched {len(chain)} options for {symbol} "
                f"(spot=${spot:.2f}, expiry={expiry_date})"
            )
            
            return chain
            
        except Exception as e:
            logger.error(f"Failed to fetch options chain for {symbol}: {e}")
            raise
    
    def _select_expiry_date(
        self,
        expiry_dates: List[str],
        min_days: int,
        max_days: int,
    ) -> str:
        """Select appropriate expiry date from available options.
        
        Args:
            expiry_dates: List of available expiry dates (YYYY-MM-DD format)
            min_days: Minimum days to expiry
            max_days: Maximum days to expiry
            
        Returns:
            Selected expiry date
        """
        now = datetime.now()
        
        # Filter expiry dates within range
        valid_dates = []
        for date_str in expiry_dates:
            expiry = datetime.strptime(date_str, "%Y-%m-%d")
            days_to_expiry = (expiry - now).days
            
            if min_days <= days_to_expiry <= max_days:
                valid_dates.append((date_str, days_to_expiry))
        
        if not valid_dates:
            # If no dates in range, use closest available
            logger.warning(
                f"No expiry dates in range {min_days}-{max_days} days, "
                f"using closest available"
            )
            return expiry_dates[0]
        
        # Select date closest to 30 days
        valid_dates.sort(key=lambda x: abs(x[1] - 30))
        selected = valid_dates[0][0]
        
        logger.debug(f"Selected expiry date: {selected} ({valid_dates[0][1]} days)")
        
        return selected
    
    def _process_options_chain(
        self,
        calls,
        puts,
        spot: float,
        expiry_date: str,
        symbol: str,
    ) -> pl.DataFrame:
        """Process options chain and calculate Greeks.
        
        Args:
            calls: Pandas DataFrame with call options
            puts: Pandas DataFrame with put options
            spot: Current spot price
            expiry_date: Expiry date (YYYY-MM-DD)
            symbol: Symbol
            
        Returns:
            Polars DataFrame with options chain and Greeks
        """
        # Calculate time to expiry
        expiry = datetime.strptime(expiry_date, "%Y-%m-%d")
        T = (expiry - datetime.now()).days / 365.0
        
        # Process calls
        call_rows = []
        for _, row in calls.iterrows():
            greeks = self._calculate_greeks(
                spot=spot,
                strike=row["strike"],
                T=T,
                sigma=row.get("impliedVolatility", 0.20),
                r=0.05,  # Assume 5% risk-free rate
                option_type="call",
            )
            
            call_rows.append({
                "symbol": symbol,
                "strike": row["strike"],
                "expiry": expiry_date,
                "option_type": "call",
                "bid": row.get("bid", 0.0),
                "ask": row.get("ask", 0.0),
                "last_price": row.get("lastPrice", 0.0),
                "volume": int(row.get("volume", 0) or 0),
                "open_interest": int(row.get("openInterest", 0) or 0),
                "implied_volatility": row.get("impliedVolatility", 0.0),
                # Greeks
                "delta": greeks["delta"],
                "gamma": greeks["gamma"],
                "theta": greeks["theta"],
                "vega": greeks["vega"],
                "vanna": greeks["vanna"],
                "charm": greeks["charm"],
            })
        
        # Process puts
        put_rows = []
        for _, row in puts.iterrows():
            greeks = self._calculate_greeks(
                spot=spot,
                strike=row["strike"],
                T=T,
                sigma=row.get("impliedVolatility", 0.20),
                r=0.05,
                option_type="put",
            )
            
            put_rows.append({
                "symbol": symbol,
                "strike": row["strike"],
                "expiry": expiry_date,
                "option_type": "put",
                "bid": row.get("bid", 0.0),
                "ask": row.get("ask", 0.0),
                "last_price": row.get("lastPrice", 0.0),
                "volume": int(row.get("volume", 0) or 0),
                "open_interest": int(row.get("openInterest", 0) or 0),
                "implied_volatility": row.get("impliedVolatility", 0.0),
                # Greeks
                "delta": greeks["delta"],
                "gamma": greeks["gamma"],
                "theta": greeks["theta"],
                "vega": greeks["vega"],
                "vanna": greeks["vanna"],
                "charm": greeks["charm"],
            })
        
        # Combine and convert to Polars
        all_rows = call_rows + put_rows
        df = pl.DataFrame(all_rows)
        
        return df
    
    def _calculate_greeks(
        self,
        spot: float,
        strike: float,
        T: float,
        sigma: float,
        r: float,
        option_type: str,
    ) -> dict:
        """Calculate option Greeks using Black-Scholes model.
        
        Args:
            spot: Current underlying price
            strike: Strike price
            T: Time to expiry (years)
            sigma: Implied volatility
            r: Risk-free rate
            option_type: "call" or "put"
            
        Returns:
            Dictionary with Greeks
        """
        # Handle edge cases
        if T <= 0:
            T = 1.0 / 365.0
        if sigma <= 0:
            sigma = 0.20  # Default to 20% vol
        
        # Calculate d1 and d2
        d1 = (np.log(spot / strike) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)
        
        # Delta
        if option_type == "call":
            delta = norm.cdf(d1)
        else:  # put
            delta = -norm.cdf(-d1)
        
        # Gamma (same for calls and puts)
        gamma = norm.pdf(d1) / (spot * sigma * np.sqrt(T))
        
        # Vega (same for calls and puts, per 1% change)
        vega = spot * norm.pdf(d1) * np.sqrt(T) / 100.0
        
        # Theta (per day)
        if option_type == "call":
            theta = (
                -spot * norm.pdf(d1) * sigma / (2 * np.sqrt(T))
                - r * strike * np.exp(-r * T) * norm.cdf(d2)
            ) / 365.0
        else:  # put
            theta = (
                -spot * norm.pdf(d1) * sigma / (2 * np.sqrt(T))
                + r * strike * np.exp(-r * T) * norm.cdf(-d2)
            ) / 365.0
        
        # Vanna (second-order: delta/volatility)
        vanna = -norm.pdf(d1) * d2 / sigma
        
        # Charm (second-order: delta/time, per day)
        if option_type == "call":
            charm = -norm.pdf(d1) * (2 * r * T - d2 * sigma * np.sqrt(T)) / (2 * T * sigma * np.sqrt(T))
        else:
            charm = norm.pdf(d1) * (2 * r * T - d2 * sigma * np.sqrt(T)) / (2 * T * sigma * np.sqrt(T))
        
        charm = charm / 365.0  # Per day
        
        return {
            "delta": float(delta),
            "gamma": float(gamma),
            "theta": float(theta),
            "vega": float(vega),
            "vanna": float(vanna),
            "charm": float(charm),
        }
    
    def test_connection(self, symbol: str = "SPY") -> bool:
        """Test connection by fetching options for a symbol.
        
        Args:
            symbol: Symbol to test (default: SPY)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            chain = self.fetch_options_chain(symbol)
            
            if chain.is_empty():
                logger.error(f"Options chain test failed: No data for {symbol}")
                return False
            
            logger.info(f"Options chain test SUCCESS: {len(chain)} options fetched")
            return True
            
        except Exception as e:
            logger.error(f"Options chain test failed: {e}")
            return False


# Convenience function
def get_options_chain(symbol: str) -> pl.DataFrame:
    """Get options chain for a symbol.
    
    Args:
        symbol: Stock symbol
        
    Returns:
        Polars DataFrame with options chain and Greeks
    """
    adapter = YahooOptionsAdapter()
    return adapter.fetch_options_chain(symbol)


# Example usage
if __name__ == "__main__":
    import sys
    
    print("Testing Yahoo Options Adapter...")
    
    adapter = YahooOptionsAdapter()
    
    # Test with SPY
    symbol = "SPY"
    print(f"\nFetching options chain for {symbol}...")
    
    try:
        chain = adapter.fetch_options_chain(symbol)
        
        print(f"✅ Fetched {len(chain)} options")
        print(f"\nSample data:")
        print(chain.head(6))
        
        print(f"\nGreeks statistics:")
        print(f"  Gamma: min={chain['gamma'].min():.6f}, max={chain['gamma'].max():.6f}")
        print(f"  Delta: min={chain['delta'].min():.4f}, max={chain['delta'].max():.4f}")
        print(f"  Vanna: min={chain['vanna'].min():.6f}, max={chain['vanna'].max():.6f}")
        
        print(f"\nOpen Interest:")
        print(f"  Total: {chain['open_interest'].sum():,}")
        print(f"  Calls: {chain.filter(pl.col('option_type') == 'call')['open_interest'].sum():,}")
        print(f"  Puts: {chain.filter(pl.col('option_type') == 'put')['open_interest'].sum():,}")
        
        print("\n✅ Yahoo Options Adapter working!")
        print("   You now have FREE options data for the Hedge Engine.")
        
    except Exception as e:
        print(f"\n❌ Failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
