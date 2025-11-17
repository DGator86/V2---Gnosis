"""FRED (Federal Reserve Economic Data) adapter for macro regime features.

Provides access to 800K+ economic time series from the Federal Reserve.
FREE with API key: https://fred.stlouisfed.org/docs/api/api_key.html
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, Optional
import polars as pl
from loguru import logger

try:
    from fredapi import Fred
    FRED_AVAILABLE = True
except ImportError:
    FRED_AVAILABLE = False
    Fred = None


class FREDAdapter:
    """Fetch macro economic data from FRED (Federal Reserve Economic Data).
    
    Provides:
    - Interest rates (Fed Funds, Treasury yields)
    - Inflation (CPI, PCE)
    - Employment (unemployment rate, jobless claims)
    - GDP growth
    - Credit spreads
    - Economic indicators
    
    All data is FREE with API key (get from: https://fred.stlouisfed.org/)
    """
    
    # Key FRED series IDs
    SERIES_IDS = {
        # Interest Rates
        "fed_funds_rate": "DFF",  # Federal Funds Effective Rate (daily)
        "treasury_10y": "DGS10",  # 10-Year Treasury Constant Maturity Rate
        "treasury_2y": "DGS2",    # 2-Year Treasury Constant Maturity Rate
        "treasury_3m": "DTB3",    # 3-Month Treasury Bill Rate
        
        # Inflation
        "cpi": "CPIAUCSL",        # Consumer Price Index
        "pce": "PCE",             # Personal Consumption Expenditures
        "core_cpi": "CPILFESL",   # CPI Less Food & Energy
        
        # Employment
        "unemployment": "UNRATE",  # Unemployment Rate
        "jobless_claims": "ICSA",  # Initial Jobless Claims
        "nonfarm_payrolls": "PAYEMS",  # Nonfarm Payrolls
        
        # GDP & Growth
        "gdp": "GDP",             # Real GDP
        "gdp_growth": "A191RL1Q025SBEA",  # Real GDP Growth Rate
        
        # Credit & Risk
        "baa_spread": "BAA10Y",   # BAA Corporate Bond Spread
        "high_yield_spread": "BAMLH0A0HYM2",  # High Yield Spread
        
        # Market Indicators
        "sp500": "SP500",         # S&P 500 Index
        "wilshire5000": "WILL5000IND",  # Wilshire 5000 Total Market Index
    }
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize FRED adapter.
        
        Args:
            api_key: FRED API key (get from https://fred.stlouisfed.org/)
                     If None, will try to read from environment variable FRED_API_KEY
        """
        if not FRED_AVAILABLE:
            raise ImportError("fredapi not installed. Install with: pip install fredapi")
        
        if api_key is None:
            import os
            api_key = os.getenv("FRED_API_KEY")
            
            if api_key is None:
                raise ValueError(
                    "FRED API key required. Get one (FREE) from:\n"
                    "https://fred.stlouisfed.org/docs/api/api_key.html\n"
                    "Then set environment variable: FRED_API_KEY=your_key_here\n"
                    "Or pass as argument: FREDAdapter(api_key='your_key')"
                )
        
        self.fred = Fred(api_key=api_key)
        logger.info("FREDAdapter initialized with API key")
    
    def fetch_series(
        self,
        series_name: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pl.DataFrame:
        """Fetch a single FRED series.
        
        Args:
            series_name: Series name from SERIES_IDS (e.g., "fed_funds_rate")
            start_date: Start date (YYYY-MM-DD) or None for default
            end_date: End date (YYYY-MM-DD) or None for today
            
        Returns:
            Polars DataFrame with timestamp and value columns
        """
        if series_name not in self.SERIES_IDS:
            raise ValueError(
                f"Unknown series: {series_name}. "
                f"Available: {list(self.SERIES_IDS.keys())}"
            )
        
        series_id = self.SERIES_IDS[series_name]
        
        try:
            # Fetch data
            data = self.fred.get_series(
                series_id,
                observation_start=start_date,
                observation_end=end_date,
            )
            
            # Convert to Polars
            df = pl.DataFrame({
                "timestamp": data.index.astype(str).tolist(),
                series_name: data.values.tolist(),
            })
            
            # Parse timestamp
            df = df.with_columns([
                pl.col("timestamp").str.strptime(pl.Date, "%Y-%m-%d").alias("timestamp")
            ])
            
            logger.debug(f"Fetched {len(df)} observations for {series_name}")
            
            return df
            
        except Exception as e:
            logger.error(f"Failed to fetch FRED series {series_name}: {e}")
            raise
    
    def fetch_macro_regime_data(
        self,
        lookback_days: int = 365,
    ) -> Dict[str, any]:
        """Fetch key macro data for regime classification.
        
        Args:
            lookback_days: Number of days of history to fetch
            
        Returns:
            Dictionary with current values and historical data
        """
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
        
        regime_data = {}
        
        # Key series for regime classification
        key_series = [
            "fed_funds_rate",
            "treasury_10y",
            "treasury_2y",
            "treasury_3m",
            "cpi",
            "unemployment",
            "baa_spread",
        ]
        
        for series_name in key_series:
            try:
                df = self.fetch_series(series_name, start_date, end_date)
                
                # Get current value (most recent)
                current_value = float(df[series_name].tail(1)[0])
                
                regime_data[series_name] = {
                    "current": current_value,
                    "history": df,
                }
                
                logger.debug(f"{series_name}: {current_value:.2f}")
                
            except Exception as e:
                logger.warning(f"Could not fetch {series_name}: {e}")
                regime_data[series_name] = {
                    "current": None,
                    "history": pl.DataFrame(),
                }
        
        # Calculate derived features
        regime_data["yield_curve_slope"] = self._calculate_yield_curve_slope(regime_data)
        regime_data["recession_probability"] = self._calculate_recession_probability(regime_data)
        
        logger.info("Fetched macro regime data from FRED")
        
        return regime_data
    
    def _calculate_yield_curve_slope(self, regime_data: dict) -> float:
        """Calculate yield curve slope (10Y - 2Y).
        
        Args:
            regime_data: Dictionary with treasury data
            
        Returns:
            Yield curve slope (positive = normal, negative = inverted)
        """
        try:
            treasury_10y = regime_data.get("treasury_10y", {}).get("current")
            treasury_2y = regime_data.get("treasury_2y", {}).get("current")
            
            if treasury_10y is not None and treasury_2y is not None:
                slope = treasury_10y - treasury_2y
                return float(slope)
            else:
                return 0.0
                
        except Exception:
            return 0.0
    
    def _calculate_recession_probability(self, regime_data: dict) -> float:
        """Estimate recession probability from macro indicators.
        
        Simple heuristic based on:
        - Inverted yield curve
        - High unemployment
        - Wide credit spreads
        
        Args:
            regime_data: Dictionary with macro data
            
        Returns:
            Recession probability (0.0 to 1.0)
        """
        try:
            yield_curve_slope = regime_data.get("yield_curve_slope", 0.0)
            unemployment = regime_data.get("unemployment", {}).get("current", 4.0)
            baa_spread = regime_data.get("baa_spread", {}).get("current", 2.0)
            
            # Simple scoring
            prob = 0.0
            
            # Inverted yield curve (strong recession signal)
            if yield_curve_slope < 0:
                prob += 0.4
            elif yield_curve_slope < 0.5:
                prob += 0.2
            
            # High unemployment
            if unemployment > 6.0:
                prob += 0.3
            elif unemployment > 5.0:
                prob += 0.15
            
            # Wide credit spreads
            if baa_spread > 3.0:
                prob += 0.3
            elif baa_spread > 2.5:
                prob += 0.15
            
            return min(prob, 1.0)
            
        except Exception:
            return 0.0
    
    def get_current_fed_funds_rate(self) -> float:
        """Get current Federal Funds rate.
        
        Returns:
            Current Fed Funds rate (%)
        """
        df = self.fetch_series("fed_funds_rate")
        return float(df["fed_funds_rate"].tail(1)[0])
    
    def get_yield_curve(self) -> Dict[str, float]:
        """Get current yield curve (3M, 2Y, 10Y).
        
        Returns:
            Dictionary with yield rates
        """
        yield_curve = {}
        
        for series in ["treasury_3m", "treasury_2y", "treasury_10y"]:
            try:
                df = self.fetch_series(series)
                yield_curve[series] = float(df[series].tail(1)[0])
            except Exception as e:
                logger.warning(f"Could not fetch {series}: {e}")
                yield_curve[series] = None
        
        return yield_curve
    
    def test_connection(self) -> bool:
        """Test FRED API connection.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Try to fetch Fed Funds rate (always available)
            rate = self.get_current_fed_funds_rate()
            
            logger.info(f"FRED connection test SUCCESS (Fed Funds: {rate:.2f}%)")
            return True
            
        except Exception as e:
            logger.error(f"FRED connection test failed: {e}")
            return False


# Convenience function
def get_macro_regime_data(api_key: Optional[str] = None) -> Dict[str, any]:
    """Get macro regime data from FRED.
    
    Args:
        api_key: FRED API key (or None to use environment variable)
        
    Returns:
        Dictionary with macro data
    """
    adapter = FREDAdapter(api_key=api_key)
    return adapter.fetch_macro_regime_data()


# Example usage
if __name__ == "__main__":
    import sys
    import os
    
    print("Testing FRED Adapter...")
    
    # Check for API key
    api_key = os.getenv("FRED_API_KEY")
    if not api_key:
        print("\n⚠️  FRED API key not found!")
        print("Get a FREE API key from: https://fred.stlouisfed.org/docs/api/api_key.html")
        print("Then set environment variable: export FRED_API_KEY=your_key_here")
        sys.exit(1)
    
    try:
        adapter = FREDAdapter(api_key=api_key)
        
        # Test connection
        print("\n1. Testing connection...")
        if adapter.test_connection():
            print("   ✅ Connection successful")
        else:
            print("   ❌ Connection failed")
            sys.exit(1)
        
        # Fetch key rates
        print("\n2. Fetching current rates...")
        fed_funds = adapter.get_current_fed_funds_rate()
        print(f"   Fed Funds Rate: {fed_funds:.2f}%")
        
        yield_curve = adapter.get_yield_curve()
        print(f"   3-Month Treasury: {yield_curve['treasury_3m']:.2f}%")
        print(f"   2-Year Treasury: {yield_curve['treasury_2y']:.2f}%")
        print(f"   10-Year Treasury: {yield_curve['treasury_10y']:.2f}%")
        
        # Fetch macro regime data
        print("\n3. Fetching macro regime data...")
        regime_data = adapter.fetch_macro_regime_data(lookback_days=90)
        
        print(f"   Yield Curve Slope: {regime_data['yield_curve_slope']:.2f}%")
        if regime_data['yield_curve_slope'] < 0:
            print("   ⚠️  INVERTED YIELD CURVE (recession signal)")
        
        print(f"   Recession Probability: {regime_data['recession_probability']:.1%}")
        
        print(f"   Unemployment: {regime_data['unemployment']['current']:.1f}%")
        print(f"   BAA Spread: {regime_data['baa_spread']['current']:.2f}%")
        
        print("\n✅ FRED Adapter working!")
        print("   You now have FREE macro data for ML regime features.")
        
    except Exception as e:
        print(f"\n❌ Failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
