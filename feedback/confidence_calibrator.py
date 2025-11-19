"""
Confidence Calibration with Online Logistic Regression

Calibrates Composer Agent confidence scores using realized trade outcomes.
Uses sklearn's SGDClassifier for incremental online learning.

Author: Super Gnosis AI Developer
Created: 2025-11-19
"""

from __future__ import annotations
import numpy as np
from typing import Dict, List, Tuple, Optional
from collections import deque

try:
    from sklearn.linear_model import SGDClassifier
    from sklearn.preprocessing import StandardScaler
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    print("⚠️  sklearn not available, confidence calibration disabled")


class ConfidenceCalibrator:
    """
    Online logistic regression for confidence calibration.
    
    Features:
    - Raw composer confidence
    - Elasticity
    - IV rank
    - Dealer gamma sign
    - Movement energy
    - Energy asymmetry
    
    Target: 1 if trade won, 0 if lost
    """
    
    def __init__(
        self,
        min_samples: int = 50,
        retrain_every_trades: int = 10
    ):
        """
        Initialize calibrator.
        
        Args:
            min_samples: Minimum trades before calibration starts
            retrain_every_trades: Retrain model every N trades
        """
        if not SKLEARN_AVAILABLE:
            self.enabled = False
            return
        
        self.enabled = True
        self.min_samples = min_samples
        self.retrain_every_trades = retrain_every_trades
        
        # SGD Logistic Regression for online learning
        self.model = SGDClassifier(
            loss='log_loss',  # Logistic regression
            penalty='l2',
            alpha=0.0001,
            max_iter=1,  # Online learning (one sample at a time)
            warm_start=True,  # Keep previous weights
            random_state=42
        )
        
        # Feature scaler
        self.scaler = StandardScaler()
        
        # Training data buffer
        self.X_buffer: deque = deque(maxlen=1000)
        self.y_buffer: deque = deque(maxlen=1000)
        
        # Model trained flag
        self.is_trained = False
        
        # Trades since last retrain
        self.trades_since_retrain = 0
        
        # Calibration curve for dashboard (confidence_bin -> actual_win_rate)
        self.calibration_curve: Dict[int, Tuple[float, int]] = {}
    
    def add_trade(
        self,
        raw_confidence: float,
        hedge_snapshot: Dict[str, float],
        won: bool,
        iv_rank: Optional[float] = None
    ):
        """
        Add a closed trade for training.
        
        Args:
            raw_confidence: Original composer confidence (0-1)
            hedge_snapshot: Hedge Engine state
            won: Whether trade was profitable
            iv_rank: IV rank (0-100), optional
        """
        if not self.enabled:
            return
        
        # Extract features
        features = self._extract_features(raw_confidence, hedge_snapshot, iv_rank)
        label = 1 if won else 0
        
        # Add to buffer
        self.X_buffer.append(features)
        self.y_buffer.append(label)
        
        # Update calibration curve
        confidence_bin = int(raw_confidence * 10)  # 0-10 bins
        if confidence_bin not in self.calibration_curve:
            self.calibration_curve[confidence_bin] = (0.0, 0)
        
        total_wins, count = self.calibration_curve[confidence_bin]
        total_wins += (1 if won else 0)
        count += 1
        self.calibration_curve[confidence_bin] = (total_wins, count)
        
        self.trades_since_retrain += 1
        
        # Online update
        if self.is_trained:
            try:
                self.model.partial_fit([features], [label])
            except Exception as e:
                print(f"⚠️  Calibrator partial_fit error: {e}")
        
        # Periodic full retrain
        if self.trades_since_retrain >= self.retrain_every_trades:
            self.retrain()
    
    def retrain(self):
        """
        Full retrain on buffered data.
        """
        if not self.enabled or len(self.X_buffer) < self.min_samples:
            return
        
        try:
            X = np.array(list(self.X_buffer))
            y = np.array(list(self.y_buffer))
            
            # Fit scaler
            self.scaler.fit(X)
            X_scaled = self.scaler.transform(X)
            
            # Train model
            if not self.is_trained:
                # Initial fit
                self.model.fit(X_scaled, y)
                self.is_trained = True
            else:
                # Incremental fit
                self.model.partial_fit(X_scaled, y)
            
            self.trades_since_retrain = 0
            
        except Exception as e:
            print(f"⚠️  Calibrator retrain error: {e}")
    
    def calibrate(
        self,
        raw_confidence: float,
        hedge_snapshot: Dict[str, float],
        iv_rank: Optional[float] = None
    ) -> float:
        """
        Calibrate a confidence score.
        
        Args:
            raw_confidence: Original composer confidence (0-1)
            hedge_snapshot: Hedge Engine state
            iv_rank: IV rank (0-100), optional
        
        Returns:
            Calibrated confidence (0-1)
        """
        if not self.enabled or not self.is_trained:
            # Return raw confidence if not calibrated yet
            return raw_confidence
        
        try:
            features = self._extract_features(raw_confidence, hedge_snapshot, iv_rank)
            X_scaled = self.scaler.transform([features])
            
            # Get calibrated probability
            calibrated_prob = self.model.predict_proba(X_scaled)[0][1]
            
            # Ensure in valid range
            calibrated_prob = np.clip(calibrated_prob, 0.0, 1.0)
            
            return float(calibrated_prob)
            
        except Exception as e:
            print(f"⚠️  Calibration error: {e}")
            return raw_confidence
    
    def _extract_features(
        self,
        raw_confidence: float,
        hedge_snapshot: Dict[str, float],
        iv_rank: Optional[float]
    ) -> np.ndarray:
        """
        Extract feature vector.
        
        Args:
            raw_confidence: Original confidence
            hedge_snapshot: Hedge Engine state
            iv_rank: IV rank
        
        Returns:
            Feature array
        """
        features = [
            raw_confidence,
            hedge_snapshot.get('elasticity', 1.0),
            hedge_snapshot.get('movement_energy', 0.0),
            hedge_snapshot.get('energy_asymmetry', 0.0),
            hedge_snapshot.get('dealer_gamma_sign', 0.0),
            hedge_snapshot.get('net_pressure', 0.0),
            iv_rank if iv_rank is not None else 50.0
        ]
        
        return np.array(features, dtype=np.float32)
    
    def get_calibration_curve(self) -> List[Tuple[float, float, int]]:
        """
        Get calibration curve for dashboard.
        
        Returns:
            List of (predicted_confidence, actual_win_rate, count) tuples
        """
        curve = []
        for bin_id in range(11):  # 0-10 bins
            if bin_id in self.calibration_curve:
                total_wins, count = self.calibration_curve[bin_id]
                predicted = bin_id / 10.0
                actual = total_wins / max(1, count)
                curve.append((predicted, actual, count))
            else:
                curve.append((bin_id / 10.0, 0.0, 0))
        
        return curve
    
    def get_stats(self) -> Dict:
        """
        Get calibrator statistics for dashboard.
        
        Returns:
            Dict with stats
        """
        return {
            'is_trained': self.is_trained,
            'samples': len(self.X_buffer),
            'min_samples': self.min_samples,
            'trades_since_retrain': self.trades_since_retrain,
            'retrain_every': self.retrain_every_trades,
            'calibration_curve': self.get_calibration_curve()
        }
    
    def to_dict(self) -> Dict:
        """
        Serialize state for persistence.
        
        Returns:
            Dict with state
        """
        if not self.enabled:
            return {'enabled': False}
        
        return {
            'enabled': True,
            'min_samples': self.min_samples,
            'retrain_every_trades': self.retrain_every_trades,
            'X_buffer': [x.tolist() for x in self.X_buffer],
            'y_buffer': list(self.y_buffer),
            'is_trained': self.is_trained,
            'trades_since_retrain': self.trades_since_retrain,
            'calibration_curve': {
                str(k): v for k, v in self.calibration_curve.items()
            }
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ConfidenceCalibrator':
        """
        Deserialize from persistence.
        
        Args:
            data: Dict with state
        
        Returns:
            Restored ConfidenceCalibrator instance
        """
        if not data.get('enabled', False) or not SKLEARN_AVAILABLE:
            instance = cls()
            instance.enabled = False
            return instance
        
        instance = cls(
            min_samples=data.get('min_samples', 50),
            retrain_every_trades=data.get('retrain_every_trades', 10)
        )
        
        # Restore buffers
        X_buffer_data = data.get('X_buffer', [])
        y_buffer_data = data.get('y_buffer', [])
        
        instance.X_buffer = deque(
            [np.array(x, dtype=np.float32) for x in X_buffer_data],
            maxlen=1000
        )
        instance.y_buffer = deque(y_buffer_data, maxlen=1000)
        
        instance.is_trained = data.get('is_trained', False)
        instance.trades_since_retrain = data.get('trades_since_retrain', 0)
        
        # Restore calibration curve
        calibration_data = data.get('calibration_curve', {})
        instance.calibration_curve = {
            int(k): tuple(v) for k, v in calibration_data.items()
        }
        
        # Retrain model from buffer
        if instance.is_trained and len(instance.X_buffer) >= instance.min_samples:
            instance.retrain()
        
        return instance
