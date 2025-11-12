"""
Complete Workflow Example
Demonstrates end-to-end usage of all integrated features.
"""

import numpy as np
import pandas as pd
import yaml
from pathlib import Path

# Import all features
from integrations.features import (
    compute_vsa, fit_hawkes_volatility, compute_hawkes_features,
    train_meta_labels, create_meta_labels, apply_meta_labels,
    compute_order_flow, compute_permutation_entropy,
    compute_hurst_exponent, detect_changepoints,
    detect_bursts,
)
from integrations.validation import mcpt_validate, check_feature_independence
from integrations.utils.io import ensure_timeseries


def load_config():
    """Load feature configuration."""
    config_path = Path(__file__).parent.parent / 'config' / 'features.yaml'
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def generate_sample_data(n=500):
    """Generate realistic sample OHLCV data."""
    np.random.seed(42)
    dates = pd.date_range('2024-01-01', periods=n, freq='1h')
    
    # Simulate price with GARCH-like volatility
    returns = np.zeros(n)
    sigma = np.zeros(n)
    sigma[0] = 0.01
    
    for t in range(1, n):
        sigma[t] = np.sqrt(0.00001 + 0.1 * returns[t-1]**2 + 0.85 * sigma[t-1]**2)
        returns[t] = sigma[t] * np.random.randn()
    
    price = 100 * np.exp(np.cumsum(returns))
    
    ohlcv = pd.DataFrame({
        'open': price,
        'high': price * (1 + np.abs(np.random.randn(n) * 0.005)),
        'low': price * (1 - np.abs(np.random.randn(n) * 0.005)),
        'close': price,
        'volume': np.abs(np.random.randn(n) * 1000000 + 5000000),
    }, index=dates)
    
    # Ensure OHLC validity
    ohlcv['high'] = ohlcv[['open', 'close', 'high']].max(axis=1)
    ohlcv['low'] = ohlcv[['open', 'close', 'low']].min(axis=1)
    
    return ohlcv


def extract_all_features(ohlcv, config):
    """Extract all enabled features from OHLCV data."""
    print("=" * 60)
    print("FEATURE EXTRACTION PIPELINE")
    print("=" * 60)
    
    features = {}
    returns = ohlcv['close'].pct_change().dropna()
    
    # Phase 1: Core Features
    print("\n[Phase 1: Core Features]")
    
    if config['phase1']['vsa']['enabled']:
        print("  Computing VSA signals...")
        vsa_signals = compute_vsa(ohlcv, window=config['phase1']['vsa']['window'])
        features['vsa_score'] = vsa_signals.vsa_score
        features['climax_bar'] = vsa_signals.climax_bar.astype(int)
        features['no_supply'] = vsa_signals.no_supply.astype(int)
        print(f"    ✓ VSA: {vsa_signals.climax_bar.sum()} climax bars detected")
    
    if config['phase1']['hawkes']['enabled']:
        print("  Computing Hawkes intensity...")
        hawkes_params = fit_hawkes_volatility(returns, compute_intensity=True)
        if hawkes_params.convergence and hawkes_params.lambda_history is not None:
            hawkes_features = compute_hawkes_features(returns, hawkes_params, lookback=20)
            features['hawkes_lambda'] = hawkes_features['lambda']
            features['hawkes_jump_prob'] = hawkes_features['jump_prob']
            features['hawkes_clustering'] = hawkes_features['high_clustering']
            print(f"    ✓ Hawkes: branching ratio = {hawkes_params.branching_ratio:.3f}")
        else:
            print(f"    ⚠ Hawkes: convergence failed")
    
    # Phase 2: Advanced Features
    print("\n[Phase 2: Advanced Features]")
    
    if config['phase2']['microstructure']['enabled']:
        print("  Computing microstructure features...")
        micro = compute_order_flow(ohlcv, window=config['phase2']['microstructure']['window'])
        features['order_flow_imbalance'] = micro.order_flow_imbalance
        features['kyle_lambda'] = micro.kyle_lambda
        print(f"    ✓ Microstructure: mean OFI = {micro.order_flow_imbalance.mean():.0f}")
    
    if config['phase2']['permutation_entropy']['enabled']:
        print("  Computing permutation entropy...")
        pe_result = compute_permutation_entropy(
            returns,
            order=config['phase2']['permutation_entropy']['order'],
            window=config['phase2']['permutation_entropy']['window'],
        )
        features['perm_entropy'] = pe_result.entropy
        features['complexity'] = pe_result.complexity
        print(f"    ✓ Perm Entropy: mean = {pe_result.entropy.mean():.3f}")
    
    # Phase 3: Research Features
    print("\n[Phase 3: Research Features]")
    
    if config['phase3']['fractal_dimension']['enabled']:
        print("  Computing Hurst exponent...")
        hurst_result = compute_hurst_exponent(
            ohlcv['close'],
            window=config['phase3']['fractal_dimension']['window'],
        )
        features['hurst_exponent'] = hurst_result.hurst_exponent
        features['regime_trending'] = (hurst_result.regime == 'trending').astype(int)
        features['regime_mean_reverting'] = (hurst_result.regime == 'mean_reverting').astype(int)
        print(f"    ✓ Hurst: mean = {hurst_result.hurst_exponent.mean():.3f}")
    
    if config['phase3']['icss_changepoints']['enabled']:
        print("  Detecting changepoints...")
        cp_result = detect_changepoints(
            returns,
            alpha=config['phase3']['icss_changepoints']['alpha'],
        )
        features['regime_id'] = cp_result.regimes
        print(f"    ✓ Changepoints: {len(cp_result.changepoints) - 2} detected")
    
    if config['phase3']['burst_detection']['enabled']:
        print("  Detecting bursts...")
        burst_result = detect_bursts(
            ohlcv['volume'],
            window=config['phase3']['burst_detection']['window'],
        )
        features['burst_score'] = burst_result.burst_score
        features['is_burst'] = burst_result.is_burst.astype(int)
        print(f"    ✓ Bursts: {burst_result.is_burst.sum()} detected")
    
    # Combine into DataFrame
    feature_df = pd.DataFrame(features)
    feature_df = ensure_timeseries(feature_df)
    
    return feature_df


