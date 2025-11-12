"""
Sentiment Engine Integration Bridge
Connects neurotrader888 features to the sentiment analysis engine.
"""

from typing import Dict, Optional, List
import pandas as pd
import numpy as np
from datetime import datetime
import yaml
from pathlib import Path

from integrations.features import (
    compute_vsa, VSASignals,
    fit_hawkes_volatility, compute_hawkes_features, HawkesParams,
    compute_permutation_entropy, PermutationEntropyResult,
    compute_hurst_exponent, FractalMetrics,
    detect_changepoints, ChangepointResult,
    detect_bursts, BurstResult,
)
from integrations.utils.io import ensure_timeseries


class EnhancedSentimentMetrics:
    """Enhanced metrics combining sentiment and technical features."""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize enhanced metrics calculator.
        
        Args:
            config_path: Path to features.yaml config file
        """
        if config_path is None:
            config_path = Path(__file__).parent / 'config' / 'features.yaml'
        
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        # Cache for expensive computations
        self._cache = {}
        self._cache_timestamp = {}
    
    def compute_vsa_metrics(
        self,
        ohlcv: pd.DataFrame,
        ticker: str,
    ) -> Dict[str, float]:
        """
        Compute VSA metrics for a ticker.
        
        Args:
            ohlcv: OHLCV DataFrame
            ticker: Ticker symbol
        
        Returns:
            Dictionary of VSA metrics
        """
        if not self.config['phase1']['vsa']['enabled']:
            return {}
        
        # Check cache
        cache_key = f"vsa_{ticker}_{len(ohlcv)}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        try:
            signals = compute_vsa(
                ohlcv,
                window=self.config['phase1']['vsa']['window'],
                climax_vol_threshold=self.config['phase1']['vsa']['climax_vol_threshold'],
                climax_spread_threshold=self.config['phase1']['vsa']['climax_spread_threshold'],
            )
            
            # Extract recent values
            metrics = {
                'vsa_score': float(signals.vsa_score.iloc[-1]),
                'volume_ratio': float(signals.volume_ratio.iloc[-1]),
                'spread_ratio': float(signals.spread_ratio.iloc[-1]),
                'is_climax': bool(signals.climax_bar.iloc[-1]),
                'is_no_supply': bool(signals.no_supply.iloc[-1]),
                'is_no_demand': bool(signals.no_demand.iloc[-1]),
                'effort_vs_result': float(signals.effort_vs_result.iloc[-1]),
            }
            
            self._cache[cache_key] = metrics
            return metrics
            
        except Exception as e:
            print(f"VSA computation failed for {ticker}: {e}")
            return {}
    
    def compute_hawkes_metrics(
        self,
        returns: pd.Series,
        ticker: str,
    ) -> Dict[str, float]:
        """
        Compute Hawkes process metrics.
        
        Args:
            returns: Returns series
            ticker: Ticker symbol
        
        Returns:
            Dictionary of Hawkes metrics
        """
        if not self.config['phase1']['hawkes']['enabled']:
            return {}
        
        cache_key = f"hawkes_{ticker}_{len(returns)}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        try:
            params = fit_hawkes_volatility(
                returns,
                threshold_percentile=self.config['phase1']['hawkes']['threshold_percentile'],
                max_iter=self.config['phase1']['hawkes']['max_iter'],
                compute_intensity=True,
            )
            
            if not params.convergence:
                return {}
            
            metrics = {
                'hawkes_mu': float(params.mu),
                'hawkes_alpha': float(params.alpha),
                'hawkes_beta': float(params.beta),
                'hawkes_branching_ratio': float(params.branching_ratio),
                'hawkes_is_clustering': bool(params.branching_ratio > self.config['phase1']['hawkes']['branching_threshold']),
            }
            
            # Add intensity metrics if available
            if params.lambda_history is not None:
                features = compute_hawkes_features(returns, params, lookback=20)
                metrics['hawkes_lambda'] = float(features['lambda'].iloc[-1])
                metrics['hawkes_jump_prob'] = float(features['jump_prob'].iloc[-1])
                metrics['hawkes_excitement'] = float(features['excitement'].iloc[-1])
            
            self._cache[cache_key] = metrics
            return metrics
            
        except Exception as e:
            print(f"Hawkes computation failed for {ticker}: {e}")
            return {}
    
    def compute_complexity_metrics(
        self,
        returns: pd.Series,
        ticker: str,
    ) -> Dict[str, float]:
        """
        Compute complexity metrics (permutation entropy).
        
        Args:
            returns: Returns series
            ticker: Ticker symbol
        
        Returns:
            Dictionary of complexity metrics
        """
        if not self.config['phase2']['permutation_entropy']['enabled']:
            return {}
        
        cache_key = f"complexity_{ticker}_{len(returns)}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        try:
            result = compute_permutation_entropy(
                returns,
                order=self.config['phase2']['permutation_entropy']['order'],
                delay=self.config['phase2']['permutation_entropy']['delay'],
                window=self.config['phase2']['permutation_entropy']['window'],
            )
            
            metrics = {
                'perm_entropy': float(result.entropy.iloc[-1]),
                'complexity': float(result.complexity.iloc[-1]),
                'is_complex': bool(result.entropy.iloc[-1] > 0.7),
                'is_predictable': bool(result.entropy.iloc[-1] < 0.3),
            }
            
            self._cache[cache_key] = metrics
            return metrics
            
        except Exception as e:
            print(f"Complexity computation failed for {ticker}: {e}")
            return {}
    
    def compute_regime_metrics(
        self,
        prices: pd.Series,
        ticker: str,
    ) -> Dict[str, float]:
        """
        Compute regime detection metrics (Hurst, changepoints).
        
        Args:
            prices: Price series
            ticker: Ticker symbol
        
        Returns:
            Dictionary of regime metrics
        """
        metrics = {}
        
        # Hurst exponent
        if self.config['phase3']['fractal_dimension']['enabled']:
            cache_key = f"hurst_{ticker}_{len(prices)}"
            if cache_key not in self._cache:
                try:
                    result = compute_hurst_exponent(
                        prices,
                        window=self.config['phase3']['fractal_dimension']['window'],
                        max_lag=self.config['phase3']['fractal_dimension']['max_lag'],
                        method=self.config['phase3']['fractal_dimension']['method'],
                    )
                    
                    self._cache[cache_key] = {
                        'hurst_exponent': float(result.hurst_exponent.iloc[-1]),
                        'fractal_dimension': float(result.fractal_dimension.iloc[-1]),
                        'regime': str(result.regime.iloc[-1]),
                        'is_trending': bool(result.regime.iloc[-1] == 'trending'),
                        'is_mean_reverting': bool(result.regime.iloc[-1] == 'mean_reverting'),
                    }
                except Exception as e:
                    print(f"Hurst computation failed for {ticker}: {e}")
                    self._cache[cache_key] = {}
            
            metrics.update(self._cache[cache_key])
        
        # Changepoint detection
        if self.config['phase3']['icss_changepoints']['enabled']:
            cache_key = f"changepoint_{ticker}_{len(prices)}"
            if cache_key not in self._cache:
                try:
                    returns = prices.pct_change().dropna()
                    result = detect_changepoints(
                        returns,
                        alpha=self.config['phase3']['icss_changepoints']['alpha'],
                        min_regime_length=self.config['phase3']['icss_changepoints']['min_regime_length'],
                    )
                    
                    # Check if we're near a changepoint
                    recent_changepoints = [cp for cp in result.changepoints if cp > len(returns) - 20]
                    
                    self._cache[cache_key] = {
                        'regime_id': int(result.regimes.iloc[-1]),
                        'n_changepoints': len(result.changepoints) - 2,
                        'is_regime_change': bool(len(recent_changepoints) > 0),
                    }
                except Exception as e:
                    print(f"Changepoint computation failed for {ticker}: {e}")
                    self._cache[cache_key] = {}
            
            metrics.update(self._cache[cache_key])
        
        return metrics
    
    def compute_activity_metrics(
        self,
        volume: pd.Series,
        ticker: str,
    ) -> Dict[str, float]:
        """
        Compute activity burst metrics.
        
        Args:
            volume: Volume series
            ticker: Ticker symbol
        
        Returns:
            Dictionary of activity metrics
        """
        if not self.config['phase3']['burst_detection']['enabled']:
            return {}
        
        cache_key = f"burst_{ticker}_{len(volume)}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        try:
            result = detect_bursts(
                volume,
                window=self.config['phase3']['burst_detection']['window'],
                threshold=self.config['phase3']['burst_detection']['threshold'],
                min_duration=self.config['phase3']['burst_detection']['min_duration'],
            )
            
            metrics = {
                'burst_score': float(result.burst_score.iloc[-1]),
                'is_burst': bool(result.is_burst.iloc[-1]),
                'burst_duration': int(result.burst_duration.iloc[-1]),
            }
            
            self._cache[cache_key] = metrics
            return metrics
            
        except Exception as e:
            print(f"Burst detection failed for {ticker}: {e}")
            return {}
    
    def get_all_metrics(
        self,
        ticker: str,
        ohlcv: pd.DataFrame,
    ) -> Dict[str, float]:
        """
        Compute all enabled metrics for a ticker.
        
        Args:
            ticker: Ticker symbol
            ohlcv: OHLCV DataFrame with columns [open, high, low, close, volume]
        
        Returns:
            Dictionary of all computed metrics
        """
        all_metrics = {}
        
        # Ensure proper format
        ohlcv = ensure_timeseries(ohlcv)
        
        # VSA metrics
        vsa_metrics = self.compute_vsa_metrics(ohlcv, ticker)
        all_metrics.update({f'vsa_{k}': v for k, v in vsa_metrics.items()})
        
        # Hawkes metrics
        returns = ohlcv['close'].pct_change().dropna()
        hawkes_metrics = self.compute_hawkes_metrics(returns, ticker)
        all_metrics.update({f'hawkes_{k}': v for k, v in hawkes_metrics.items()})
        
        # Complexity metrics
        complexity_metrics = self.compute_complexity_metrics(returns, ticker)
        all_metrics.update({f'complexity_{k}': v for k, v in complexity_metrics.items()})
        
        # Regime metrics
        regime_metrics = self.compute_regime_metrics(ohlcv['close'], ticker)
        all_metrics.update({f'regime_{k}': v for k, v in regime_metrics.items()})
        
        # Activity metrics
        activity_metrics = self.compute_activity_metrics(ohlcv['volume'], ticker)
        all_metrics.update({f'activity_{k}': v for k, v in activity_metrics.items()})
        
        return all_metrics
    
    def clear_cache(self, ticker: Optional[str] = None):
        """Clear cached computations."""
        if ticker is None:
            self._cache.clear()
            self._cache_timestamp.clear()
        else:
            # Clear only for specific ticker
            keys_to_delete = [k for k in self._cache.keys() if ticker in k]
            for key in keys_to_delete:
                del self._cache[key]
                if key in self._cache_timestamp:
                    del self._cache_timestamp[key]


# Example usage
if __name__ == "__main__":
    # Generate sample data
    np.random.seed(42)
    n = 300
    dates = pd.date_range('2024-01-01', periods=n, freq='1h')
    
    price = 100 + np.cumsum(np.random.randn(n) * 0.5)
    ohlcv = pd.DataFrame({
        'open': price,
        'high': price * 1.01,
        'low': price * 0.99,
        'close': price,
        'volume': np.abs(np.random.randn(n) * 1000000 + 5000000),
    }, index=dates)
    
    # Initialize enhanced metrics
    calculator = EnhancedSentimentMetrics()
    
    # Compute all metrics
    metrics = calculator.get_all_metrics('AAPL', ohlcv)
    
    print("Enhanced Sentiment Metrics for AAPL:")
    print("=" * 60)
    for key, value in sorted(metrics.items()):
        if isinstance(value, float):
            print(f"  {key}: {value:.4f}")
        else:
            print(f"  {key}: {value}")
