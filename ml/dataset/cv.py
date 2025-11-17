"""Purged K-Fold cross-validation to prevent leakage in time series."""

from __future__ import annotations

from typing import Iterator, Optional, Tuple
import numpy as np
from sklearn.model_selection import KFold


class PurgedKFold:
    """Purged K-Fold cross-validation for time series data.
    
    Prevents leakage by:
    1. Purging samples close to validation set from training
    2. Adding embargo period after validation set
    
    Based on "Advances in Financial Machine Learning" by Marcos López de Prado.
    """
    
    def __init__(
        self,
        n_splits: int = 5,
        embargo_bars: int = 10,
        purge_bars: int = 5,
    ):
        """Initialize purged k-fold.
        
        Args:
            n_splits: Number of folds
            embargo_bars: Number of bars to embargo after validation set
            purge_bars: Number of bars to purge before validation set
        """
        self.n_splits = n_splits
        self.embargo_bars = embargo_bars
        self.purge_bars = purge_bars
        self.kfold = KFold(n_splits=n_splits, shuffle=False)
    
    def split(
        self,
        X: np.ndarray,
        y: Optional[np.ndarray] = None,
        groups: Optional[np.ndarray] = None,
    ) -> Iterator[Tuple[np.ndarray, np.ndarray]]:
        """Generate purged train/validation indices.
        
        Args:
            X: Feature matrix
            y: Target array (optional)
            groups: Group labels (optional)
            
        Yields:
            Tuple of (train_indices, valid_indices)
        """
        n_samples = len(X)
        indices = np.arange(n_samples)
        
        for train_idx, valid_idx in self.kfold.split(X):
            # Apply purging: remove samples close to validation set from training
            train_idx_purged = self._purge_train_indices(
                train_idx, valid_idx, n_samples
            )
            
            # Apply embargo: remove samples after validation set from training
            train_idx_embargoed = self._embargo_train_indices(
                train_idx_purged, valid_idx, n_samples
            )
            
            yield train_idx_embargoed, valid_idx
    
    def _purge_train_indices(
        self,
        train_idx: np.ndarray,
        valid_idx: np.ndarray,
        n_samples: int,
    ) -> np.ndarray:
        """Purge training samples too close to validation set.
        
        Args:
            train_idx: Training indices
            valid_idx: Validation indices
            n_samples: Total number of samples
            
        Returns:
            Purged training indices
        """
        if self.purge_bars == 0:
            return train_idx
        
        # Get validation boundaries
        valid_start = valid_idx.min()
        valid_end = valid_idx.max()
        
        # Remove training samples within purge_bars of validation set
        purge_start = max(0, valid_start - self.purge_bars)
        purge_end = min(n_samples - 1, valid_end + self.purge_bars)
        
        # Keep only training samples outside purge zone
        mask = (train_idx < purge_start) | (train_idx > purge_end)
        
        return train_idx[mask]
    
    def _embargo_train_indices(
        self,
        train_idx: np.ndarray,
        valid_idx: np.ndarray,
        n_samples: int,
    ) -> np.ndarray:
        """Apply embargo period after validation set.
        
        Args:
            train_idx: Training indices
            valid_idx: Validation indices
            n_samples: Total number of samples
            
        Returns:
            Training indices with embargo applied
        """
        if self.embargo_bars == 0:
            return train_idx
        
        # Get validation end
        valid_end = valid_idx.max()
        
        # Remove training samples in embargo period
        embargo_end = min(n_samples - 1, valid_end + self.embargo_bars)
        
        # Keep only training samples before validation or after embargo
        mask = (train_idx < valid_idx.min()) | (train_idx > embargo_end)
        
        return train_idx[mask]
    
    def get_n_splits(
        self,
        X: Optional[np.ndarray] = None,
        y: Optional[np.ndarray] = None,
        groups: Optional[np.ndarray] = None,
    ) -> int:
        """Get number of splits.
        
        Returns:
            Number of splits
        """
        return self.n_splits


def embargo_samples(
    train_idx: np.ndarray,
    valid_idx: np.ndarray,
    test_idx: np.ndarray,
    embargo_bars: int = 10,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Apply embargo to train/valid/test splits.
    
    Removes samples from training set that are too close to validation/test sets.
    
    Args:
        train_idx: Training indices
        valid_idx: Validation indices
        test_idx: Test indices
        embargo_bars: Number of bars to embargo
        
    Returns:
        Tuple of (embargoed_train_idx, valid_idx, test_idx)
    """
    if embargo_bars == 0:
        return train_idx, valid_idx, test_idx
    
    # Find boundaries
    valid_start = valid_idx.min() if len(valid_idx) > 0 else float('inf')
    test_start = test_idx.min() if len(test_idx) > 0 else float('inf')
    
    # Remove training samples within embargo period
    mask = (train_idx < (valid_start - embargo_bars)) | \
           ((train_idx > (valid_idx.max() + embargo_bars)) & 
            (train_idx < (test_start - embargo_bars)))
    
    embargoed_train_idx = train_idx[mask]
    
    return embargoed_train_idx, valid_idx, test_idx


def compute_sample_uniqueness(
    timestamps: np.ndarray,
    lookback_window: int = 20,
) -> np.ndarray:
    """Compute sample uniqueness for weighting.
    
    Samples that overlap with many other samples (in time) receive lower weights.
    This reduces overfitting to overlapping samples.
    
    Args:
        timestamps: Array of timestamps
        lookback_window: Window size for computing overlaps
        
    Returns:
        Array of uniqueness weights (0 to 1)
    """
    n = len(timestamps)
    uniqueness = np.ones(n)
    
    for i in range(n):
        # Count how many samples are within the lookback window
        window_start = timestamps[i] - lookback_window
        window_end = timestamps[i] + lookback_window
        
        overlaps = ((timestamps >= window_start) & (timestamps <= window_end)).sum()
        
        # Uniqueness is inverse of overlap count
        uniqueness[i] = 1.0 / max(1, overlaps)
    
    # Normalize to [0, 1]
    uniqueness = uniqueness / uniqueness.max()
    
    return uniqueness
