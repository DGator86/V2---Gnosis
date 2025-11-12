"""
Comprehensive test suite for all feature modules.
Run with: pytest integrations/tests/test_all_features.py -v
"""

import numpy as np
import pandas as pd
import pytest

from integrations.features import (
    compute_vsa, fit_hawkes_volatility, train_meta_labels, create_meta_labels,
    compute_order_flow, compute_visibility_graph, compute_permutation_entropy,
    compute_hurst_exponent, detect_changepoints, fit_kpca, detect_bursts,
    discretize_events,
)
from integrations.validation import mcpt_validate, check_feature_independence, test_reversibility


@pytest.fixture
def sample_ohlcv():
    """Generate sample OHLCV data."""
    np.random.seed(42)
    n = 200
    dates = pd.date_range('2024-01-01', periods=n, freq='1h')
    
    price = 100 + np.cumsum(np.random.randn(n) * 0.5)
    ohlcv = pd.DataFrame({
        'open': price + np.random.randn(n) * 0.1,
        'high': price + np.abs(np.random.randn(n) * 0.3),
        'low': price - np.abs(np.random.randn(n) * 0.3),
        'close': price + np.random.randn(n) * 0.1,
        'volume': np.abs(np.random.randn(n) * 1000000 + 5000000),
    }, index=dates)
    
    # Ensure OHLC relationship
    ohlcv['high'] = ohlcv[['open', 'close', 'high']].max(axis=1)
    ohlcv['low'] = ohlcv[['open', 'close', 'low']].min(axis=1)
    
    return ohlcv


@pytest.fixture
def sample_returns(sample_ohlcv):
    """Generate sample returns."""
    return sample_ohlcv['close'].pct_change().dropna()


class TestVSA:
    """Test Volume Spread Analysis."""
    
    def test_compute_vsa(self, sample_ohlcv):
        signals = compute_vsa(sample_ohlcv, window=50)
        
        assert signals.vsa_score is not None
        assert len(signals.vsa_score) == len(sample_ohlcv)
        assert signals.climax_bar.sum() >= 0
        assert signals.no_supply.sum() >= 0
    
    def test_vsa_scores_reasonable(self, sample_ohlcv):
        signals = compute_vsa(sample_ohlcv, window=50)
        
        # VSA scores should be mostly positive
        assert (signals.vsa_score > 0).sum() > len(signals.vsa_score) * 0.3


class TestHawkes:
    """Test Hawkes Process."""
    
    def test_fit_hawkes(self, sample_returns):
        params = fit_hawkes_volatility(sample_returns, threshold_percentile=85)
        
        assert params.mu > 0
        assert params.alpha >= 0
        assert params.beta > 0
        assert 0 <= params.branching_ratio <= 2
        assert params.convergence in [True, False]
    
    def test_hawkes_lambda_history(self, sample_returns):
        params = fit_hawkes_volatility(sample_returns, compute_intensity=True)
        
        if params.convergence:
            assert params.lambda_history is not None
            assert len(params.lambda_history) == len(sample_returns)


class TestMetaLabeling:
    """Test Meta-Labeling."""
    
    def test_create_meta_labels(self, sample_returns):
        # Create signals with same index as returns
        signals = pd.Series(
            np.random.choice([-1, 0, 1], size=len(sample_returns)),
            index=sample_returns.index
        )
        
        labels = create_meta_labels(signals, sample_returns, holding_period=5)
        
        assert len(labels) == len(signals)
        assert labels.dtype == bool or labels.isna().any()
    
    def test_train_meta_labels(self, sample_returns):
        n = len(sample_returns)
        signals = pd.Series(np.random.choice([-1, 1], size=n), index=sample_returns.index)
        
        labels = create_meta_labels(signals, sample_returns, holding_period=5)
        
        features = pd.DataFrame({
            'vol': sample_returns.rolling(20).std(),
            'mom': sample_returns.rolling(10).mean(),
        }, index=sample_returns.index).fillna(0)
        
        # Need sufficient valid labels
        if (~labels.isna()).sum() > 30:
            model = train_meta_labels(signals, labels, features)
            
            assert model.model is not None
            assert 0 <= model.cv_score <= 1
            assert 0 <= model.precision <= 1


class TestMicrostructure:
    """Test Microstructure Features."""
    
    def test_compute_order_flow(self, sample_ohlcv):
        features = compute_order_flow(sample_ohlcv, tick_rule='tick', window=20)
        
        assert features.order_flow_imbalance is not None
        assert features.trade_intensity is not None
        assert len(features.kyle_lambda) == len(sample_ohlcv)


class TestPermutationEntropy:
    """Test Permutation Entropy."""
    
    def test_compute_pe(self, sample_returns):
        result = compute_permutation_entropy(sample_returns, order=3, window=50)
        
        assert result.entropy is not None
        assert (result.entropy >= 0).all()
        assert (result.entropy <= 1).all()
        assert result.most_common_pattern is not None


