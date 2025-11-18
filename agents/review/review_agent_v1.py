"""
Review Agent V1.0 - Post-Mortem Analysis & Pattern Recognition
===============================================================

Analyzes completed predictions and trades to identify:
- What worked and what didn't
- Patterns in wins vs losses
- Confidence calibration issues
- Engine agreement patterns
- Market regime effects

Feeds insights to Optimization Agent for continuous improvement.

Author: Super Gnosis Development Team
Version: 1.0.0
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from collections import defaultdict, Counter
import numpy as np


class ReviewAgentV1:
    """
    Post-mortem analysis of predictions and trades.
    
    Key Analyses:
    1. Win/Loss Patterns
    2. Confidence Calibration
    3. Engine Agreement Effects
    4. Market Regime Performance
    5. Timeframe-Specific Insights
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.reviews: List[Dict] = []
    
    def analyze_prediction_batch(
        self,
        predictions: List[Dict],
        min_sample_size: int = 10
    ) -> Dict[str, Any]:
        """
        Analyze a batch of completed predictions.
        
        Args:
            predictions: List of completed prediction dicts from Tracker
            min_sample_size: Minimum predictions required for analysis
        
        Returns:
            Comprehensive review dict
        """
        if len(predictions) < min_sample_size:
            return {
                'status': 'insufficient_data',
                'sample_size': len(predictions),
                'required_size': min_sample_size
            }
        
        review = {
            'timestamp': datetime.now(),
            'sample_size': len(predictions),
            'analyses': {}
        }
        
        # 1. Overall accuracy metrics
        review['analyses']['overall'] = self._analyze_overall_accuracy(predictions)
        
        # 2. Confidence calibration
        review['analyses']['calibration'] = self._analyze_confidence_calibration(predictions)
        
        # 3. Timeframe performance
        review['analyses']['timeframe'] = self._analyze_timeframe_performance(predictions)
        
        # 4. Directional accuracy
        review['analyses']['directional'] = self._analyze_directional_accuracy(predictions)
        
        # 5. Range accuracy patterns
        review['analyses']['range_patterns'] = self._analyze_range_patterns(predictions)
        
        # 6. Identify best/worst patterns
        review['analyses']['patterns'] = self._identify_patterns(predictions)
        
        # 7. Actionable recommendations
        review['recommendations'] = self._generate_recommendations(review['analyses'])
        
        # Store review
        self.reviews.append(review)
        
        return review
    
    def _analyze_overall_accuracy(self, predictions: List[Dict]) -> Dict[str, float]:
        """Calculate overall accuracy metrics."""
        total_outcomes = 0
        range_correct = 0
        direction_correct = 0
        total_error = 0.0
        
        for pred in predictions:
            for outcome in pred['outcomes'].values():
                total_outcomes += 1
                if outcome['in_range']:
                    range_correct += 1
                if outcome['direction_correct']:
                    direction_correct += 1
                total_error += outcome['range_error_pct']
        
        if total_outcomes == 0:
            return {}
        
        return {
            'total_outcomes': total_outcomes,
            'range_accuracy': range_correct / total_outcomes,
            'direction_accuracy': direction_correct / total_outcomes,
            'avg_range_error_pct': total_error / total_outcomes
        }
    
    def _analyze_confidence_calibration(self, predictions: List[Dict]) -> Dict[str, Any]:
        """
        Analyze if confidence scores are well-calibrated.
        
        Theory: If we predict with 70% confidence, we should be right ~70% of the time.
        """
        # Bucket predictions by confidence
        buckets = defaultdict(lambda: {'total': 0, 'correct': 0})
        
        for pred in predictions:
            confidence = pred['confidence']
            
            # Bucket into 0.1 intervals (0.0-0.1, 0.1-0.2, etc.)
            bucket = int(confidence * 10) / 10.0
            
            for outcome in pred['outcomes'].values():
                buckets[bucket]['total'] += 1
                if outcome['in_range']:
                    buckets[bucket]['correct'] += 1
        
        # Calculate calibration
        calibration = {}
        calibration_error = 0.0
        
        for bucket, stats in buckets.items():
            if stats['total'] > 0:
                actual_accuracy = stats['correct'] / stats['total']
                expected_accuracy = bucket
                error = abs(actual_accuracy - expected_accuracy)
                
                calibration[f'conf_{bucket:.1f}'] = {
                    'expected': expected_accuracy,
                    'actual': actual_accuracy,
                    'error': error,
                    'sample_size': stats['total']
                }
                
                calibration_error += error
        
        # Average calibration error
        avg_calibration_error = calibration_error / len(buckets) if buckets else 0.0
        
        return {
            'buckets': calibration,
            'avg_calibration_error': avg_calibration_error,
            'well_calibrated': avg_calibration_error < 0.15  # Threshold
        }
    
    def _analyze_timeframe_performance(self, predictions: List[Dict]) -> Dict[str, Dict]:
        """Analyze performance by timeframe."""
        tf_stats = defaultdict(lambda: {
            'total': 0,
            'range_correct': 0,
            'direction_correct': 0,
            'errors': []
        })
        
        for pred in predictions:
            for tf, outcome in pred['outcomes'].items():
                tf_stats[tf]['total'] += 1
                if outcome['in_range']:
                    tf_stats[tf]['range_correct'] += 1
                if outcome['direction_correct']:
                    tf_stats[tf]['direction_correct'] += 1
                tf_stats[tf]['errors'].append(outcome['range_error_pct'])
        
        # Calculate metrics
        results = {}
        for tf, stats in tf_stats.items():
            if stats['total'] > 0:
                results[tf] = {
                    'sample_size': stats['total'],
                    'range_accuracy': stats['range_correct'] / stats['total'],
                    'direction_accuracy': stats['direction_correct'] / stats['total'],
                    'avg_error_pct': np.mean(stats['errors']),
                    'std_error_pct': np.std(stats['errors'])
                }
        
        return results
    
    def _analyze_directional_accuracy(self, predictions: List[Dict]) -> Dict[str, Any]:
        """Analyze accuracy by predicted direction."""
        direction_stats = defaultdict(lambda: {'total': 0, 'correct': 0})
        
        for pred in predictions:
            bias = pred['forecast'].get('directional_bias', 0.0)
            
            # Classify direction
            if bias > 0.3:
                direction = 'bullish'
            elif bias < -0.3:
                direction = 'bearish'
            else:
                direction = 'neutral'
            
            for outcome in pred['outcomes'].values():
                direction_stats[direction]['total'] += 1
                if outcome['direction_correct']:
                    direction_stats[direction]['correct'] += 1
        
        # Calculate accuracies
        results = {}
        for direction, stats in direction_stats.items():
            if stats['total'] > 0:
                results[direction] = {
                    'sample_size': stats['total'],
                    'accuracy': stats['correct'] / stats['total']
                }
        
        return results
    
    def _analyze_range_patterns(self, predictions: List[Dict]) -> Dict[str, Any]:
        """Analyze patterns in range predictions."""
        
        # Track if ranges are too wide, too narrow, or just right
        range_quality = {'too_wide': 0, 'too_narrow': 0, 'optimal': 0}
        
        for pred in predictions:
            for tf, outcome in pred['outcomes'].items():
                error = outcome['range_error_pct']
                
                # Classify range quality
                if error < 0.5:  # Very close
                    # Check if range was too wide (wasting edge)
                    range_quality['too_wide'] += 1
                elif error > 2.0:  # Missed significantly
                    range_quality['too_narrow'] += 1
                else:
                    range_quality['optimal'] += 1
        
        total = sum(range_quality.values())
        
        return {
            'range_quality': range_quality,
            'too_wide_pct': range_quality['too_wide'] / total if total > 0 else 0,
            'too_narrow_pct': range_quality['too_narrow'] / total if total > 0 else 0,
            'optimal_pct': range_quality['optimal'] / total if total > 0 else 0
        }
    
    def _identify_patterns(self, predictions: List[Dict]) -> Dict[str, Any]:
        """Identify best and worst performing patterns."""
        
        patterns = {
            'best_confidence_range': None,
            'worst_confidence_range': None,
            'best_timeframe': None,
            'worst_timeframe': None
        }
        
        # Find best/worst by confidence
        confidence_buckets = defaultdict(list)
        for pred in predictions:
            confidence = pred['confidence']
            bucket = int(confidence * 10) / 10.0
            
            for outcome in pred['outcomes'].values():
                confidence_buckets[bucket].append(outcome['in_range'])
        
        if confidence_buckets:
            accuracies = {
                bucket: sum(outcomes) / len(outcomes)
                for bucket, outcomes in confidence_buckets.items()
                if len(outcomes) >= 5  # Minimum sample
            }
            
            if accuracies:
                best_conf = max(accuracies.items(), key=lambda x: x[1])
                worst_conf = min(accuracies.items(), key=lambda x: x[1])
                
                patterns['best_confidence_range'] = {
                    'range': f'{best_conf[0]:.1f}-{best_conf[0]+0.1:.1f}',
                    'accuracy': best_conf[1]
                }
                patterns['worst_confidence_range'] = {
                    'range': f'{worst_conf[0]:.1f}-{worst_conf[0]+0.1:.1f}',
                    'accuracy': worst_conf[1]
                }
        
        # Find best/worst timeframe
        tf_accuracies = {}
        for pred in predictions:
            for tf, outcome in pred['outcomes'].items():
                if tf not in tf_accuracies:
                    tf_accuracies[tf] = []
                tf_accuracies[tf].append(outcome['in_range'])
        
        if tf_accuracies:
            tf_scores = {
                tf: sum(outcomes) / len(outcomes)
                for tf, outcomes in tf_accuracies.items()
            }
            
            best_tf = max(tf_scores.items(), key=lambda x: x[1])
            worst_tf = min(tf_scores.items(), key=lambda x: x[1])
            
            patterns['best_timeframe'] = {
                'timeframe': best_tf[0],
                'accuracy': best_tf[1]
            }
            patterns['worst_timeframe'] = {
                'timeframe': worst_tf[0],
                'accuracy': worst_tf[1]
            }
        
        return patterns
    
    def _generate_recommendations(self, analyses: Dict[str, Any]) -> List[str]:
        """Generate actionable recommendations from analysis."""
        recommendations = []
        
        # Overall accuracy recommendations
        overall = analyses.get('overall', {})
        if overall.get('range_accuracy', 0) < 0.5:
            recommendations.append(
                "⚠️ Range accuracy below 50% - Consider widening range multipliers"
            )
        
        if overall.get('direction_accuracy', 0) < 0.55:
            recommendations.append(
                "⚠️ Direction accuracy below 55% - Review engine weights and directional bias calculation"
            )
        
        # Calibration recommendations
        calibration = analyses.get('calibration', {})
        if calibration.get('avg_calibration_error', 1.0) > 0.15:
            recommendations.append(
                "⚠️ Poor confidence calibration - Adjust confidence scaling factors"
            )
        
        # Timeframe recommendations
        tf_perf = analyses.get('timeframe', {})
        for tf, stats in tf_perf.items():
            if stats.get('range_accuracy', 0) < 0.4:
                recommendations.append(
                    f"⚠️ {tf} timeframe struggling ({stats['range_accuracy']:.1%}) - Review range parameters"
                )
        
        # Range pattern recommendations
        range_patterns = analyses.get('range_patterns', {})
        if range_patterns.get('too_wide_pct', 0) > 0.4:
            recommendations.append(
                "💡 Ranges often too wide - Tighten range multipliers to capture more edge"
            )
        elif range_patterns.get('too_narrow_pct', 0) > 0.4:
            recommendations.append(
                "💡 Ranges often too narrow - Widen range multipliers to improve hit rate"
            )
        
        # Best/worst pattern recommendations
        patterns = analyses.get('patterns', {})
        if patterns.get('best_confidence_range'):
            best = patterns['best_confidence_range']
            recommendations.append(
                f"✅ Best performance at {best['range']} confidence ({best['accuracy']:.1%}) - Focus here"
            )
        
        if patterns.get('worst_timeframe'):
            worst = patterns['worst_timeframe']
            recommendations.append(
                f"⚠️ Worst performance on {worst['timeframe']} ({worst['accuracy']:.1%}) - Needs attention"
            )
        
        if not recommendations:
            recommendations.append("✅ All metrics within acceptable ranges - Continue monitoring")
        
        return recommendations
    
    def get_latest_review(self) -> Optional[Dict]:
        """Get most recent review."""
        if not self.reviews:
            return None
        return self.reviews[-1]
    
    def get_trend_analysis(self, lookback_reviews: int = 5) -> Dict[str, Any]:
        """Analyze trends across recent reviews."""
        if len(self.reviews) < 2:
            return {'status': 'insufficient_reviews'}
        
        recent_reviews = self.reviews[-lookback_reviews:]
        
        # Track accuracy trend
        accuracies = [
            r['analyses']['overall']['range_accuracy']
            for r in recent_reviews
            if 'overall' in r['analyses']
        ]
        
        if len(accuracies) >= 2:
            trend = 'improving' if accuracies[-1] > accuracies[0] else 'declining'
            change_pct = ((accuracies[-1] - accuracies[0]) / accuracies[0]) * 100
        else:
            trend = 'stable'
            change_pct = 0.0
        
        return {
            'trend': trend,
            'accuracy_change_pct': change_pct,
            'current_accuracy': accuracies[-1] if accuracies else 0.0,
            'review_count': len(recent_reviews)
        }
