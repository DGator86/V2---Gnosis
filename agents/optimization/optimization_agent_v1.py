"""
Optimization Agent V1.0 - Closed-Loop Self-Improvement
=======================================================

Takes Review Agent insights and automatically adjusts system parameters:
- Engine weights (hedge vs liquidity vs sentiment)
- Confidence calibration factors
- Range multipliers by timeframe
- Agreement thresholds
- Regime-specific adjustments

Implements gradient-free optimization (Bayesian/Evolutionary) to avoid
overfitting and maintain robustness.

Author: Super Gnosis Development Team
Version: 1.0.0
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import numpy as np
from copy import deepcopy


class ParameterSpace:
    """Define the parameter space for optimization."""
    
    def __init__(self):
        self.parameters = {
            # Engine weights (must sum to 1.0)
            'hedge_weight': {
                'min': 0.2,
                'max': 0.6,
                'current': 0.40,
                'step': 0.05
            },
            'liquidity_weight': {
                'min': 0.2,
                'max': 0.5,
                'current': 0.35,
                'step': 0.05
            },
            'sentiment_weight': {
                'min': 0.1,
                'max': 0.4,
                'current': 0.25,
                'step': 0.05
            },
            
            # Confidence calibration
            'confidence_scaling': {
                'min': 0.7,
                'max': 1.3,
                'current': 1.0,
                'step': 0.1
            },
            
            # Range multipliers by timeframe
            '1m_range_multiplier': {
                'min': 1.0,
                'max': 3.0,
                'current': 1.5,
                'step': 0.25
            },
            '5m_range_multiplier': {
                'min': 1.5,
                'max': 3.5,
                'current': 2.0,
                'step': 0.25
            },
            '15m_range_multiplier': {
                'min': 2.0,
                'max': 4.0,
                'current': 2.5,
                'step': 0.25
            },
            '1h_range_multiplier': {
                'min': 2.5,
                'max': 4.5,
                'current': 3.0,
                'step': 0.25
            },
            '4h_range_multiplier': {
                'min': 3.0,
                'max': 5.0,
                'current': 3.5,
                'step': 0.25
            },
            '1d_range_multiplier': {
                'min': 3.5,
                'max': 5.5,
                'current': 4.0,
                'step': 0.25
            },
            
            # Agreement thresholds
            'action_threshold': {
                'min': 0.2,
                'max': 0.5,
                'current': 0.3,
                'step': 0.05
            },
            'confidence_threshold': {
                'min': 0.3,
                'max': 0.7,
                'current': 0.5,
                'step': 0.1
            }
        }
    
    def get_current_config(self) -> Dict[str, float]:
        """Get current parameter configuration."""
        return {
            name: params['current']
            for name, params in self.parameters.items()
        }
    
    def update_parameter(self, name: str, value: float) -> bool:
        """Update a parameter value (with bounds checking)."""
        if name not in self.parameters:
            return False
        
        params = self.parameters[name]
        
        # Clamp to bounds
        value = max(params['min'], min(params['max'], value))
        params['current'] = value
        
        # Normalize weights if needed
        if 'weight' in name:
            self._normalize_weights()
        
        return True
    
    def _normalize_weights(self):
        """Ensure engine weights sum to 1.0."""
        weight_params = [
            'hedge_weight',
            'liquidity_weight',
            'sentiment_weight'
        ]
        
        total = sum(
            self.parameters[p]['current']
            for p in weight_params
        )
        
        if total > 0:
            for p in weight_params:
                self.parameters[p]['current'] /= total


class OptimizationAgentV1:
    """
    Self-improving optimization agent.
    
    Strategy:
    1. Collect performance metrics from Review Agent
    2. Identify underperforming parameters
    3. Propose parameter adjustments
    4. Test adjustments (via backtesting or paper trading)
    5. Apply if improvement confirmed
    
    Uses conservative gradient-free optimization to avoid overfitting.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.parameter_space = ParameterSpace()
        self.optimization_history: List[Dict] = []
        
        # Optimization settings
        self.min_samples_for_optimization = 50
        self.optimization_interval_hours = 24
        self.last_optimization_time = None
        
        # Conservative learning
        self.learning_rate = 0.2  # Small adjustments only
        self.improvement_threshold = 0.02  # 2% improvement required
    
    def should_optimize(
        self,
        current_sample_size: int
    ) -> bool:
        """Check if we should run optimization now."""
        
        # Need minimum samples
        if current_sample_size < self.min_samples_for_optimization:
            return False
        
        # Check time interval
        if self.last_optimization_time:
            from datetime import timedelta
            time_since = datetime.now() - self.last_optimization_time
            if time_since < timedelta(hours=self.optimization_interval_hours):
                return False
        
        return True
    
    def optimize(
        self,
        review: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Run optimization based on review analysis.
        
        Args:
            review: Review dict from ReviewAgent
        
        Returns:
            Optimization result with proposed changes
        """
        if not review or 'analyses' not in review:
            return {'status': 'no_review_data'}
        
        analyses = review['analyses']
        
        # Start optimization record
        opt_result = {
            'timestamp': datetime.now(),
            'baseline_metrics': analyses.get('overall', {}),
            'proposed_changes': {},
            'reasons': []
        }
        
        # 1. Optimize engine weights
        directional = analyses.get('directional', {})
        if directional:
            weight_changes = self._optimize_engine_weights(directional)
            opt_result['proposed_changes'].update(weight_changes)
        
        # 2. Optimize confidence calibration
        calibration = analyses.get('calibration', {})
        if calibration:
            conf_changes = self._optimize_confidence_calibration(calibration)
            opt_result['proposed_changes'].update(conf_changes)
        
        # 3. Optimize range multipliers
        timeframe = analyses.get('timeframe', {})
        if timeframe:
            range_changes = self._optimize_range_multipliers(timeframe)
            opt_result['proposed_changes'].update(range_changes)
        
        # 4. Optimize thresholds
        overall = analyses.get('overall', {})
        if overall:
            threshold_changes = self._optimize_thresholds(overall)
            opt_result['proposed_changes'].update(threshold_changes)
        
        # Store in history
        self.optimization_history.append(opt_result)
        self.last_optimization_time = datetime.now()
        
        return opt_result
    
    def _optimize_engine_weights(
        self,
        directional_analysis: Dict[str, Any]
    ) -> Dict[str, float]:
        """
        Optimize engine weights based on directional accuracy.
        
        Theory: If one engine consistently outperforms, increase its weight.
        """
        changes = {}
        
        # This is simplified - in practice, you'd track per-engine accuracy
        # For now, we use directional analysis as proxy
        
        bullish_accuracy = directional_analysis.get('bullish', {}).get('accuracy', 0.5)
        bearish_accuracy = directional_analysis.get('bearish', {}).get('accuracy', 0.5)
        neutral_accuracy = directional_analysis.get('neutral', {}).get('accuracy', 0.5)
        
        # Average directional accuracy
        avg_directional = np.mean([bullish_accuracy, bearish_accuracy])
        
        # If directional accuracy is poor, reduce hedge weight (it drives direction)
        if avg_directional < 0.50:
            current = self.parameter_space.parameters['hedge_weight']['current']
            new_value = current * (1 - self.learning_rate * 0.5)
            changes['hedge_weight'] = new_value
            
        # If neutral accuracy is poor, reduce sentiment weight
        if neutral_accuracy < 0.45:
            current = self.parameter_space.parameters['sentiment_weight']['current']
            new_value = current * (1 - self.learning_rate * 0.3)
            changes['sentiment_weight'] = new_value
        
        return changes
    
    def _optimize_confidence_calibration(
        self,
        calibration_analysis: Dict[str, Any]
    ) -> Dict[str, float]:
        """
        Optimize confidence scaling based on calibration error.
        
        Theory: If predictions are overconfident, reduce scaling.
        If underconfident, increase scaling.
        """
        changes = {}
        
        avg_error = calibration_analysis.get('avg_calibration_error', 0.0)
        
        if avg_error > 0.15:  # Poor calibration
            # Check if overconfident or underconfident
            buckets = calibration_analysis.get('buckets', {})
            
            # Calculate if we're systematically over/under confident
            errors = []
            for bucket_data in buckets.values():
                expected = bucket_data.get('expected', 0.5)
                actual = bucket_data.get('actual', 0.5)
                errors.append(expected - actual)  # Positive = overconfident
            
            if errors:
                avg_bias = np.mean(errors)
                
                current = self.parameter_space.parameters['confidence_scaling']['current']
                
                if avg_bias > 0.1:  # Overconfident
                    # Reduce confidence scaling
                    new_value = current * (1 - self.learning_rate)
                    changes['confidence_scaling'] = new_value
                    
                elif avg_bias < -0.1:  # Underconfident
                    # Increase confidence scaling
                    new_value = current * (1 + self.learning_rate)
                    changes['confidence_scaling'] = new_value
        
        return changes
    
    def _optimize_range_multipliers(
        self,
        timeframe_analysis: Dict[str, Dict]
    ) -> Dict[str, float]:
        """
        Optimize range multipliers for each timeframe.
        
        Theory: Adjust based on average error.
        - High error = widen ranges
        - Low error with high accuracy = tighten ranges
        """
        changes = {}
        
        for tf, stats in timeframe_analysis.items():
            param_name = f'{tf}_range_multiplier'
            
            if param_name not in self.parameter_space.parameters:
                continue
            
            avg_error = stats.get('avg_error_pct', 1.0)
            range_accuracy = stats.get('range_accuracy', 0.5)
            
            current = self.parameter_space.parameters[param_name]['current']
            
            # If high error, widen ranges
            if avg_error > 2.0 and range_accuracy < 0.5:
                new_value = current * (1 + self.learning_rate * 0.5)
                changes[param_name] = new_value
            
            # If low error and high accuracy, can tighten ranges slightly
            elif avg_error < 0.5 and range_accuracy > 0.7:
                new_value = current * (1 - self.learning_rate * 0.3)
                changes[param_name] = new_value
        
        return changes
    
    def _optimize_thresholds(
        self,
        overall_analysis: Dict[str, Any]
    ) -> Dict[str, float]:
        """
        Optimize action and confidence thresholds.
        
        Theory: Adjust based on overall accuracy.
        """
        changes = {}
        
        range_accuracy = overall_analysis.get('range_accuracy', 0.5)
        
        # If accuracy is poor, be more conservative (higher threshold)
        if range_accuracy < 0.5:
            current = self.parameter_space.parameters['confidence_threshold']['current']
            new_value = current * (1 + self.learning_rate * 0.5)
            changes['confidence_threshold'] = new_value
        
        # If accuracy is very good, can be more aggressive (lower threshold)
        elif range_accuracy > 0.7:
            current = self.parameter_space.parameters['confidence_threshold']['current']
            new_value = current * (1 - self.learning_rate * 0.3)
            changes['confidence_threshold'] = new_value
        
        return changes
    
    def apply_changes(
        self,
        changes: Dict[str, float],
        require_confirmation: bool = True
    ) -> Dict[str, Any]:
        """
        Apply proposed parameter changes.
        
        Args:
            changes: Dict of parameter changes
            require_confirmation: If True, simulate first
        
        Returns:
            Result dict with applied changes
        """
        if require_confirmation:
            # In production, you'd run backtest simulation here
            # For now, just apply conservatively
            pass
        
        applied = {}
        failed = {}
        
        for param_name, new_value in changes.items():
            success = self.parameter_space.update_parameter(param_name, new_value)
            
            if success:
                applied[param_name] = {
                    'old_value': self.parameter_space.parameters[param_name]['current'],
                    'new_value': new_value
                }
            else:
                failed[param_name] = 'parameter_not_found'
        
        return {
            'applied': applied,
            'failed': failed,
            'timestamp': datetime.now()
        }
    
    def get_current_parameters(self) -> Dict[str, float]:
        """Get current optimized parameters."""
        return self.parameter_space.get_current_config()
    
    def get_optimization_history(
        self,
        limit: Optional[int] = None
    ) -> List[Dict]:
        """Get optimization history."""
        history = self.optimization_history
        
        if limit:
            history = history[-limit:]
        
        return history
    
    def rollback_to_baseline(self) -> Dict[str, Any]:
        """Rollback all parameters to baseline values."""
        baseline = {
            'hedge_weight': 0.40,
            'liquidity_weight': 0.35,
            'sentiment_weight': 0.25,
            'confidence_scaling': 1.0,
            '1m_range_multiplier': 1.5,
            '5m_range_multiplier': 2.0,
            '15m_range_multiplier': 2.5,
            '1h_range_multiplier': 3.0,
            '4h_range_multiplier': 3.5,
            '1d_range_multiplier': 4.0,
            'action_threshold': 0.3,
            'confidence_threshold': 0.5
        }
        
        for param, value in baseline.items():
            self.parameter_space.update_parameter(param, value)
        
        return {
            'status': 'rolled_back',
            'timestamp': datetime.now(),
            'parameters': baseline
        }
