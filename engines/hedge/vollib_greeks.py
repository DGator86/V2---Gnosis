"""
Precise Option Greeks using vollib Library

Provides production-grade Greeks calculations using the vollib library.
Supports multiple pricing models:
- Black-Scholes (European options)
- Black-Scholes-Merton (dividend-adjusted)
- Black (futures options)

Install: pip install vollib

This replaces the basic Black-Scholes implementation with a more robust
and tested library specifically designed for options pricing.
"""

from typing import Dict, Literal
from datetime import date, datetime
from loguru import logger
from pydantic import BaseModel

try:
    from vollib.black_scholes import black_scholes as bs
    from vollib.black_scholes.greeks import analytical as greeks
    from vollib.black_scholes_merton import black_scholes_merton as bsm
    from vollib.black_scholes_merton.greeks import analytical as bsm_greeks
    VOLLIB_AVAILABLE = True
except ImportError:
    VOLLIB_AVAILABLE = False
    logger.warning(
        "vollib not installed. Install with: pip install vollib"
    )


class OptionGreeks(BaseModel):
    """Complete set of option Greeks."""
    
    # First-order Greeks
    delta: float  # Price sensitivity
    gamma: float  # Delta sensitivity (curvature)
    vega: float   # Volatility sensitivity
    theta: float  # Time decay
    rho: float    # Interest rate sensitivity
    
    # Second-order Greeks
    vanna: float = 0.0   # Delta sensitivity to volatility
    charm: float = 0.0   # Delta decay over time
    vomma: float = 0.0   # Vega sensitivity to volatility
    
    # Option value
    price: float


