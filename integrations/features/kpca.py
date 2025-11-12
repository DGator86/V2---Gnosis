"""
Kernel PCA for Dimensionality Reduction
Based on: https://github.com/neurotrader888/kPCA

Non-linear dimensionality reduction using kernel trick.
"""

from dataclasses import dataclass
from typing import Optional
import numpy as np
import pandas as pd
from sklearn.decomposition import KernelPCA as SklearnKPCA


@dataclass
class KPCAModel:
    """Trained Kernel PCA model."""
    
    model: SklearnKPCA
    explained_variance_ratio: np.ndarray
    feature_names: list
    n_components: int


def fit_kpca(
    features: pd.DataFrame,
    n_components: int = 5,
    kernel: str = 'rbf',
    gamma: Optional[float] = None,
) -> KPCAModel:
    """Fit Kernel PCA model."""
    X = features.fillna(0).values
    
    kpca = SklearnKPCA(
        n_components=n_components,
        kernel=kernel,
        gamma=gamma,
        fit_inverse_transform=True,
    )
    
    kpca.fit(X)
    
    # Approximate explained variance
    X_transformed = kpca.transform(X)
    var_ratio = np.var(X_transformed, axis=0) / np.var(X, axis=0).sum()
    
    return KPCAModel(
        model=kpca,
        explained_variance_ratio=var_ratio,
        feature_names=list(features.columns),
        n_components=n_components,
    )


def transform_kpca(model: KPCAModel, features: pd.DataFrame) -> pd.DataFrame:
    """Transform features using fitted Kernel PCA."""
    X = features[model.feature_names].fillna(0).values
    X_transformed = model.model.transform(X)
    
    return pd.DataFrame(
        X_transformed,
        index=features.index,
        columns=[f'kPC{i+1}' for i in range(model.n_components)],
    )


if __name__ == "__main__":
    np.random.seed(42)
    
    n, p = 200, 10
    X = np.random.randn(n, p)
    features = pd.DataFrame(X, columns=[f'f{i}' for i in range(p)])
    
    model = fit_kpca(features, n_components=3)
    transformed = transform_kpca(model, features)
    
    print(f"Explained variance: {model.explained_variance_ratio}")
    print(f"Transformed shape: {transformed.shape}")
