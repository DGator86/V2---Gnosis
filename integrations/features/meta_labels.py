"""
Meta-Labeling for Trading Signals
Based on: https://github.com/neurotrader888/meta-labeling

Meta-labeling applies machine learning to SIZE bets, not SIDE:
1. Primary model generates directional signals (SIDE: long/short)
2. Meta-model predicts probability of success (SIZE: 0% to 100%)
3. Only take bets when meta-model confidence is high

This improves Sharpe ratio by reducing false positives.

Reference: Advances in Financial Machine Learning (López de Prado, 2018)
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import cross_val_score
from sklearn.metrics import precision_score, recall_score, f1_score


@dataclass
class MetaLabelModel:
    """Container for trained meta-labeling model."""
    
    model: RandomForestClassifier
    """Trained sklearn classifier."""
    
    feature_names: List[str]
    """Names of features used for training."""
    
    feature_importance: Dict[str, float]
    """Feature importance scores."""
    
    cv_score: float
    """Cross-validation F1 score."""
    
    precision: float
    """Precision on training set."""
    
    recall: float
    """Recall on training set."""
    
    threshold: float
    """Probability threshold for positive predictions."""


def create_meta_labels(
    primary_signals: pd.Series,
    returns: pd.Series,
    holding_period: int = 5,
) -> pd.Series:
    """
    Create meta-labels (target variable) from primary signals and outcomes.
    
    Meta-label = 1 if primary signal was correct, 0 otherwise.
    
    Args:
        primary_signals: Series with values {-1, 0, 1} for short/neutral/long
        returns: Forward returns
        holding_period: Bars to hold position
    
    Returns:
        Boolean Series: True if signal was profitable
    
    Example:
        >>> signals = pd.Series([1, 0, -1, 1, 0])  # Long, neutral, short, long, neutral
        >>> returns = pd.Series([0.01, 0.00, -0.02, 0.03, 0.01])
        >>> labels = create_meta_labels(signals, returns.shift(-1), holding_period=1)
        >>> # labels[0] = True (long with +0.01 return)
        >>> # labels[2] = True (short with -0.02 return, i.e., +0.02 for short)
    """
    # Compute forward returns over holding period
    forward_returns = returns.rolling(holding_period).sum().shift(-holding_period)
    
    # Meta-label: signal direction matches return direction
    meta_labels = (primary_signals * forward_returns) > 0
    
    # Only consider time points where we have a signal (non-zero)
    meta_labels[primary_signals == 0] = np.nan
    
    return meta_labels


def train_meta_labels(
    primary_signals: pd.Series,
    outcomes: pd.Series,
    features: pd.DataFrame,
    n_estimators: int = 100,
    max_depth: int = 5,
    min_samples_leaf: int = 50,
    cv_folds: int = 5,
    threshold: float = 0.5,
) -> MetaLabelModel:
    """
    Train meta-labeling model to predict signal quality.
    
    Args:
        primary_signals: Primary model signals {-1, 0, 1}
        outcomes: Binary outcomes (1 = signal was correct, 0 = wrong)
        features: Feature DataFrame (market state, indicators, etc.)
        n_estimators: Number of trees in random forest
        max_depth: Maximum tree depth
        min_samples_leaf: Minimum samples per leaf (reduce overfitting)
        cv_folds: Cross-validation folds
        threshold: Probability threshold for predictions
    
    Returns:
        MetaLabelModel with trained classifier
    
    Example:
        >>> # Generate primary signals
        >>> signals = momentum_strategy(prices)
        >>> 
        >>> # Create meta-labels
        >>> meta_labels = create_meta_labels(signals, returns, holding_period=5)
        >>> 
        >>> # Engineer features
        >>> features = pd.DataFrame({
        >>>     'volatility': returns.rolling(20).std(),
        >>>     'momentum': prices.pct_change(10),
        >>>     'volume_ratio': volume / volume.rolling(20).mean(),
        >>> })
        >>> 
        >>> # Train meta-model
        >>> meta_model = train_meta_labels(signals, meta_labels, features)
        >>> 
        >>> # Apply to new data
        >>> confidence = apply_meta_labels(meta_model, new_features)
        >>> filtered_signals = signals * (confidence > 0.6)
    """
    # Filter to rows with signals
    mask = (primary_signals != 0) & ~outcomes.isna()
    X = features.loc[mask].fillna(0)
    y = outcomes.loc[mask].astype(int)
    
    if len(y) < 30:
        raise ValueError(f"Insufficient samples for training: {len(y)} < 30")
    
    # Train random forest
    clf = RandomForestClassifier(
        n_estimators=n_estimators,
        max_depth=max_depth,
        min_samples_leaf=min_samples_leaf,
        random_state=42,
        n_jobs=-1,
    )
    
    clf.fit(X, y)
    
    # Cross-validation score
    cv_scores = cross_val_score(clf, X, y, cv=cv_folds, scoring='f1')
    cv_score = cv_scores.mean()
    
    # Training metrics
    y_pred = clf.predict(X)
    precision = precision_score(y, y_pred, zero_division=0)
    recall = recall_score(y, y_pred, zero_division=0)
    
    # Feature importance
    feature_importance = dict(zip(X.columns, clf.feature_importances_))
    feature_importance = dict(sorted(
        feature_importance.items(),
        key=lambda x: x[1],
        reverse=True,
    ))
    
    return MetaLabelModel(
        model=clf,
        feature_names=list(X.columns),
        feature_importance=feature_importance,
        cv_score=cv_score,
        precision=precision,
        recall=recall,
        threshold=threshold,
    )


def apply_meta_labels(
    model: MetaLabelModel,
    features: pd.DataFrame,
) -> pd.Series:
    """
    Apply trained meta-labeling model to generate confidence scores.
    
    Args:
        model: Trained MetaLabelModel
        features: Feature DataFrame (must match training features)
    
    Returns:
        Series of confidence scores [0, 1]
    """
    # Ensure features match training
    X = features[model.feature_names].fillna(0)
    
    # Predict probabilities
    proba = model.model.predict_proba(X)[:, 1]
    
    return pd.Series(proba, index=features.index)


def optimize_threshold(
    model: MetaLabelModel,
    primary_signals: pd.Series,
    outcomes: pd.Series,
    features: pd.DataFrame,
    metric: str = 'f1',
) -> float:
    """
    Optimize probability threshold to maximize given metric.
    
    Args:
        model: Trained MetaLabelModel
        primary_signals: Primary signals
        outcomes: True outcomes
        features: Features
        metric: Metric to optimize ('f1', 'precision', 'recall', 'sharpe')
    
    Returns:
        Optimal threshold
    """
    # Get predictions
    mask = (primary_signals != 0) & ~outcomes.isna()
    X = features.loc[mask][model.feature_names].fillna(0)
    y = outcomes.loc[mask].astype(int)
    proba = model.model.predict_proba(X)[:, 1]
    
    # Try different thresholds
    thresholds = np.linspace(0.3, 0.7, 41)
    scores = []
    
    for thresh in thresholds:
        y_pred = (proba >= thresh).astype(int)
        
        if metric == 'f1':
            score = f1_score(y, y_pred, zero_division=0)
        elif metric == 'precision':
            score = precision_score(y, y_pred, zero_division=0)
        elif metric == 'recall':
            score = recall_score(y, y_pred, zero_division=0)
        elif metric == 'sharpe':
            # Approximate Sharpe: win_rate / sqrt(n_bets)
            if y_pred.sum() == 0:
                score = 0
            else:
                win_rate = (y[y_pred == 1] == 1).mean()
                n_bets = y_pred.sum()
                score = win_rate / np.sqrt(n_bets + 1)
        else:
            raise ValueError(f"Unknown metric: {metric}")
        
        scores.append(score)
    
    best_idx = np.argmax(scores)
    return thresholds[best_idx]


def backtest_with_meta_labels(
    primary_signals: pd.Series,
    returns: pd.Series,
    meta_confidence: pd.Series,
    threshold: float = 0.5,
    transaction_cost: float = 0.001,
) -> Dict[str, float]:
    """
    Backtest strategy with meta-label filtering.
    
    Args:
        primary_signals: Primary model signals {-1, 0, 1}
        returns: Actual returns
        meta_confidence: Meta-model confidence scores [0, 1]
        threshold: Minimum confidence to take trade
        transaction_cost: Cost per trade (as fraction)
    
    Returns:
        Dictionary with performance metrics
    """
    # Filter signals by confidence
    filtered_signals = primary_signals.copy()
    filtered_signals[meta_confidence < threshold] = 0
    
    # Compute returns
    primary_returns = primary_signals * returns - np.abs(primary_signals.diff()) * transaction_cost
    filtered_returns = filtered_signals * returns - np.abs(filtered_signals.diff()) * transaction_cost
    
    # Metrics
    def compute_metrics(rets):
        if len(rets) == 0 or rets.std() == 0:
            return {
                'total_return': 0.0,
                'sharpe': 0.0,
                'max_drawdown': 0.0,
                'win_rate': 0.0,
                'n_trades': 0,
            }
        
        cumrets = (1 + rets).cumprod()
        running_max = cumrets.cummax()
        drawdown = (cumrets - running_max) / running_max
        
        n_trades = int(np.abs(rets != 0).sum())
        win_rate = (rets[rets != 0] > 0).mean() if n_trades > 0 else 0.0
        
        return {
            'total_return': cumrets.iloc[-1] - 1.0,
            'sharpe': rets.mean() / (rets.std() + 1e-9) * np.sqrt(252),
            'max_drawdown': drawdown.min(),
            'win_rate': win_rate,
            'n_trades': n_trades,
        }
    
    primary_metrics = compute_metrics(primary_returns)
    filtered_metrics = compute_metrics(filtered_returns)
    
    return {
        'primary': primary_metrics,
        'filtered': filtered_metrics,
        'improvement': {
            'sharpe_diff': filtered_metrics['sharpe'] - primary_metrics['sharpe'],
            'return_diff': filtered_metrics['total_return'] - primary_metrics['total_return'],
            'trade_reduction': 1.0 - filtered_metrics['n_trades'] / max(primary_metrics['n_trades'], 1),
        }
    }


# Example usage
if __name__ == "__main__":
    # Generate synthetic data
    np.random.seed(42)
    n = 500
    dates = pd.date_range('2024-01-01', periods=n, freq='1D')
    
    # Simulate price with trend + noise
    price = 100 * np.exp(np.cumsum(np.random.randn(n) * 0.02 + 0.0005))
    prices = pd.Series(price, index=dates)
    returns = prices.pct_change()
    
    # Simple momentum strategy (primary model)
    momentum = prices.pct_change(20)
    primary_signals = pd.Series(0, index=dates)
    primary_signals[momentum > 0.05] = 1
    primary_signals[momentum < -0.05] = -1
    
    # Create meta-labels
    meta_labels = create_meta_labels(primary_signals, returns, holding_period=5)
    
    # Engineer features
    features = pd.DataFrame({
        'volatility': returns.rolling(20).std(),
        'momentum_10': prices.pct_change(10),
        'momentum_20': prices.pct_change(20),
        'rsi': 100 - (100 / (1 + (returns.rolling(14).apply(lambda x: x[x > 0].sum()) /
                                     -returns.rolling(14).apply(lambda x: x[x < 0].sum())))),
    }, index=dates).fillna(0)
    
    # Train meta-model
    print("Training meta-labeling model...")
    meta_model = train_meta_labels(
        primary_signals,
        meta_labels,
        features,
        n_estimators=100,
        max_depth=5,
    )
    
    print(f"\nModel Performance:")
    print(f"  CV F1 Score: {meta_model.cv_score:.4f}")
    print(f"  Precision: {meta_model.precision:.4f}")
    print(f"  Recall: {meta_model.recall:.4f}")
    
    print(f"\nTop 3 Features:")
    for i, (feat, imp) in enumerate(list(meta_model.feature_importance.items())[:3], 1):
        print(f"  {i}. {feat}: {imp:.4f}")
    
    # Apply to data
    confidence = apply_meta_labels(meta_model, features)
    
    # Backtest
    print("\nBacktesting with meta-labels...")
    results = backtest_with_meta_labels(
        primary_signals,
        returns,
        confidence,
        threshold=0.5,
    )
    
    print(f"\nPrimary Strategy:")
    print(f"  Return: {results['primary']['total_return']:.2%}")
    print(f"  Sharpe: {results['primary']['sharpe']:.2f}")
    print(f"  Max DD: {results['primary']['max_drawdown']:.2%}")
    print(f"  Trades: {results['primary']['n_trades']}")
    
    print(f"\nFiltered Strategy (Meta-Labels):")
    print(f"  Return: {results['filtered']['total_return']:.2%}")
    print(f"  Sharpe: {results['filtered']['sharpe']:.2f}")
    print(f"  Max DD: {results['filtered']['max_drawdown']:.2%}")
    print(f"  Trades: {results['filtered']['n_trades']}")
    
    print(f"\nImprovement:")
    print(f"  Sharpe Diff: {results['improvement']['sharpe_diff']:+.2f}")
    print(f"  Return Diff: {results['improvement']['return_diff']:+.2%}")
    print(f"  Trade Reduction: {results['improvement']['trade_reduction']:.1%}")