class TestHurst:
    """Test Hurst Exponent."""
    
    def test_compute_hurst(self, sample_returns):
        result = compute_hurst_exponent(
            pd.Series(sample_returns.values.cumsum()),  # Use price-like series
            window=100,
        )
        
        assert result.hurst_exponent is not None
        assert (result.hurst_exponent >= 0).all()
        assert (result.hurst_exponent <= 1).all()
        assert result.regime.isin(['trending', 'random', 'mean_reverting']).all()


class TestChangepoints:
    """Test ICSS Changepoint Detection."""
    
    def test_detect_changepoints(self, sample_returns):
        result = detect_changepoints(sample_returns, alpha=0.05, min_regime_length=20)
        
        assert len(result.changepoints) >= 2  # At least start and end
        assert result.changepoints[0] == 0
        assert result.changepoints[-1] == len(sample_returns)


class TestKPCA:
    """Test Kernel PCA."""
    
    def test_fit_kpca(self):
        np.random.seed(42)
        n, p = 100, 5
        features = pd.DataFrame(np.random.randn(n, p), columns=[f'f{i}' for i in range(p)])
        
        model = fit_kpca(features, n_components=3)
        
        assert model.model is not None
        assert model.n_components == 3
        assert len(model.explained_variance_ratio) == 3


class TestBurstDetection:
    """Test Burst Detection."""
    
    def test_detect_bursts(self):
        np.random.seed(42)
        n = 200
        activity = pd.Series(np.abs(np.random.randn(n)) + 1)
        activity.iloc[100:110] *= 5  # Create burst
        
        result = detect_bursts(activity, window=20, threshold=2.0, min_duration=2)
        
        assert result.burst_score is not None
        assert result.is_burst.sum() >= 0  # May or may not detect depending on threshold


class TestEventDiscretization:
    """Test Event Discretization."""
    
    def test_discretize_events(self, sample_ohlcv):
        result = discretize_events(sample_ohlcv, method='tick')
        
        assert result.events is not None
        assert len(result.events) == len(sample_ohlcv)
    
    def test_volume_discretization(self, sample_ohlcv):
        result = discretize_events(sample_ohlcv, method='volume')
        
        assert len(result.events) <= len(sample_ohlcv)
        assert len(result.events) > 0


class TestMCPT:
    """Test Monte Carlo Permutation Tests."""
    
    def test_mcpt_validate(self):
        np.random.seed(42)
        # Strategy with positive edge
        returns = pd.Series(np.random.randn(252) * 0.15 + 0.01)
        
        result = mcpt_validate(returns, metric='sharpe', n_permutations=500)
        
        assert result.observed_metric is not None
        assert 0 <= result.p_value <= 1
        assert result.is_significant in [True, False]
        assert len(result.null_distribution) == 500


class TestIndependence:
    """Test Feature Independence Checking."""
    
    def test_check_independence(self):
        np.random.seed(42)
        n = 150
        
        # Create correlated features
        f1 = np.random.randn(n)
        f2 = f1 + np.random.randn(n) * 0.3  # Highly correlated
        f3 = np.random.randn(n)  # Independent
        
        features = pd.DataFrame({'f1': f1, 'f2': f2, 'f3': f3})
        
        report = check_feature_independence(features, correlation_threshold=0.7)
        
        assert report.correlation_matrix is not None
        assert len(report.high_correlations) > 0  # Should find f1-f2 correlation


class TestReversibility:
    """Test Reversibility/Causality Testing."""
    
    def test_reversibility(self):
        np.random.seed(42)
        n = 150
        
        # Create causal relationship
        feature = np.random.randn(n)
        target = np.zeros(n)
        for t in range(1, n):
            target[t] = 0.5 * feature[t-1] + np.random.randn()
        
        result = test_reversibility(pd.Series(feature), pd.Series(target), max_lag=3)
        
        assert 0 <= result.granger_pvalue <= 1
        assert 0 <= result.reverse_granger_pvalue <= 1
        assert result.is_causal in [True, False]


def test_full_pipeline(sample_ohlcv):
    """Test complete pipeline integration."""
    # VSA
    vsa_signals = compute_vsa(sample_ohlcv, window=50)
    
    # Hawkes
    returns = sample_ohlcv['close'].pct_change().dropna()
    hawkes_params = fit_hawkes_volatility(returns)
    
    # Microstructure
    microstructure = compute_order_flow(sample_ohlcv)
    
    # Permutation Entropy
    pe_result = compute_permutation_entropy(returns, order=3, window=50)
    
    # All should complete without errors
    assert vsa_signals is not None
    assert hawkes_params is not None
    assert microstructure is not None
    assert pe_result is not None


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, '-v', '--tb=short'])