class VolilibGreeksCalculator:
    """
    Production-grade Greeks calculator using vollib.
    
    Advantages over custom implementation:
    - Industry-standard calculations
    - Extensively tested
    - Supports multiple models
    - Handles edge cases properly
    - Vectorized operations
    """
    
    def __init__(self, risk_free_rate: float = 0.05):
        """
        Initialize Greeks calculator.
        
        Args:
            risk_free_rate: Annual risk-free rate (default 5%)
        """
        if not VOLLIB_AVAILABLE:
            raise ImportError(
                "vollib required. Install with: pip install vollib"
            )
        
        self.risk_free_rate = risk_free_rate
        logger.info(f"✅ vollib Greeks calculator initialized (r={risk_free_rate})")
    
    def calculate_greeks(
        self,
        spot: float,
        strike: float,
        time_to_expiry: float,
        volatility: float,
        option_type: Literal["call", "put"],
        dividend_yield: float = 0.0,
        model: Literal["bs", "bsm"] = "bs"
    ) -> OptionGreeks:
        """
        Calculate complete Greeks for an option.
        
        Args:
            spot: Current underlying price
            strike: Option strike price
            time_to_expiry: Time to expiration in years
            volatility: Implied volatility (e.g., 0.25 for 25%)
            option_type: "call" or "put"
            dividend_yield: Annual dividend yield (default 0)
            model: "bs" (Black-Scholes) or "bsm" (Black-Scholes-Merton)
        
        Returns:
            OptionGreeks with all calculated values
        """
        flag = 'c' if option_type == "call" else 'p'
        
        try:
            if model == "bsm" and dividend_yield > 0:
                # Black-Scholes-Merton (with dividends)
                price = bsm(
                    flag=flag,
                    S=spot,
                    K=strike,
                    t=time_to_expiry,
                    r=self.risk_free_rate,
                    sigma=volatility,
                    q=dividend_yield
                )
                
                delta = bsm_greeks.delta(flag, spot, strike, time_to_expiry, 
                                        self.risk_free_rate, volatility, dividend_yield)
                gamma = bsm_greeks.gamma(flag, spot, strike, time_to_expiry, 
                                        self.risk_free_rate, volatility, dividend_yield)
                vega = bsm_greeks.vega(flag, spot, strike, time_to_expiry, 
                                      self.risk_free_rate, volatility, dividend_yield)
                theta = bsm_greeks.theta(flag, spot, strike, time_to_expiry, 
                                        self.risk_free_rate, volatility, dividend_yield)
                rho = bsm_greeks.rho(flag, spot, strike, time_to_expiry, 
                                    self.risk_free_rate, volatility, dividend_yield)
            else:
                # Black-Scholes (no dividends)
                price = bs(
                    flag=flag,
                    S=spot,
                    K=strike,
                    t=time_to_expiry,
                    r=self.risk_free_rate,
                    sigma=volatility
                )
                
                delta = greeks.delta(flag, spot, strike, time_to_expiry, 
                                    self.risk_free_rate, volatility)
                gamma = greeks.gamma(flag, spot, strike, time_to_expiry, 
                                    self.risk_free_rate, volatility)
                vega = greeks.vega(flag, spot, strike, time_to_expiry, 
                                  self.risk_free_rate, volatility)
                theta = greeks.theta(flag, spot, strike, time_to_expiry, 
                                    self.risk_free_rate, volatility)
                rho = greeks.rho(flag, spot, strike, time_to_expiry, 
                                self.risk_free_rate, volatility)
            
            # Calculate second-order Greeks
            vanna = self._calculate_vanna(spot, strike, time_to_expiry, 
                                         volatility, option_type)
            charm = self._calculate_charm(spot, strike, time_to_expiry, 
                                         volatility, option_type)
            vomma = self._calculate_vomma(spot, strike, time_to_expiry, 
                                         volatility, option_type)
            
            return OptionGreeks(
                delta=delta,
                gamma=gamma,
                vega=vega / 100,  # vollib returns vega in % terms
                theta=theta / 365,  # Convert to daily theta
                rho=rho / 100,      # vollib returns rho in % terms
                vanna=vanna,
                charm=charm,
                vomma=vomma,
                price=price
            )
        
        except Exception as e:
            logger.error(f"Failed to calculate Greeks: {e}")
            raise
    
    def calculate_greeks_from_date(
        self,
        spot: float,
        strike: float,
        expiry_date: date,
        volatility: float,
        option_type: Literal["call", "put"],
        current_date: date = None,
        dividend_yield: float = 0.0
    ) -> OptionGreeks:
        """
        Calculate Greeks using calendar dates.
        
        Args:
            spot: Current underlying price
            strike: Option strike price
            expiry_date: Expiration date
            volatility: Implied volatility
            option_type: "call" or "put"
            current_date: Current date (defaults to today)
            dividend_yield: Annual dividend yield
        
        Returns:
            OptionGreeks with all calculated values
        """
        if current_date is None:
            current_date = date.today()
        
        # Calculate time to expiry in years
        days_to_expiry = (expiry_date - current_date).days
        time_to_expiry = days_to_expiry / 365.0
        
        if time_to_expiry <= 0:
            logger.warning(f"Option expired on {expiry_date}")
            # Return zero Greeks for expired option
            return OptionGreeks(
                delta=0.0, gamma=0.0, vega=0.0, theta=0.0, rho=0.0,
                vanna=0.0, charm=0.0, vomma=0.0, price=0.0
            )
        
        return self.calculate_greeks(
            spot=spot,
            strike=strike,
            time_to_expiry=time_to_expiry,
            volatility=volatility,
            option_type=option_type,
            dividend_yield=dividend_yield
        )
    
    def _calculate_vanna(
        self,
        spot: float,
        strike: float,
        time_to_expiry: float,
        volatility: float,
        option_type: str
    ) -> float:
        """
        Calculate vanna (∂²V/∂S∂σ).
        
        Vanna measures the rate of change of delta with respect to volatility.
        """
        from scipy.stats import norm
        import numpy as np
        
        d1 = (np.log(spot / strike) + (self.risk_free_rate + 0.5 * volatility**2) * time_to_expiry) / \
             (volatility * np.sqrt(time_to_expiry))
        d2 = d1 - volatility * np.sqrt(time_to_expiry)
        
        vanna = -norm.pdf(d1) * d2 / volatility
        
        return vanna
    
    def _calculate_charm(
        self,
        spot: float,
        strike: float,
        time_to_expiry: float,
        volatility: float,
        option_type: str
    ) -> float:
        """
        Calculate charm (∂²V/∂S∂t).
        
        Charm measures the rate of change of delta over time (delta decay).
        """
        from scipy.stats import norm
        import numpy as np
        
        d1 = (np.log(spot / strike) + (self.risk_free_rate + 0.5 * volatility**2) * time_to_expiry) / \
             (volatility * np.sqrt(time_to_expiry))
        d2 = d1 - volatility * np.sqrt(time_to_expiry)
        
        charm = -norm.pdf(d1) * (self.risk_free_rate / (volatility * np.sqrt(time_to_expiry)) - \
                                 d2 / (2 * time_to_expiry))
        
        if option_type == "put":
            charm = charm - self.risk_free_rate * norm.cdf(-d2) * np.exp(-self.risk_free_rate * time_to_expiry)
        else:
            charm = charm + self.risk_free_rate * norm.cdf(d2) * np.exp(-self.risk_free_rate * time_to_expiry)
        
        return charm / 365  # Convert to daily
    
    def _calculate_vomma(
        self,
        spot: float,
        strike: float,
        time_to_expiry: float,
        volatility: float,
        option_type: str
    ) -> float:
        """
        Calculate vomma (∂²V/∂σ²).
        
        Vomma measures the rate of change of vega with respect to volatility.
        """
        from scipy.stats import norm
        import numpy as np
        
        d1 = (np.log(spot / strike) + (self.risk_free_rate + 0.5 * volatility**2) * time_to_expiry) / \
             (volatility * np.sqrt(time_to_expiry))
        d2 = d1 - volatility * np.sqrt(time_to_expiry)
        
        vomma = spot * norm.pdf(d1) * np.sqrt(time_to_expiry) * d1 * d2 / volatility
        
        return vomma / 100  # Scale


