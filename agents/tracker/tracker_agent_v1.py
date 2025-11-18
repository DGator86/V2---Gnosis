"""
Tracker Agent V1.0 - Real-Time Position & Prediction Monitoring
================================================================

Monitors all:
- Live positions (if trading)
- Predictions vs actual outcomes
- Multi-timeframe forecast accuracy
- Confidence calibration

Feeds data to Review Agent for post-mortem analysis.

Author: Super Gnosis Development Team
Version: 1.0.0
"""

from __future__ import annotations

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from uuid import uuid4
import polars as pl

from schemas.core_schemas import StandardSnapshot, Suggestion, TradeIdea, LedgerRecord


class PredictionTracker:
    """Track predictions and their outcomes."""
    
    def __init__(self):
        self.active_predictions: Dict[str, Dict] = {}
        self.completed_predictions: List[Dict] = []
    
    def register_prediction(
        self,
        prediction_id: str,
        symbol: str,
        forecast: Dict[str, float],
        confidence: float,
        timestamp: datetime,
        timeframes: List[str] = None
    ) -> None:
        """
        Register a new prediction to track.
        
        Args:
            prediction_id: Unique ID for this prediction
            symbol: Stock symbol
            forecast: Multi-TF forecast dict
            confidence: Prediction confidence
            timestamp: When prediction was made
            timeframes: Timeframes to track (e.g., ['1m', '5m', '1h'])
        """
        self.active_predictions[prediction_id] = {
            'id': prediction_id,
            'symbol': symbol,
            'forecast': forecast,
            'confidence': confidence,
            'timestamp': timestamp,
            'timeframes': timeframes or ['1m', '5m', '15m', '1h', '4h', '1d'],
            'outcomes': {},
            'accuracy_by_tf': {},
            'status': 'active'
        }
    
    def update_outcome(
        self,
        prediction_id: str,
        timeframe: str,
        actual_price: float,
        timestamp: datetime
    ) -> Optional[Dict]:
        """
        Update prediction outcome for a specific timeframe.
        
        Args:
            prediction_id: Prediction to update
            timeframe: Timeframe that just completed (e.g., '1m')
            actual_price: Actual price at timeframe end
            timestamp: When this outcome occurred
        
        Returns:
            Prediction result dict or None if not found
        """
        if prediction_id not in self.active_predictions:
            return None
        
        pred = self.active_predictions[prediction_id]
        forecast = pred['forecast']
        
        # Extract predicted range for this timeframe
        low_key = f'{timeframe}_low'
        mid_key = f'{timeframe}_mid'
        high_key = f'{timeframe}_high'
        prob_key = f'{timeframe}_prob'
        
        if low_key not in forecast:
            return None  # No forecast for this TF
        
        predicted_low = forecast[low_key]
        predicted_mid = forecast[mid_key]
        predicted_high = forecast[high_key]
        predicted_prob = forecast.get(prob_key, 0.5)
        
        # Calculate accuracy
        in_range = predicted_low <= actual_price <= predicted_high
        direction_correct = (
            (actual_price >= predicted_mid and forecast.get('directional_bias', 0) > 0) or
            (actual_price <= predicted_mid and forecast.get('directional_bias', 0) < 0)
        )
        
        # Range error (% from mid)
        if predicted_mid != 0:
            range_error_pct = abs((actual_price - predicted_mid) / predicted_mid) * 100
        else:
            range_error_pct = 100.0
        
        # Store outcome
        pred['outcomes'][timeframe] = {
            'actual_price': actual_price,
            'predicted_range': (predicted_low, predicted_high),
            'predicted_mid': predicted_mid,
            'in_range': in_range,
            'direction_correct': direction_correct,
            'range_error_pct': range_error_pct,
            'timestamp': timestamp
        }
        
        # Calculate TF accuracy
        pred['accuracy_by_tf'][timeframe] = {
            'in_range': in_range,
            'direction_correct': direction_correct,
            'range_error_pct': range_error_pct
        }
        
        # Check if all TFs complete
        if len(pred['outcomes']) == len(pred['timeframes']):
            pred['status'] = 'complete'
            self.completed_predictions.append(pred)
            del self.active_predictions[prediction_id]
        
        return pred['outcomes'][timeframe]
    
    def get_active_predictions(self) -> List[Dict]:
        """Get all active predictions being tracked."""
        return list(self.active_predictions.values())
    
    def get_completed_predictions(
        self,
        since: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> List[Dict]:
        """
        Get completed predictions.
        
        Args:
            since: Only return predictions after this time
            limit: Max number to return (most recent first)
        """
        predictions = self.completed_predictions
        
        if since:
            predictions = [p for p in predictions if p['timestamp'] >= since]
        
        # Sort by timestamp descending
        predictions = sorted(predictions, key=lambda x: x['timestamp'], reverse=True)
        
        if limit:
            predictions = predictions[:limit]
        
        return predictions
    
    def calculate_aggregate_accuracy(
        self,
        timeframe: Optional[str] = None,
        since: Optional[datetime] = None
    ) -> Dict[str, float]:
        """
        Calculate aggregate accuracy metrics.
        
        Args:
            timeframe: Specific TF to analyze (None = all)
            since: Only consider predictions after this time
        
        Returns:
            Dict with accuracy metrics
        """
        predictions = self.get_completed_predictions(since=since)
        
        if not predictions:
            return {
                'total_predictions': 0,
                'range_accuracy': 0.0,
                'direction_accuracy': 0.0,
                'avg_range_error_pct': 0.0
            }
        
        total = 0
        range_correct = 0
        direction_correct = 0
        total_error = 0.0
        
        for pred in predictions:
            for tf, outcome in pred['outcomes'].items():
                # Filter by timeframe if specified
                if timeframe and tf != timeframe:
                    continue
                
                total += 1
                
                if outcome['in_range']:
                    range_correct += 1
                
                if outcome['direction_correct']:
                    direction_correct += 1
                
                total_error += outcome['range_error_pct']
        
        if total == 0:
            return {
                'total_predictions': 0,
                'range_accuracy': 0.0,
                'direction_accuracy': 0.0,
                'avg_range_error_pct': 0.0
            }
        
        return {
            'total_predictions': total,
            'range_accuracy': range_correct / total,
            'direction_accuracy': direction_correct / total,
            'avg_range_error_pct': total_error / total
        }


class PositionTracker:
    """Track live positions (for actual trading)."""
    
    def __init__(self):
        self.active_positions: Dict[str, Dict] = {}
        self.closed_positions: List[Dict] = []
    
    def open_position(
        self,
        position_id: str,
        symbol: str,
        trade_idea: TradeIdea,
        entry_price: float,
        quantity: int,
        timestamp: datetime
    ) -> None:
        """Register a new opened position."""
        self.active_positions[position_id] = {
            'id': position_id,
            'symbol': symbol,
            'trade_idea': trade_idea,
            'entry_price': entry_price,
            'quantity': quantity,
            'entry_timestamp': timestamp,
            'current_price': entry_price,
            'unrealized_pnl': 0.0,
            'status': 'open'
        }
    
    def update_position(
        self,
        position_id: str,
        current_price: float,
        timestamp: datetime
    ) -> Optional[Dict]:
        """Update position with current market price."""
        if position_id not in self.active_positions:
            return None
        
        pos = self.active_positions[position_id]
        pos['current_price'] = current_price
        pos['last_update'] = timestamp
        
        # Calculate unrealized P&L (simplified)
        side = pos['trade_idea'].side
        if side == 'long':
            pos['unrealized_pnl'] = (current_price - pos['entry_price']) * pos['quantity']
        elif side == 'short':
            pos['unrealized_pnl'] = (pos['entry_price'] - current_price) * pos['quantity']
        
        return pos
    
    def close_position(
        self,
        position_id: str,
        exit_price: float,
        timestamp: datetime,
        reason: str = 'manual'
    ) -> Optional[Dict]:
        """Close a position and calculate realized P&L."""
        if position_id not in self.active_positions:
            return None
        
        pos = self.active_positions[position_id]
        
        # Calculate realized P&L
        side = pos['trade_idea'].side
        if side == 'long':
            realized_pnl = (exit_price - pos['entry_price']) * pos['quantity']
        elif side == 'short':
            realized_pnl = (pos['entry_price'] - exit_price) * pos['quantity']
        else:
            realized_pnl = 0.0  # Complex positions need special handling
        
        # Store closed position
        closed_pos = {
            **pos,
            'exit_price': exit_price,
            'exit_timestamp': timestamp,
            'realized_pnl': realized_pnl,
            'close_reason': reason,
            'status': 'closed',
            'duration_seconds': (timestamp - pos['entry_timestamp']).total_seconds()
        }
        
        self.closed_positions.append(closed_pos)
        del self.active_positions[position_id]
        
        return closed_pos
    
    def get_active_positions(self) -> List[Dict]:
        """Get all open positions."""
        return list(self.active_positions.values())
    
    def get_closed_positions(
        self,
        since: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> List[Dict]:
        """Get closed positions."""
        positions = self.closed_positions
        
        if since:
            positions = [p for p in positions if p['exit_timestamp'] >= since]
        
        positions = sorted(positions, key=lambda x: x['exit_timestamp'], reverse=True)
        
        if limit:
            positions = positions[:limit]
        
        return positions
    
    def calculate_performance(
        self,
        since: Optional[datetime] = None
    ) -> Dict[str, float]:
        """Calculate performance metrics."""
        positions = self.get_closed_positions(since=since)
        
        if not positions:
            return {
                'total_trades': 0,
                'win_rate': 0.0,
                'total_pnl': 0.0,
                'avg_pnl': 0.0,
                'max_win': 0.0,
                'max_loss': 0.0
            }
        
        total_pnl = sum(p['realized_pnl'] for p in positions)
        wins = [p for p in positions if p['realized_pnl'] > 0]
        losses = [p for p in positions if p['realized_pnl'] <= 0]
        
        return {
            'total_trades': len(positions),
            'win_rate': len(wins) / len(positions) if positions else 0.0,
            'total_pnl': total_pnl,
            'avg_pnl': total_pnl / len(positions) if positions else 0.0,
            'max_win': max([p['realized_pnl'] for p in wins]) if wins else 0.0,
            'max_loss': min([p['realized_pnl'] for p in losses]) if losses else 0.0,
            'avg_win': sum(p['realized_pnl'] for p in wins) / len(wins) if wins else 0.0,
            'avg_loss': sum(p['realized_pnl'] for p in losses) / len(losses) if losses else 0.0
        }


class TrackerAgentV1:
    """
    Main Tracker Agent - coordinates prediction and position tracking.
    
    Responsibilities:
    - Track predictions vs outcomes
    - Track live positions (if trading)
    - Calculate real-time performance metrics
    - Feed data to Review Agent
    """
    
    def __init__(self):
        self.prediction_tracker = PredictionTracker()
        self.position_tracker = PositionTracker()
    
    def track_suggestion(
        self,
        suggestion: Suggestion,
        snapshot: StandardSnapshot
    ) -> str:
        """
        Start tracking a composer suggestion.
        
        Returns:
            Tracking ID
        """
        tracking_id = suggestion.id
        
        self.prediction_tracker.register_prediction(
            prediction_id=tracking_id,
            symbol=suggestion.symbol,
            forecast=suggestion.forecast,
            confidence=suggestion.confidence,
            timestamp=datetime.now()
        )
        
        return tracking_id
    
    def update_prediction_outcome(
        self,
        tracking_id: str,
        timeframe: str,
        actual_price: float
    ) -> Optional[Dict]:
        """Update prediction with actual outcome."""
        return self.prediction_tracker.update_outcome(
            prediction_id=tracking_id,
            timeframe=timeframe,
            actual_price=actual_price,
            timestamp=datetime.now()
        )
    
    def get_accuracy_report(
        self,
        timeframe: Optional[str] = None,
        lookback_hours: int = 24
    ) -> Dict[str, Any]:
        """Get accuracy report for recent predictions."""
        since = datetime.now() - timedelta(hours=lookback_hours)
        
        accuracy = self.prediction_tracker.calculate_aggregate_accuracy(
            timeframe=timeframe,
            since=since
        )
        
        return {
            'timeframe': timeframe or 'all',
            'lookback_hours': lookback_hours,
            'metrics': accuracy,
            'timestamp': datetime.now()
        }
    
    def get_position_report(self) -> Dict[str, Any]:
        """Get current position status report."""
        active = self.position_tracker.get_active_positions()
        performance = self.position_tracker.calculate_performance()
        
        return {
            'active_positions': len(active),
            'performance': performance,
            'timestamp': datetime.now()
        }
