"""
Feature Independence Testing
Identifies redundant and correlated features to avoid overfitting.

Checks:
- Pearson correlation (linear relationships)
- Spearman correlation (monotonic relationships)
- Mutual information (non-linear dependencies)
- VIF (Variance Inflation Factor) for multicollinearity
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from scipy import stats
from scipy.stats import spearmanr
from sklearn.feature_selection import mutual_info_regression


@dataclass
class IndependenceReport:
    """Feature independence analysis report."""
    
    correlation_matrix: pd.DataFrame
    """Pearson correlation matrix."""
    
    spearman_matrix: pd.DataFrame
    """Spearman rank correlation matrix."""
    
    high_correlations: List[Tuple[str, str, float]]
    """List of (feat1, feat2, correlation) for highly correlated pairs."""
    
    vif_scores: Dict[str, float]
    """Variance Inflation Factor for each feature."""
    
    redundant_features: List[str]
    """Features identified as redundant."""
    
    mutual_info: Dict[str, float]
    """Mutual information with target variable."""


def check_feature_independence(
    features: pd.DataFrame,
    target: pd.Series = None,
    correlation_threshold: float = 0.85,
    vif_threshold: float = 10.0,
) -> IndependenceReport:
    """
    Analyze feature independence and identify redundancies.
    
    Args:
        features: Feature DataFrame
        target: Target variable (optional, for mutual information)
        correlation_threshold: Threshold for identifying high correlation
        vif_threshold: Threshold for identifying multicollinearity
    
    Returns:
        IndependenceReport with detailed analysis
    """
    # Pearson correlation
    corr_matrix = features.corr()
    
    # Spearman correlation (rank-based, catches non-linear monotonic)
    spearman_matrix = features.corr(method='spearman')
    
    # Find highly correlated pairs
    high_corr = []
    for i in range(len(corr_matrix.columns)):
        for j in range(i+1, len(corr_matrix.columns)):
            corr = abs(corr_matrix.iloc[i, j])
            if corr > correlation_threshold:
                high_corr.append((
                    corr_matrix.columns[i],
                    corr_matrix.columns[j],
                    corr
                ))
    
    high_corr.sort(key=lambda x: x[2], reverse=True)
    
    # VIF scores
    vif_scores = {}
    if len(features.columns) > 1:
        for col in features.columns:
            try:
                X = features.drop(columns=[col]).fillna(0)
                y = features[col].fillna(0)
                
                # Compute R²
                from sklearn.linear_model import LinearRegression
                model = LinearRegression()
                model.fit(X, y)
                r_squared = model.score(X, y)
                
                # VIF = 1 / (1 - R²)
                if r_squared < 0.999:
                    vif = 1 / (1 - r_squared)
                else:
                    vif = np.inf
                
                vif_scores[col] = vif
            except:
                vif_scores[col] = np.nan
    
    # Identify redundant features
    redundant = []
    checked = set()
    
    for feat1, feat2, corr in high_corr:
        if feat1 not in checked and feat2 not in checked:
            # Keep feature with lower VIF (less correlated with others)
            vif1 = vif_scores.get(feat1, np.inf)
            vif2 = vif_scores.get(feat2, np.inf)
            
            if vif1 > vif2:
                redundant.append(feat1)
                checked.add(feat1)
            else:
                redundant.append(feat2)
                checked.add(feat2)
    
    # Add features with VIF > threshold
    for feat, vif in vif_scores.items():
        if vif > vif_threshold and feat not in redundant:
            redundant.append(feat)
    
    # Mutual information with target
    mi_scores = {}
    if target is not None:
        mask = ~target.isna()
        X = features.loc[mask].fillna(0)
        y = target.loc[mask]
        
        if len(y) > 10:
            mi = mutual_info_regression(X, y, random_state=42)
            mi_scores = dict(zip(features.columns, mi))
    
    return IndependenceReport(
        correlation_matrix=corr_matrix,
        spearman_matrix=spearman_matrix,
        high_correlations=high_corr,
        vif_scores=vif_scores,
        redundant_features=redundant,
        mutual_info=mi_scores,
    )


# Example
if __name__ == "__main__":
    np.random.seed(42)
    n = 200
    
    # Create features with known correlations
    f1 = np.random.randn(n)
    f2 = f1 + np.random.randn(n) * 0.3  # Highly correlated with f1
    f3 = np.random.randn(n)
    f4 = f1 + f3 + np.random.randn(n) * 0.2  # Multicollinear
    f5 = np.random.randn(n)  # Independent
    
    features = pd.DataFrame({
        'feature1': f1,
        'feature2': f2,
        'feature3': f3,
        'feature4': f4,
        'feature5': f5,
    })
    
    target = f1 + f3 + np.random.randn(n) * 0.5
    
    report = check_feature_independence(features, pd.Series(target))
    
    print("High Correlations:")
    for f1, f2, corr in report.high_correlations:
        print(f"  {f1} <-> {f2}: {corr:.3f}")
    
    print(f"\nRedundant Features: {report.redundant_features}")
    
    print("\nVIF Scores:")
    for feat, vif in sorted(report.vif_scores.items(), key=lambda x: x[1], reverse=True):
        print(f"  {feat}: {vif:.2f}")
