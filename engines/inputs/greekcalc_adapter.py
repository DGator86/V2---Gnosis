"""
Greeks Calculator Adapter using greekcalc library.

Provides validation and additional Greeks calculations as a complement to
the Black-Scholes implementation in sample_options_generator.py and
yahoo_options_adapter.py.

Uses greekcalc library: https://github.com/cemkocagil/greekcalc

This adapter serves two purposes:
1. Validate Greeks from other sources (Yahoo, sample generator)
2. Fill in missing Greeks if data sources don't provide them
"""

from typing import Dict, Optional, List
from datetime import datetime, date
from loguru import logger
import polars as pl
from pydantic import BaseModel, Field

try:
    from greekcalc import GreekCalculator
    GREEKCALC_AVAILABLE = True
except ImportError:
    GREEKCALC_AVAILABLE = False
    logger.warning(
        "greekcalc library not installed. Install with: pip install greekcalc"
    )


class GreeksValidationResult(BaseModel):
    """Result of Greeks validation comparison."""
    
    strike: float
    expiry: str
    option_type: str
    
    # Original Greeks (from source)
    source_delta: Optional[float] = None
    source_gamma: Optional[float] = None
    source_theta: Optional[float] = None
    source_vega: Optional[float] = None
    source_rho: Optional[float] = None
    
    # Calculated Greeks (from greekcalc)
    calc_delta: Optional[float] = None
    calc_gamma: Optional[float] = None
    calc_theta: Optional[float] = None
    calc_vega: Optional[float] = None
    calc_rho: Optional[float] = None
    
    # Differences
    delta_diff: Optional[float] = None
    gamma_diff: Optional[float] = None
    theta_diff: Optional[float] = None
    vega_diff: Optional[float] = None
    rho_diff: Optional[float] = None
    
    # Validation status
    is_valid: bool = True
    warnings: List[str] = Field(default_factory=list)


