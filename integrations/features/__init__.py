"""
Feature extraction modules from neurotrader888 repositories.

This package contains implementations of advanced trading features:
- VSA: Volume Spread Analysis
- Hawkes: Volatility clustering via Hawkes processes
- Meta-Labeling: Confidence scoring for primary signals
- Microstructure: Order flow features
- Visibility Graphs: Time series network topology
- Permutation Entropy: Complexity analysis
- Fractal Dimension: Hurst exponent
- ICSS: Changepoint detection
- kPCA: Dimensionality reduction
- Burst Detection: Activity spike identification
- MSM: Markov Switching Multifractal
- Event Discretization: Microstructure events
"""

from .vsa import compute_vsa, VSASignals
from .vol_hawkes import fit_hawkes_volatility, HawkesParams
from .meta_labels import train_meta_labels, apply_meta_labels, MetaLabelModel
from .microstructure import compute_order_flow, MicrostructureFeatures
from .visibility_graph import compute_visibility_graph, VisibilityGraphMetrics
from .permutation_entropy import compute_permutation_entropy, PermutationEntropyResult
from .fractal_dimension import compute_hurst_exponent, FractalMetrics
from .icss_changepoints import detect_changepoints, ChangepointResult
from .kpca import fit_kpca, transform_kpca, KPCAModel
from .burst_detection import detect_bursts, BurstResult
from .event_discretization import discretize_events, EventFeatures

__all__ = [
    # VSA
    "compute_vsa",
    "VSASignals",
    # Hawkes
    "fit_hawkes_volatility",
    "HawkesParams",
    # Meta-Labeling
    "train_meta_labels",
    "apply_meta_labels",
    "MetaLabelModel",
    # Microstructure
    "compute_order_flow",
    "MicrostructureFeatures",
    # Visibility Graphs
    "compute_visibility_graph",
    "VisibilityGraphMetrics",
    # Permutation Entropy
    "compute_permutation_entropy",
    "PermutationEntropyResult",
    # Fractal Dimension
    "compute_hurst_exponent",
    "FractalMetrics",
    # ICSS Changepoints
    "detect_changepoints",
    "ChangepointResult",
    # kPCA
    "fit_kpca",
    "transform_kpca",
    "KPCAModel",
    # Burst Detection
    "detect_bursts",
    "BurstResult",
    # Event Discretization
    "discretize_events",
    "EventFeatures",
]
