"""Sample options data generator for testing Hedge Engine.

Generates realistic-looking options chain data with Greeks for testing purposes.
Use this when you don't have access to real options data yet.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional
import numpy as np
import polars as pl
from loguru import logger


class SampleOptionsGenerator:
    """Generate sample options chain data for testing.
    
    This generates realistic-looking options data with Greeks based on:
    - Black-Scholes model for option pricing
    - Typical Greek values for at-the-money, in-the-money, out-of-the-money options
    - Realistic open interest and volume distributions
    """
    
    def __init__(
        self,
        spot: float = 450.0,
        volatility: float = 0.20,
        risk_free_rate: float = 0.05,
    ):
        """Initialize sample options generator.
        
        Args:
            spot: Current underlying price
            volatility: Implied volatility (e.g., 0.20 = 20%)
            risk_free_rate: Risk-free rate (e.g., 0.05 = 5%)
        """
        self.spot = spot
        self.volatility = volatility
        self.risk_free_rate = risk_free_rate
    
    def generate_chain(
        self,
        n_strikes: int = 20,
        days_to_expiry: int = 30,
        strike_spacing: float = 5.0,
    ) -> pl.DataFrame:
        """Generate a complete options chain with Greeks.
        
        Args:
            n_strikes: Number of strike prices to generate
            days_to_expiry: Days until expiration
            strike_spacing: Dollar spacing between strikes
            
        Returns:
            Polars DataFrame with options chain data
        """
        # Generate strike prices around spot
        center_strike = round(self.spot / strike_spacing) * strike_spacing
        strikes = [
            center_strike + (i - n_strikes // 2) * strike_spacing
            for i in range(n_strikes)
        ]
        
        # Calculate time to expiry in years
        T = days_to_expiry / 365.0
        
        # Generate expiry date
        expiry = datetime.now() + timedelta(days=days_to_expiry)
        
        # Generate data for calls and puts
        rows = []
        
        for strike in strikes:
            # Calculate moneyness
            moneyness = self.spot / strike
            
            # Calculate Greeks for call
            call_greeks = self._calculate_greeks(
                spot=self.spot,
                strike=strike,
                T=T,
                sigma=self.volatility,
                r=self.risk_free_rate,
                option_type="call",
            )
            
            # Calculate Greeks for put
            put_greeks = self._calculate_greeks(
                spot=self.spot,
                strike=strike,
                T=T,
                sigma=self.volatility,
                r=self.risk_free_rate,
                option_type="put",
            )
            
            # Generate open interest and volume (higher near ATM)
            atm_factor = np.exp(-0.5 * ((moneyness - 1.0) / 0.1) ** 2)
            
            call_oi = int(1000 * atm_factor * np.random.uniform(0.5, 1.5))
            put_oi = int(1000 * atm_factor * np.random.uniform(0.5, 1.5))
            
            call_volume = int(call_oi * np.random.uniform(0.01, 0.1))
            put_volume = int(put_oi * np.random.uniform(0.01, 0.1))
            
            # Call row
            rows.append({
                "strike": strike,
                "expiry": expiry,
                "option_type": "call",
                "gamma": call_greeks["gamma"],
                "delta": call_greeks["delta"],
                "vanna": call_greeks["vanna"],
                "charm": call_greeks["charm"],
                "vega": call_greeks["vega"],
                "theta": call_greeks["theta"],
                "open_interest": call_oi,
                "volume": call_volume,
                "bid": call_greeks["price"] * 0.98,
                "ask": call_greeks["price"] * 1.02,
                "implied_volatility": self.volatility,
            })
            
            # Put row
            rows.append({
                "strike": strike,
                "expiry": expiry,
                "option_type": "put",
                "gamma": put_greeks["gamma"],
                "delta": put_greeks["delta"],
                "vanna": put_greeks["vanna"],
                "charm": put_greeks["charm"],
                "vega": put_greeks["vega"],
                "theta": put_greeks["theta"],
                "open_interest": put_oi,
                "volume": put_volume,
                "bid": put_greeks["price"] * 0.98,
                "ask": put_greeks["price"] * 1.02,
                "implied_volatility": self.volatility,
            })
        
        df = pl.DataFrame(rows)
        
        logger.info(
            f"Generated sample options chain: {len(df)} options "
            f"({n_strikes} strikes × 2 types) for spot={self.spot:.2f}"
        )
        
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
            sigma: Volatility
            r: Risk-free rate
            option_type: "call" or "put"
            
        Returns:
            Dictionary with Greeks and price
        """
        from scipy.stats import norm
        
        # Avoid division by zero
        if T <= 0:
            T = 1.0 / 365.0
        
        # Calculate d1 and d2
        d1 = (np.log(spot / strike) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)
        
        # Calculate option price
        if option_type == "call":
            price = spot * norm.cdf(d1) - strike * np.exp(-r * T) * norm.cdf(d2)
            delta = norm.cdf(d1)
        else:  # put
            price = strike * np.exp(-r * T) * norm.cdf(-d2) - spot * norm.cdf(-d1)
            delta = -norm.cdf(-d1)
        
        # Calculate gamma (same for calls and puts)
        gamma = norm.pdf(d1) / (spot * sigma * np.sqrt(T))
        
        # Calculate vega (same for calls and puts)
        vega = spot * norm.pdf(d1) * np.sqrt(T) / 100.0  # Per 1% change in vol
        
        # Calculate theta
        if option_type == "call":
            theta = (
                -spot * norm.pdf(d1) * sigma / (2 * np.sqrt(T))
                - r * strike * np.exp(-r * T) * norm.cdf(d2)
            ) / 365.0  # Per day
        else:  # put
            theta = (
                -spot * norm.pdf(d1) * sigma / (2 * np.sqrt(T))
                + r * strike * np.exp(-r * T) * norm.cdf(-d2)
            ) / 365.0  # Per day
        
        # Calculate vanna (simplified approximation)
        vanna = -norm.pdf(d1) * d2 / sigma
        
        # Calculate charm (simplified approximation)
        if option_type == "call":
            charm = -norm.pdf(d1) * (2 * r * T - d2 * sigma * np.sqrt(T)) / (2 * T * sigma * np.sqrt(T))
        else:
            charm = norm.pdf(d1) * (2 * r * T - d2 * sigma * np.sqrt(T)) / (2 * T * sigma * np.sqrt(T))
        
        return {
            "price": price,
            "delta": delta,
            "gamma": gamma,
            "vega": vega,
            "theta": theta,
            "vanna": vanna,
            "charm": charm,
        }


