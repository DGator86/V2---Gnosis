"""
Hedge/Fields engine
Computes dealer positioning, greek exposures, and flow dynamics
Uses Polars for performance when available
"""
from typing import Dict, Any, List
from datetime import datetime
from schemas import EngineOutput
from ..orchestration.logger import get_logger

logger = get_logger(__name__)

# Try to import polars for performance
try:
    import polars as pl
    POLARS_AVAILABLE = True
    logger.info("Polars available for hedge engine")
except ImportError:
    POLARS_AVAILABLE = False
    logger.info("Polars not available, using fallback implementation")


class HedgeEngine:
    """
    Engine for dealer hedge positioning and greek analysis
    Computes gamma pressure, vanna exposure, charm decay, etc.
    """
    
    def __init__(self, polars_threads: int = 4):
        self.polars_threads = polars_threads
        logger.info(f"Hedge engine initialized (polars={POLARS_AVAILABLE}, threads={polars_threads})")
    
    def _compute_with_polars(self, options: List[Dict[str, Any]]) -> Dict[str, float]:
        """Fast computation using Polars"""
        if not options:
            return self._empty_features()
        
        # Create DataFrame
        df = pl.DataFrame(options)
        
        # Compute aggregated greeks
        gamma_pressure = float(df.get_column("gamma").sum()) if "gamma" in df.columns else 0.0
        delta_net = float(df.get_column("delta").sum()) if "delta" in df.columns else 0.0
        vega_notional = float(df.get_column("vega").sum()) if "vega" in df.columns else 0.0
        
        # Vanna approximation (gamma * underlying movement sensitivity)
        vanna_pressure = gamma_pressure * 0.1
        
        # Charm approximation (gamma decay over time)
        charm_pressure = gamma_pressure * 0.05
        
        # Call/put gamma imbalance
        if "type" in df.columns and "gamma" in df.columns:
            call_gamma = float(
                df.filter(pl.col("type") == "call")
                .get_column("gamma")
                .sum()
            )
            put_gamma = float(
                df.filter(pl.col("type") == "put")
                .get_column("gamma")
                .sum()
            )
            gamma_imbalance = (call_gamma - put_gamma) / (call_gamma + put_gamma + 1e-9)
        else:
            gamma_imbalance = 0.0
        
        # Strike concentration (gamma at specific strikes)
        if "strike" in df.columns and "gamma" in df.columns:
            strike_gamma = (
                df.groupby("strike")
                .agg(pl.col("gamma").sum().alias("total_gamma"))
                .sort("total_gamma", descending=True)
            )
            max_strike_gamma = float(strike_gamma.head(1).get_column("total_gamma")[0]) if len(strike_gamma) > 0 else 0.0
        else:
            max_strike_gamma = 0.0
        
        return {
            "gamma_pressure": gamma_pressure,
            "vanna_pressure": vanna_pressure,
            "charm_pressure": charm_pressure,
            "vega_notional": vega_notional,
            "delta_imbalance": delta_net,
            "gamma_imbalance": gamma_imbalance,
            "max_strike_gamma": max_strike_gamma
        }
    
    def _compute_fallback(self, options: List[Dict[str, Any]]) -> Dict[str, float]:
        """Fallback computation without Polars"""
        if not options:
            return self._empty_features()
        
        gamma_pressure = sum(opt.get("gamma", 0.0) for opt in options)
        delta_net = sum(opt.get("delta", 0.0) for opt in options)
        vega_notional = sum(opt.get("vega", 0.0) for opt in options)
        
        vanna_pressure = gamma_pressure * 0.1
        charm_pressure = gamma_pressure * 0.05
        
        # Call/put split
        call_gamma = sum(opt.get("gamma", 0.0) for opt in options if opt.get("type") == "call")
        put_gamma = sum(opt.get("gamma", 0.0) for opt in options if opt.get("type") == "put")
        gamma_imbalance = (call_gamma - put_gamma) / (call_gamma + put_gamma + 1e-9)
        
        # Strike concentration
        strike_gamma = {}
        for opt in options:
            strike = opt.get("strike", 0)
            gamma = opt.get("gamma", 0.0)
            strike_gamma[strike] = strike_gamma.get(strike, 0.0) + gamma
        
        max_strike_gamma = max(strike_gamma.values()) if strike_gamma else 0.0
        
        return {
            "gamma_pressure": gamma_pressure,
            "vanna_pressure": vanna_pressure,
            "charm_pressure": charm_pressure,
            "vega_notional": vega_notional,
            "delta_imbalance": delta_net,
            "gamma_imbalance": gamma_imbalance,
            "max_strike_gamma": max_strike_gamma
        }
    
    def _empty_features(self) -> Dict[str, float]:
        """Return empty features"""
        return {
            "gamma_pressure": 0.0,
            "vanna_pressure": 0.0,
            "charm_pressure": 0.0,
            "vega_notional": 0.0,
            "delta_imbalance": 0.0,
            "gamma_imbalance": 0.0,
            "max_strike_gamma": 0.0
        }
    
    def run(self, options: List[Dict[str, Any]]) -> EngineOutput:
        """
        Main entry point: compute hedge features from options chain
        
        Args:
            options: List of option dicts with greeks
        
        Returns:
            EngineOutput with hedge features
        """
        start_time = datetime.now()
        
        # Choose computation method
        if POLARS_AVAILABLE:
            features = self._compute_with_polars(options)
        else:
            features = self._compute_fallback(options)
        
        latency_ms = (datetime.now() - start_time).total_seconds() * 1000
        
        logger.debug(f"Hedge engine computed {len(features)} features in {latency_ms:.2f}ms")
        
        return EngineOutput(
            kind="hedge",
            features=features,
            metadata={
                "n_options": len(options),
                "latency_ms": latency_ms,
                "method": "polars" if POLARS_AVAILABLE else "fallback"
            },
            timestamp=datetime.now().timestamp(),
            confidence=1.0 if len(options) > 0 else 0.0
        )