class GreekCalcAdapter:
    """
    Adapter for greekcalc library to calculate and validate option Greeks.
    
    Supports:
    - Delta, Gamma, Theta, Vega, Rho calculation
    - Greeks validation against other sources
    - Multiple pricing models (Black-Scholes, Binomial, etc.)
    """
    
    def __init__(
        self,
        risk_free_rate: float = 0.05,
        model: str = "black_scholes"
    ):
        """
        Initialize Greeks calculator.
        
        Args:
            risk_free_rate: Annual risk-free rate (default 5%)
            model: Pricing model to use ("black_scholes", "binomial", etc.)
        """
        if not GREEKCALC_AVAILABLE:
            raise ImportError(
                "greekcalc library is required. Install with: pip install greekcalc"
            )
        
        self.risk_free_rate = risk_free_rate
        self.model = model
        self.calculator = GreekCalculator()
        
        logger.info(
            f"✅ GreekCalcAdapter initialized (model={model}, r={risk_free_rate})"
        )
    
    def calculate_greeks(
        self,
        spot_price: float,
        strike: float,
        expiry_date: date,
        option_type: str,
        volatility: float,
        current_date: Optional[date] = None
    ) -> Dict[str, float]:
        """
        Calculate all Greeks for a single option.
        
        Args:
            spot_price: Current price of underlying
            strike: Strike price
            expiry_date: Expiration date
            option_type: "call" or "put"
            volatility: Implied volatility (e.g., 0.25 for 25%)
            current_date: Current date (defaults to today)
        
        Returns:
            Dictionary with delta, gamma, theta, vega, rho
        """
        if current_date is None:
            current_date = date.today()
        
        # Calculate time to expiration in years
        days_to_expiry = (expiry_date - current_date).days
        time_to_expiry = days_to_expiry / 365.0
        
        if time_to_expiry <= 0:
            logger.warning(f"Option already expired: {expiry_date}")
            return {
                "delta": 0.0,
                "gamma": 0.0,
                "theta": 0.0,
                "vega": 0.0,
                "rho": 0.0
            }
        
        try:
            # Calculate Greeks using greekcalc
            greeks = self.calculator.calculate(
                spot=spot_price,
                strike=strike,
                time_to_maturity=time_to_expiry,
                volatility=volatility,
                risk_free_rate=self.risk_free_rate,
                option_type=option_type.lower()
            )
            
            return {
                "delta": greeks.get("delta", 0.0),
                "gamma": greeks.get("gamma", 0.0),
                "theta": greeks.get("theta", 0.0),
                "vega": greeks.get("vega", 0.0),
                "rho": greeks.get("rho", 0.0)
            }
        
        except Exception as e:
            logger.error(f"Failed to calculate Greeks: {e}")
            return {
                "delta": 0.0,
                "gamma": 0.0,
                "theta": 0.0,
                "vega": 0.0,
                "rho": 0.0
            }
    
    def validate_greeks(
        self,
        spot_price: float,
        strike: float,
        expiry_date: date,
        option_type: str,
        volatility: float,
        source_greeks: Dict[str, float],
        tolerance: float = 0.05,
        current_date: Optional[date] = None
    ) -> GreeksValidationResult:
        """
        Validate Greeks from another source by comparing with greekcalc.
        
        Args:
            spot_price: Current price of underlying
            strike: Strike price
            expiry_date: Expiration date
            option_type: "call" or "put"
            volatility: Implied volatility
            source_greeks: Greeks from external source to validate
            tolerance: Maximum allowed relative difference (default 5%)
            current_date: Current date (defaults to today)
        
        Returns:
            GreeksValidationResult with comparison details
        """
        # Calculate Greeks with greekcalc
        calc_greeks = self.calculate_greeks(
            spot_price=spot_price,
            strike=strike,
            expiry_date=expiry_date,
            option_type=option_type,
            volatility=volatility,
            current_date=current_date
        )
        
        # Initialize result
        result = GreeksValidationResult(
            strike=strike,
            expiry=str(expiry_date),
            option_type=option_type,
            source_delta=source_greeks.get("delta"),
            source_gamma=source_greeks.get("gamma"),
            source_theta=source_greeks.get("theta"),
            source_vega=source_greeks.get("vega"),
            source_rho=source_greeks.get("rho"),
            calc_delta=calc_greeks["delta"],
            calc_gamma=calc_greeks["gamma"],
            calc_theta=calc_greeks["theta"],
            calc_vega=calc_greeks["vega"],
            calc_rho=calc_greeks["rho"]
        )
        
        # Compare each Greek
        for greek_name in ["delta", "gamma", "theta", "vega", "rho"]:
            source_val = source_greeks.get(greek_name)
            calc_val = calc_greeks.get(greek_name, 0.0)
            
            if source_val is None:
                result.warnings.append(f"Missing {greek_name} in source")
                continue
            
            # Calculate relative difference
            if calc_val != 0:
                rel_diff = abs(source_val - calc_val) / abs(calc_val)
            else:
                rel_diff = abs(source_val - calc_val)
            
            # Store difference
            setattr(result, f"{greek_name}_diff", rel_diff)
            
            # Check tolerance
            if rel_diff > tolerance:
                result.is_valid = False
                result.warnings.append(
                    f"{greek_name} diff {rel_diff:.2%} exceeds tolerance {tolerance:.2%}"
                )
        
        return result
    
    def validate_options_chain(
        self,
        df_options: pl.DataFrame,
        spot_price: float,
        tolerance: float = 0.05,
        current_date: Optional[date] = None
    ) -> pl.DataFrame:
        """
        Validate Greeks for an entire options chain.
        
        Args:
            df_options: Polars DataFrame with options chain
                Must have columns: strike, expiry, option_type, implied_vol,
                delta, gamma, theta, vega, rho
            spot_price: Current spot price
            tolerance: Maximum allowed relative difference
            current_date: Current date (defaults to today)
        
        Returns:
            DataFrame with validation results added
        """
        logger.info(f"Validating Greeks for {len(df_options)} options")
        
        validation_results = []
        
        for row in df_options.iter_rows(named=True):
            # Parse expiry date
            expiry_date = datetime.strptime(row["expiry"], "%Y-%m-%d").date()
            
            # Get source Greeks
            source_greeks = {
                "delta": row.get("delta"),
                "gamma": row.get("gamma"),
                "theta": row.get("theta"),
                "vega": row.get("vega"),
                "rho": row.get("rho")
            }
            
            # Validate
            validation = self.validate_greeks(
                spot_price=spot_price,
                strike=row["strike"],
                expiry_date=expiry_date,
                option_type=row["option_type"],
                volatility=row.get("implied_vol", 0.25),
                source_greeks=source_greeks,
                tolerance=tolerance,
                current_date=current_date
            )
            
            validation_results.append(validation)
        
        # Convert to DataFrame
        validation_df = pl.DataFrame([
            {
                "strike": v.strike,
                "expiry": v.expiry,
                "option_type": v.option_type,
                "is_valid": v.is_valid,
                "delta_diff": v.delta_diff,
                "gamma_diff": v.gamma_diff,
                "theta_diff": v.theta_diff,
                "vega_diff": v.vega_diff,
                "rho_diff": v.rho_diff,
                "warnings": "|".join(v.warnings) if v.warnings else ""
            }
            for v in validation_results
        ])
        
        # Merge with original
        result = df_options.join(
            validation_df,
            on=["strike", "expiry", "option_type"],
            how="left"
        )
        
        # Log summary
        n_valid = validation_df.filter(pl.col("is_valid")).height
        n_total = len(validation_df)
        logger.info(f"✅ Validation complete: {n_valid}/{n_total} passed")
        
        return result
    
    def fill_missing_greeks(
        self,
        df_options: pl.DataFrame,
        spot_price: float,
        current_date: Optional[date] = None
    ) -> pl.DataFrame:
        """
        Fill in missing Greeks using greekcalc.
        
        Args:
            df_options: Options chain with potentially missing Greeks
            spot_price: Current spot price
            current_date: Current date
        
        Returns:
            DataFrame with all Greeks filled
        """
        logger.info(f"Filling missing Greeks for {len(df_options)} options")
        
        result_rows = []
        
        for row in df_options.iter_rows(named=True):
            row_dict = dict(row)
            
            # Check if Greeks are missing
            greeks_missing = any(
                row_dict.get(g) is None
                for g in ["delta", "gamma", "theta", "vega", "rho"]
            )
            
            if greeks_missing:
                # Parse expiry
                expiry_date = datetime.strptime(row["expiry"], "%Y-%m-%d").date()
                
                # Calculate Greeks
                greeks = self.calculate_greeks(
                    spot_price=spot_price,
                    strike=row["strike"],
                    expiry_date=expiry_date,
                    option_type=row["option_type"],
                    volatility=row.get("implied_vol", 0.25),
                    current_date=current_date
                )
                
                # Fill missing values
                for greek_name, greek_value in greeks.items():
                    if row_dict.get(greek_name) is None:
                        row_dict[greek_name] = greek_value
            
            result_rows.append(row_dict)
        
        result = pl.DataFrame(result_rows)
        logger.info("✅ Missing Greeks filled")
        
        return result