# Example usage
if __name__ == "__main__":
    from datetime import timedelta
    
    # Initialize calculator
    calc = VolilibGreeksCalculator(risk_free_rate=0.05)
    
    print("\n" + "="*60)
    print("VOLLIB GREEKS CALCULATOR DEMO")
    print("="*60)
    
    # Example 1: ATM call option
    print("\n1️⃣  ATM Call Option (30 days to expiry)")
    print("-" * 60)
    
    greeks = calc.calculate_greeks(
        spot=450.0,
        strike=450.0,
        time_to_expiry=30/365,
        volatility=0.25,
        option_type="call"
    )
    
    print(f"\nSpot: $450.00 | Strike: $450.00 | IV: 25% | 30 DTE")
    print(f"\nOption Price: ${greeks.price:.2f}")
    print(f"\nFirst-Order Greeks:")
    print(f"  Delta:  {greeks.delta:+.4f}  (price sensitivity)")
    print(f"  Gamma:  {greeks.gamma:+.6f}  (delta sensitivity)")
    print(f"  Vega:   {greeks.vega:+.4f}  (vol sensitivity)")
    print(f"  Theta:  {greeks.theta:+.4f}  (daily decay)")
    print(f"  Rho:    {greeks.rho:+.4f}  (rate sensitivity)")
    print(f"\nSecond-Order Greeks:")
    print(f"  Vanna:  {greeks.vanna:+.6f}  (delta-vol sensitivity)")
    print(f"  Charm:  {greeks.charm:+.6f}  (delta decay)")
    print(f"  Vomma:  {greeks.vomma:+.6f}  (vega-vol sensitivity)")
    
    # Example 2: OTM put option
    print("\n2️⃣  OTM Put Option (30 days to expiry)")
    print("-" * 60)
    
    greeks_put = calc.calculate_greeks(
        spot=450.0,
        strike=440.0,
        time_to_expiry=30/365,
        volatility=0.30,
        option_type="put"
    )
    
    print(f"\nSpot: $450.00 | Strike: $440.00 | IV: 30% | 30 DTE")
    print(f"\nOption Price: ${greeks_put.price:.2f}")
    print(f"\nFirst-Order Greeks:")
    print(f"  Delta:  {greeks_put.delta:+.4f}")
    print(f"  Gamma:  {greeks_put.gamma:+.6f}")
    print(f"  Vega:   {greeks_put.vega:+.4f}")
    print(f"  Theta:  {greeks_put.theta:+.4f}")
    print(f"  Rho:    {greeks_put.rho:+.4f}")
    
    # Example 3: With dividends (BSM model)
    print("\n3️⃣  ATM Call with Dividends (BSM Model)")
    print("-" * 60)
    
    greeks_div = calc.calculate_greeks(
        spot=450.0,
        strike=450.0,
        time_to_expiry=30/365,
        volatility=0.25,
        option_type="call",
        dividend_yield=0.02,  # 2% dividend yield
        model="bsm"
    )
    
    print(f"\nSpot: $450.00 | Strike: $450.00 | IV: 25% | Div: 2% | 30 DTE")
    print(f"\nOption Price: ${greeks_div.price:.2f}")
    print(f"Delta: {greeks_div.delta:+.4f} (adjusted for dividends)")
    
    # Example 4: Calendar date usage
    print("\n4️⃣  Using Calendar Dates")
    print("-" * 60)
    
    expiry = date.today() + timedelta(days=45)
    
    greeks_date = calc.calculate_greeks_from_date(
        spot=450.0,
        strike=455.0,
        expiry_date=expiry,
        volatility=0.28,
        option_type="call"
    )
    
    print(f"\nSpot: $450.00 | Strike: $455.00 | Expiry: {expiry}")
    print(f"\nOption Price: ${greeks_date.price:.2f}")
    print(f"Delta: {greeks_date.delta:+.4f}")
    print(f"Gamma: {greeks_date.gamma:+.6f}")
    
    print("\n" + "="*60)
    print("✅ vollib provides industry-standard Greeks calculations!")
    print("="*60)