def generate_sample_chain_for_testing(
    symbol: str = "SPY",
    spot: Optional[float] = None,
) -> pl.DataFrame:
    """Generate sample options chain for testing.
    
    Args:
        symbol: Symbol (for logging purposes)
        spot: Current spot price (REQUIRED - yfinance removed, must provide spot)
        
    Returns:
        Polars DataFrame with sample options chain
    """
    # Get spot price if not provided
    if spot is None:
        logger.error("NOTE: yfinance removed - spot price is now REQUIRED")
        raise ValueError(
            "spot parameter is required. yfinance has been removed. "
            "Use Unusual Whales or Public.com to fetch current price first."
        )
    
    # Generate chain
    generator = SampleOptionsGenerator(spot=spot)
    chain = generator.generate_chain(n_strikes=20, days_to_expiry=30)
    
    return chain


# Example usage
if __name__ == "__main__":
    import sys
    
    # Check if scipy is available
    try:
        import scipy
    except ImportError:
        print("❌ scipy not installed. Install with: pip install scipy")
        sys.exit(1)
    
    print("Generating sample options chain...")
    
    # Generate sample chain
    generator = SampleOptionsGenerator(spot=450.0, volatility=0.20)
    chain = generator.generate_chain(n_strikes=10, days_to_expiry=30)
    
    print(f"\n✅ Generated {len(chain)} options")
    print(f"\nSample data:")
    print(chain.head(6))
    
    print(f"\nGamma statistics:")
    print(f"  Min: {chain['gamma'].min():.6f}")
    print(f"  Max: {chain['gamma'].max():.6f}")
    print(f"  Mean: {chain['gamma'].mean():.6f}")
    
    print(f"\nDelta statistics:")
    print(f"  Calls - Min: {chain.filter(pl.col('option_type') == 'call')['delta'].min():.4f}")
    print(f"  Calls - Max: {chain.filter(pl.col('option_type') == 'call')['delta'].max():.4f}")
    print(f"  Puts - Min: {chain.filter(pl.col('option_type') == 'put')['delta'].min():.4f}")
    print(f"  Puts - Max: {chain.filter(pl.col('option_type') == 'put')['delta'].max():.4f}")
    
    print("\n✅ Sample options chain generated successfully!")
    print("   You can now test the Hedge Engine without real options data.")
