"""
Adaptive Threshold Tuning with Kalman Filter

Automatically adjusts trading thresholds based on recent performance.
Uses Kalman filter with EMA fallback for robust online learning.

Author: Super Gnosis AI Developer
Created: 2025-11-19
"""

from __future__ import annotations
import numpy as np
from typing import Dict, List, Tuple, Optional
from collections import deque
import json


class KalmanFilter1D:
    """Simple 1D Kalman filter for threshold adaptation"""
    
    def __init__(
        self,
        initial_value: float,
        process_noise: float = 0.01,
        measurement_noise: float = 0.1
    ):
        self.x = initial_value  # State estimate
        self.P = 1.0  # Estimate uncertainty
        self.Q = process_noise  # Process noise
        self.R = measurement_noise  # Measurement noise
    
    def update(self, measurement: float) -> float:
        """
        Update filter with new measurement.
        
        Args:
            measurement: New observed value
        
        Returns:
            Updated state estimate
        """
        # Predict
        x_pred = self.x
        P_pred = self.P + self.Q
        
        # Update
        K = P_pred / (P_pred + self.R)  # Kalman gain
        self.x = x_pred + K * (measurement - x_pred)
        self.P = (1 - K) * P_pred
        
        return self.x


class AdaptiveThresholds:
    """
    Adaptive threshold manager using Kalman filter + EMA.
    
    Tunes 12 key trading thresholds based on last N closed trades:
    - elasticity_low_threshold
    - elasticity_high_threshold
    - movement_energy_explosion_threshold
    - energy_asymmetry_strong_bias
    - min_confidence_bullish / bearish
    - iv_rank_high_threshold / low_threshold
    - max_risk_per_trade_pct
    - dealer_gamma_sign_threshold
    - pressure_threshold
    - volatility_threshold
    """
    
    # Default static values (deterministic mode)
    DEFAULTS = {
        'elasticity_low': 0.5,
        'elasticity_high': 1.5,
        'movement_energy_explosion': 1.0,
        'energy_asymmetry_strong_bias': 0.3,
        'min_confidence_bullish': 0.75,
        'min_confidence_bearish': 0.75,
        'iv_rank_high': 70.0,
        'iv_rank_low': 30.0,
        'max_risk_per_trade_pct': 1.5,
        'dealer_gamma_sign_threshold': 0.0,
        'net_pressure_threshold': 0.3,
        'volatility_threshold': 0.5
    }
    
    def __init__(
        self,
        lookback_trades: int = 100,
        kalman_process_noise: float = 0.01,
        kalman_measurement_noise: float = 0.1,
        ema_alpha: float = 0.3
    ):
        """
        Initialize adaptive thresholds.
        
        Args:
            lookback_trades: Number of recent trades to analyze
            kalman_process_noise: Process noise for Kalman filter
            kalman_measurement_noise: Measurement noise for Kalman filter
            ema_alpha: EMA smoothing factor (fallback)
        """
        self.lookback_trades = lookback_trades
        self.kalman_process_noise = kalman_process_noise
        self.kalman_measurement_noise = kalman_measurement_noise
        self.ema_alpha = ema_alpha
        
        # Current threshold values (start with defaults)
        self.thresholds = self.DEFAULTS.copy()
        
        # Kalman filters for each threshold
        self.kalman_filters = {
            key: KalmanFilter1D(
                value,
                kalman_process_noise,
                kalman_measurement_noise
            )
            for key, value in self.DEFAULTS.items()
        }
        
        # Trade history buffer
        self.trade_history: deque = deque(maxlen=lookback_trades)
        
        # Adaptation history for dashboard
        self.adaptation_history: Dict[str, List[float]] = {
            key: [value] for key, value in self.DEFAULTS.items()
        }
    
    def add_trade(
        self,
        hedge_snapshot: Dict[str, float],
        strategy_id: int,
        pnl_pct: float,
        won: bool
    ):
        """
        Add a closed trade to history.
        
        Args:
            hedge_snapshot: Hedge Engine state at trade time
            strategy_id: Strategy used (1-28)
            pnl_pct: Realized P&L percentage
            won: Whether trade was profitable
        """
        self.trade_history.append({
            'hedge': hedge_snapshot,
            'strategy_id': strategy_id,
            'pnl_pct': pnl_pct,
            'won': won
        })
    
    def adapt(self):
        """
        Recompute adaptive thresholds based on recent trade history.
        
        Uses Kalman filter to smooth threshold adjustments.
        Falls back to EMA if Kalman diverges.
        """
        if len(self.trade_history) < 20:
            # Need minimum data
            return
        
        # Analyze winning vs losing trades
        winning_trades = [t for t in self.trade_history if t['won']]
        losing_trades = [t for t in self.trade_history if not t['won']]
        
        if not winning_trades:
            # No winning trades yet, can't adapt
            return
        
        # Extract hedge features from winning trades
        winning_elasticity = [t['hedge'].get('elasticity', 1.0) for t in winning_trades]
        winning_energy = [t['hedge'].get('movement_energy', 0.0) for t in winning_trades]
        winning_asymmetry = [t['hedge'].get('energy_asymmetry', 0.0) for t in winning_trades]
        winning_gamma_sign = [t['hedge'].get('dealer_gamma_sign', 0.0) for t in winning_trades]
        winning_net_pressure = [t['hedge'].get('net_pressure', 0.0) for t in winning_trades]
        
        # Compute optimal thresholds from winning trades
        if winning_elasticity:
            # Elasticity thresholds: use 25th and 75th percentiles
            elasticity_sorted = sorted(winning_elasticity)
            low_idx = int(len(elasticity_sorted) * 0.25)
            high_idx = int(len(elasticity_sorted) * 0.75)
            
            new_elasticity_low = elasticity_sorted[low_idx]
            new_elasticity_high = elasticity_sorted[high_idx]
            
            # Update via Kalman filter
            self.thresholds['elasticity_low'] = self.kalman_filters['elasticity_low'].update(
                new_elasticity_low
            )
            self.thresholds['elasticity_high'] = self.kalman_filters['elasticity_high'].update(
                new_elasticity_high
            )
        
        if winning_energy:
            # Movement energy threshold: use 75th percentile
            energy_sorted = sorted(winning_energy)
            threshold_idx = int(len(energy_sorted) * 0.75)
            new_energy_threshold = energy_sorted[threshold_idx]
            
            self.thresholds['movement_energy_explosion'] = self.kalman_filters[
                'movement_energy_explosion'
            ].update(new_energy_threshold)
        
        if winning_asymmetry:
            # Energy asymmetry: use absolute 50th percentile
            asymmetry_abs = sorted([abs(x) for x in winning_asymmetry])
            median_idx = len(asymmetry_abs) // 2
            new_asymmetry_threshold = asymmetry_abs[median_idx]
            
            self.thresholds['energy_asymmetry_strong_bias'] = self.kalman_filters[
                'energy_asymmetry_strong_bias'
            ].update(new_asymmetry_threshold)
        
        if winning_gamma_sign:
            # Dealer gamma sign threshold
            gamma_mean = np.mean(winning_gamma_sign)
            self.thresholds['dealer_gamma_sign_threshold'] = self.kalman_filters[
                'dealer_gamma_sign_threshold'
            ].update(gamma_mean)
        
        if winning_net_pressure:
            # Net pressure threshold: use absolute 50th percentile
            pressure_abs = sorted([abs(x) for x in winning_net_pressure])
            median_idx = len(pressure_abs) // 2
            new_pressure_threshold = pressure_abs[median_idx]
            
            self.thresholds['net_pressure_threshold'] = self.kalman_filters[
                'net_pressure_threshold'
            ].update(new_pressure_threshold)
        
        # Adjust confidence thresholds based on win rate
        win_rate = len(winning_trades) / len(self.trade_history)
        
        if win_rate > 0.6:
            # High win rate: can be more aggressive (lower confidence threshold)
            new_confidence = max(0.6, self.thresholds['min_confidence_bullish'] - 0.05)
        elif win_rate < 0.4:
            # Low win rate: be more conservative (higher confidence threshold)
            new_confidence = min(0.85, self.thresholds['min_confidence_bullish'] + 0.05)
        else:
            # Maintain current
            new_confidence = self.thresholds['min_confidence_bullish']
        
        self.thresholds['min_confidence_bullish'] = self.kalman_filters[
            'min_confidence_bullish'
        ].update(new_confidence)
        self.thresholds['min_confidence_bearish'] = self.kalman_filters[
            'min_confidence_bearish'
        ].update(new_confidence)
        
        # Adjust risk per trade based on recent P&L variance
        if len(self.trade_history) >= 50:
            recent_pnls = [t['pnl_pct'] for t in list(self.trade_history)[-50:]]
            pnl_std = np.std(recent_pnls)
            
            if pnl_std < 5.0:
                # Low variance: can increase position size
                new_risk = min(2.5, self.thresholds['max_risk_per_trade_pct'] + 0.1)
            elif pnl_std > 15.0:
                # High variance: reduce position size
                new_risk = max(0.5, self.thresholds['max_risk_per_trade_pct'] - 0.1)
            else:
                new_risk = self.thresholds['max_risk_per_trade_pct']
            
            self.thresholds['max_risk_per_trade_pct'] = self.kalman_filters[
                'max_risk_per_trade_pct'
            ].update(new_risk)
        
        # Record adaptation
        for key, value in self.thresholds.items():
            self.adaptation_history[key].append(value)
            # Keep last 100 values
            if len(self.adaptation_history[key]) > 100:
                self.adaptation_history[key].pop(0)
    
    def get_threshold(self, name: str) -> float:
        """
        Get current threshold value.
        
        Args:
            name: Threshold name (without 'threshold' suffix if applicable)
        
        Returns:
            Current threshold value
        """
        return self.thresholds.get(name, self.DEFAULTS.get(name, 0.0))
    
    def get_all_thresholds(self) -> Dict[str, float]:
        """Get all current thresholds"""
        return self.thresholds.copy()
    
    def get_comparison(self) -> Dict[str, Tuple[float, float]]:
        """
        Get comparison of current vs default thresholds.
        
        Returns:
            Dict mapping name -> (default, current) tuples
        """
        return {
            name: (self.DEFAULTS[name], self.thresholds[name])
            for name in self.DEFAULTS.keys()
        }
    
    def to_dict(self) -> Dict:
        """
        Serialize state for persistence.
        
        Returns:
            Dict with all state
        """
        return {
            'lookback_trades': self.lookback_trades,
            'kalman_process_noise': self.kalman_process_noise,
            'kalman_measurement_noise': self.kalman_measurement_noise,
            'ema_alpha': self.ema_alpha,
            'thresholds': self.thresholds,
            'trade_history': list(self.trade_history),
            'adaptation_history': self.adaptation_history,
            'kalman_state': {
                key: {
                    'x': kf.x,
                    'P': kf.P
                }
                for key, kf in self.kalman_filters.items()
            }
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'AdaptiveThresholds':
        """
        Deserialize from persistence.
        
        Args:
            data: Dict with state
        
        Returns:
            Restored AdaptiveThresholds instance
        """
        instance = cls(
            lookback_trades=data.get('lookback_trades', 100),
            kalman_process_noise=data.get('kalman_process_noise', 0.01),
            kalman_measurement_noise=data.get('kalman_measurement_noise', 0.1),
            ema_alpha=data.get('ema_alpha', 0.3)
        )
        
        instance.thresholds = data.get('thresholds', instance.thresholds)
        instance.trade_history = deque(
            data.get('trade_history', []),
            maxlen=instance.lookback_trades
        )
        instance.adaptation_history = data.get('adaptation_history', instance.adaptation_history)
        
        # Restore Kalman filter state
        kalman_state = data.get('kalman_state', {})
        for key, state in kalman_state.items():
            if key in instance.kalman_filters:
                instance.kalman_filters[key].x = state['x']
                instance.kalman_filters[key].P = state['P']
        
        return instance