def validate_features(feature_df, strategy_returns, config):
    """Validate feature quality."""
    print("\n" + "=" * 60)
    print("FEATURE VALIDATION")
    print("=" * 60)
    
    # Independence check
    if config['validation']['run_independence_check']:
        print("\n[Independence Check]")
        report = check_feature_independence(
            feature_df,
            correlation_threshold=config['validation']['correlation_threshold'],
        )
        
        print(f"  High correlations found: {len(report.high_correlations)}")
        for f1, f2, corr in report.high_correlations[:3]:
            print(f"    {f1} <-> {f2}: {corr:.3f}")
        
        if report.redundant_features:
            print(f"  Redundant features: {report.redundant_features}")
    
    # Strategy validation with MCPT
    if config['validation']['run_mcpt_on_features'] and strategy_returns is not None:
        print("\n[Strategy Validation (MCPT)]")
        result = mcpt_validate(
            strategy_returns,
            metric='sharpe',
            n_permutations=500,
        )
        
        print(f"  Observed Sharpe: {result.observed_metric:.2f}")
        print(f"  P-value: {result.p_value:.4f}")
        print(f"  Significant: {result.is_significant}")
        
        if result.is_significant:
            print("  ✅ PASS: Strategy shows significant skill")
        else:
            print("  ❌ FAIL: Performance could be due to luck")


def build_trading_strategy(ohlcv, feature_df):
    """Build example trading strategy using features."""
    print("\n" + "=" * 60)
    print("TRADING STRATEGY CONSTRUCTION")
    print("=" * 60)
    
    returns = ohlcv['close'].pct_change()
    
    # Simple multi-factor strategy
    signals = pd.Series(0, index=feature_df.index)
    
    # Condition 1: VSA no supply + trending regime
    if 'no_supply' in feature_df.columns and 'regime_trending' in feature_df.columns:
        long_condition = (
            (feature_df['no_supply'] == 1) &
            (feature_df['regime_trending'] == 1)
        )
        signals[long_condition] = 1
        print(f"  Long signals (VSA + Hurst): {long_condition.sum()}")
    
    # Condition 2: High Hawkes clustering + burst
    if 'hawkes_clustering' in feature_df.columns and 'is_burst' in feature_df.columns:
        volatility_warning = (
            (feature_df['hawkes_clustering'] == 1) &
            (feature_df['is_burst'] == 1)
        )
        signals[volatility_warning] = 0  # Stay out during high volatility
        print(f"  Volatility warnings: {volatility_warning.sum()}")
    
    # Condition 3: Mean reversion setup
    if 'regime_mean_reverting' in feature_df.columns and 'hurst_exponent' in feature_df.columns:
        mean_revert_condition = (
            (feature_df['regime_mean_reverting'] == 1) &
            (feature_df['hurst_exponent'] < 0.4)
        )
        # Could add mean reversion logic here
        print(f"  Mean reversion opportunities: {mean_revert_condition.sum()}")
    
    # Compute strategy returns
    strategy_returns = signals.shift(1) * returns
    strategy_returns = strategy_returns.dropna()
    
    # Performance metrics
    if len(strategy_returns) > 0 and strategy_returns.std() > 0:
        total_return = (1 + strategy_returns).prod() - 1
        sharpe = strategy_returns.mean() / strategy_returns.std() * np.sqrt(252)
        n_trades = (signals.diff() != 0).sum()
        
        print(f"\n  Strategy Performance:")
        print(f"    Total Return: {total_return:.2%}")
        print(f"    Sharpe Ratio: {sharpe:.2f}")
        print(f"    Number of Trades: {n_trades}")
    
    return signals, strategy_returns


def main():
    """Run complete workflow."""
    print("\n" + "=" * 80)
    print("GNOSIS INTEGRATION FRAMEWORK - COMPLETE WORKFLOW")
    print("=" * 80)
    
    # Load configuration
    config = load_config()
    print(f"\nConfiguration loaded: version {config['version']}")
    
    # Generate sample data
    print("\nGenerating sample OHLCV data...")
    ohlcv = generate_sample_data(n=500)
    print(f"  Generated {len(ohlcv)} bars")
    
    # Extract features
    feature_df = extract_all_features(ohlcv, config)
    print(f"\nExtracted {len(feature_df.columns)} features")
    print(f"Feature names: {list(feature_df.columns)}")
    
    # Build strategy
    signals, strategy_returns = build_trading_strategy(ohlcv, feature_df)
    
    # Validate
    validate_features(feature_df, strategy_returns, config)
    
    print("\n" + "=" * 80)
    print("WORKFLOW COMPLETE")
    print("=" * 80)
    
    return feature_df, signals, strategy_returns


if __name__ == "__main__":
    feature_df, signals, strategy_returns = main()