# Example usage
if __name__ == "__main__":
    import numpy as np
    from datetime import timedelta
    
    # Initialize adapter
    adapter = GreekCalcAdapter(risk_free_rate=0.05)
    
    # Example 1: Calculate Greeks for a single option
    print("\n" + "="*60)
    print("EXAMPLE 1: Calculate Greeks for Single Option")
    print("="*60)
    
    spot = 450.0
    strike = 450.0
    expiry = date.today() + timedelta(days=30)
    
    greeks = adapter.calculate_greeks(
        spot_price=spot,
        strike=strike,
        expiry_date=expiry,
        option_type="call",
        volatility=0.25
    )
    
    print(f"\nSPY ATM Call (Strike={strike}, 30 DTE):")
    for greek, value in greeks.items():
        print(f"  {greek}: {value:.6f}")
    
    # Example 2: Validate Greeks from external source
    print("\n" + "="*60)
    print("EXAMPLE 2: Validate Greeks from External Source")
    print("="*60)
    
    # Simulate Greeks from Yahoo Finance (with small error)
    yahoo_greeks = {
        "delta": greeks["delta"] * 1.02,  # 2% error
        "gamma": greeks["gamma"] * 0.98,  # 2% error
        "theta": greeks["theta"] * 1.01,  # 1% error
        "vega": greeks["vega"] * 0.99,    # 1% error
        "rho": greeks["rho"] * 1.03       # 3% error
    }
    
    validation = adapter.validate_greeks(
        spot_price=spot,
        strike=strike,
        expiry_date=expiry,
        option_type="call",
        volatility=0.25,
        source_greeks=yahoo_greeks,
        tolerance=0.05  # 5% tolerance
    )
    
    print(f"\nValidation Result:")
    print(f"  Valid: {validation.is_valid}")
    print(f"  Warnings: {validation.warnings}")
    print(f"\nGreeks Comparison:")
    print(f"  Delta: source={validation.source_delta:.6f}, calc={validation.calc_delta:.6f}, diff={validation.delta_diff:.2%}")
    print(f"  Gamma: source={validation.source_gamma:.6f}, calc={validation.calc_gamma:.6f}, diff={validation.gamma_diff:.2%}")
    
    # Example 3: Validate full options chain
    print("\n" + "="*60)
    print("EXAMPLE 3: Validate Full Options Chain")
    print("="*60)
    
    # Create sample options chain
    strikes = [440, 445, 450, 455, 460]
    chain_data = []
    
    for strike in strikes:
        for option_type in ["call", "put"]:
            # Calculate "true" Greeks
            true_greeks = adapter.calculate_greeks(
                spot_price=spot,
                strike=strike,
                expiry_date=expiry,
                option_type=option_type,
                volatility=0.25
            )
            
            # Add small random error
            chain_data.append({
                "strike": strike,
                "expiry": str(expiry),
                "option_type": option_type,
                "implied_vol": 0.25,
                "delta": true_greeks["delta"] * (1 + np.random.uniform(-0.02, 0.02)),
                "gamma": true_greeks["gamma"] * (1 + np.random.uniform(-0.02, 0.02)),
                "theta": true_greeks["theta"] * (1 + np.random.uniform(-0.02, 0.02)),
                "vega": true_greeks["vega"] * (1 + np.random.uniform(-0.02, 0.02)),
                "rho": true_greeks["rho"] * (1 + np.random.uniform(-0.02, 0.02))
            })
    
    df_chain = pl.DataFrame(chain_data)
    
    # Validate entire chain
    df_validated = adapter.validate_options_chain(
        df_options=df_chain,
        spot_price=spot,
        tolerance=0.05
    )
    
    print(f"\nValidated {len(df_validated)} options")
    print(f"Passed validation: {df_validated.filter(pl.col('is_valid')).height}/{len(df_validated)}")
    
    # Show failed validations
    df_failed = df_validated.filter(~pl.col("is_valid"))
    if len(df_failed) > 0:
        print(f"\n❌ Failed validations:")
        print(df_failed.select(["strike", "option_type", "warnings"]))
