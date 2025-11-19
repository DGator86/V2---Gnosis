"""
Learning Orchestrator - Master Adaptive Learning Loop

Coordinates all adaptive learning components:
- Bandit strategy selector
- Adaptive thresholds
- Confidence calibrator
- Lookahead transformer

Triggered after every closed trade to update all components.

Author: Super Gnosis AI Developer
Created: 2025-11-19
"""

from __future__ import annotations
import json
import os
from typing import Dict, Optional
from datetime import datetime
import threading

from feedback.bandit_strategy_selector import BanditStrategySelector
from feedback.adaptive_thresholds import AdaptiveThresholds
from feedback.confidence_calibrator import ConfidenceCalibrator
from models.lookahead_transformer import LookaheadTransformer


class LearningOrchestrator:
    """
    Master coordinator for all adaptive learning components.
    
    Loads state on startup, updates all components after trades,
    persists state periodically.
    """
    
    def __init__(
        self,
        config: Dict,
        state_path: str = "data/adaptation_state.json"
    ):
        """
        Initialize learning orchestrator.
        
        Args:
            config: Full configuration dict
            state_path: Path to persisted state file
        """
        self.config = config
        self.state_path = state_path
        
        # Check if adaptation is enabled
        adaptation_config = config.get('adaptation', {})
        self.enabled = adaptation_config.get('enabled', False)
        
        if not self.enabled:
            print("ℹ️  Adaptive learning DISABLED - using deterministic mode")
            return
        
        print("🧠 Adaptive learning ENABLED - initializing components...")
        
        # Initialize components
        bandit_config = adaptation_config.get('bandit', {})
        self.bandit = BanditStrategySelector(
            num_strategies=28,
            alpha_prior=bandit_config.get('alpha_prior', 1.0),
            beta_prior=bandit_config.get('beta_prior', 1.0),
            per_symbol=bandit_config.get('per_symbol', True)
        )
        
        threshold_config = adaptation_config.get('thresholds', {})
        self.thresholds = AdaptiveThresholds(
            lookback_trades=threshold_config.get('lookback_trades', 100),
            kalman_process_noise=threshold_config.get('kalman_process_noise', 0.01),
            kalman_measurement_noise=threshold_config.get('kalman_measurement_noise', 0.1),
            ema_alpha=threshold_config.get('ema_alpha', 0.3)
        )
        
        calibration_config = adaptation_config.get('calibration', {})
        self.calibrator = ConfidenceCalibrator(
            min_samples=calibration_config.get('min_samples', 50),
            retrain_every_trades=calibration_config.get('retrain_every_trades', 10)
        )
        
        lookahead_config = adaptation_config.get('lookahead', {})
        self.lookahead = LookaheadTransformer(
            sequence_length=lookahead_config.get('sequence_length', 20),
            hidden_dim=lookahead_config.get('hidden_dim', 64),
            num_layers=lookahead_config.get('num_layers', 4),
            num_heads=lookahead_config.get('num_heads', 4),
            train_every_minutes=lookahead_config.get('train_every_minutes', 10),
            prediction_weight=lookahead_config.get('prediction_weight', 0.3)
        )
        
        # Load persisted state
        self.load_state()
        
        # Start background training for lookahead model
        if adaptation_config.get('lookahead_model', True):
            self.lookahead.start_background_training()
        
        # Periodic state saving
        self.save_every_minutes = adaptation_config.get('save_state_every_minutes', 15)
        self.last_save_time = datetime.now()
        
        # Lock for thread safety
        self.lock = threading.Lock()
        
        print("✅ Adaptive learning components initialized")
        print(f"   - Bandit: {self.bandit.num_strategies} strategies")
        print(f"   - Thresholds: {len(self.thresholds.thresholds)} parameters")
        print(f"   - Calibrator: {'Enabled' if self.calibrator.enabled else 'Disabled'}")
        print(f"   - Lookahead: {'Enabled' if self.lookahead.enabled else 'Disabled'}")
    
    def after_trade_closed(
        self,
        symbol: str,
        strategy_id: int,
        entry_price: float,
        exit_price: float,
        hedge_snapshot: Dict[str, float],
        raw_confidence: float,
        realized_pnl_usd: float,
        capital_risked: float,
        iv_rank: Optional[float] = None
    ):
        """
        Called after every closed trade to update all learning components.
        
        Args:
            symbol: Symbol traded
            strategy_id: Strategy used (1-28)
            entry_price: Entry price
            exit_price: Exit price
            hedge_snapshot: Hedge Engine state at entry
            raw_confidence: Original composer confidence
            realized_pnl_usd: Realized P&L in USD
            capital_risked: Capital risked on trade
            iv_rank: IV rank at entry
        """
        if not self.enabled:
            return
        
        with self.lock:
            # Calculate metrics
            price_change_pct = ((exit_price - entry_price) / entry_price) * 100.0
            pnl_pct = (realized_pnl_usd / capital_risked) * 100.0 if capital_risked > 0 else 0.0
            won = realized_pnl_usd > 0
            
            # Update bandit
            if self.config.get('adaptation', {}).get('bandit_strategies', True):
                self.bandit.update(
                    strategy_id=strategy_id,
                    pnl_pct=pnl_pct,
                    symbol=symbol
                )
            
            # Update adaptive thresholds
            if self.config.get('adaptation', {}).get('adaptive_thresholds', True):
                self.thresholds.add_trade(
                    hedge_snapshot=hedge_snapshot,
                    strategy_id=strategy_id,
                    pnl_pct=pnl_pct,
                    won=won
                )
                self.thresholds.adapt()
            
            # Update confidence calibrator
            if self.config.get('adaptation', {}).get('confidence_calibration', True):
                self.calibrator.add_trade(
                    raw_confidence=raw_confidence,
                    hedge_snapshot=hedge_snapshot,
                    won=won,
                    iv_rank=iv_rank
                )
            
            # Note: Lookahead model training happens in background thread
            # Sequences are added separately via add_hedge_snapshot()
            
            # Periodic save
            now = datetime.now()
            elapsed_minutes = (now - self.last_save_time).total_seconds() / 60.0
            if elapsed_minutes >= self.save_every_minutes:
                self.save_state()
                self.last_save_time = now
    
    def add_hedge_snapshot_sequence(
        self,
        symbol: str,
        hedge_snapshots: list[Dict[str, float]],
        future_price_change_pct: float
    ):
        """
        Add a sequence for lookahead model training.
        
        Args:
            symbol: Symbol
            hedge_snapshots: List of hedge snapshots
            future_price_change_pct: Actual price change % after sequence
        """
        if not self.enabled or not self.config.get('adaptation', {}).get('lookahead_model', True):
            return
        
        with self.lock:
            self.lookahead.add_sequence(hedge_snapshots, future_price_change_pct)
    
    def get_bandit_strategy(
        self,
        symbol: str,
        deterministic_strategy: int,
        exploration_rate: float = 0.20
    ) -> int:
        """
        Get strategy from bandit (possibly overriding deterministic choice).
        
        Args:
            symbol: Symbol
            deterministic_strategy: Strategy chosen by deterministic logic
            exploration_rate: Probability of using bandit (0-1)
        
        Returns:
            Strategy ID (1-28)
        """
        if not self.enabled or not self.config.get('adaptation', {}).get('bandit_strategies', True):
            return deterministic_strategy
        
        import random
        if random.random() < exploration_rate:
            # Use bandit
            strategy, _ = self.bandit.sample_strategy(symbol, deterministic_strategy)
            return strategy
        else:
            # Use deterministic
            return deterministic_strategy
    
    def get_calibrated_confidence(
        self,
        raw_confidence: float,
        hedge_snapshot: Dict[str, float],
        iv_rank: Optional[float] = None
    ) -> float:
        """
        Get calibrated confidence score.
        
        Args:
            raw_confidence: Original composer confidence
            hedge_snapshot: Hedge Engine state
            iv_rank: IV rank
        
        Returns:
            Calibrated confidence (0-1)
        """
        if not self.enabled or not self.config.get('adaptation', {}).get('confidence_calibration', True):
            return raw_confidence
        
        return self.calibrator.calibrate(raw_confidence, hedge_snapshot, iv_rank)
    
    def get_lookahead_prediction(
        self,
        hedge_snapshots: list[Dict[str, float]]
    ) -> Optional[float]:
        """
        Get lookahead model prediction.
        
        Args:
            hedge_snapshots: Recent hedge snapshots
        
        Returns:
            Predicted price change % or None
        """
        if not self.enabled or not self.config.get('adaptation', {}).get('lookahead_model', True):
            return None
        
        return self.lookahead.predict(hedge_snapshots)
    
    def get_threshold(self, name: str) -> float:
        """
        Get adaptive threshold value.
        
        Args:
            name: Threshold name
        
        Returns:
            Current threshold value
        """
        if not self.enabled or not self.config.get('adaptation', {}).get('adaptive_thresholds', True):
            return self.thresholds.DEFAULTS.get(name, 0.0)
        
        return self.thresholds.get_threshold(name)
    
    def get_all_stats(self) -> Dict:
        """
        Get statistics from all components for dashboard.
        
        Returns:
            Dict with all stats
        """
        if not self.enabled:
            return {'enabled': False}
        
        return {
            'enabled': True,
            'bandit': {
                'top_strategies': self.bandit.get_top_strategies(top_n=10),
                'global_probabilities': self.bandit.get_strategy_probabilities()
            },
            'thresholds': {
                'current': self.thresholds.get_all_thresholds(),
                'defaults': self.thresholds.DEFAULTS,
                'comparison': self.thresholds.get_comparison()
            },
            'calibrator': self.calibrator.get_stats(),
            'lookahead': self.lookahead.get_stats()
        }
    
    def save_state(self):
        """
        Persist all component states to JSON.
        """
        if not self.enabled:
            return
        
        try:
            state = {
                'timestamp': datetime.now().isoformat(),
                'bandit': self.bandit.to_dict(),
                'thresholds': self.thresholds.to_dict(),
                'calibrator': self.calibrator.to_dict(),
                'lookahead': self.lookahead.to_dict()
            }
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
            
            # Write to file
            with open(self.state_path, 'w') as f:
                json.dump(state, f, indent=2)
            
            print(f"💾 Adaptive learning state saved to {self.state_path}")
            
        except Exception as e:
            print(f"⚠️  Failed to save adaptation state: {e}")
    
    def load_state(self):
        """
        Load persisted component states from JSON.
        """
        if not self.enabled or not os.path.exists(self.state_path):
            print("ℹ️  No existing adaptation state found, starting fresh")
            return
        
        try:
            with open(self.state_path, 'r') as f:
                state = json.load(f)
            
            # Restore components
            if 'bandit' in state:
                self.bandit = BanditStrategySelector.from_dict(state['bandit'])
            
            if 'thresholds' in state:
                self.thresholds = AdaptiveThresholds.from_dict(state['thresholds'])
            
            if 'calibrator' in state:
                self.calibrator = ConfidenceCalibrator.from_dict(state['calibrator'])
            
            if 'lookahead' in state:
                self.lookahead = LookaheadTransformer.from_dict(state['lookahead'])
            
            print(f"✅ Adaptive learning state loaded from {self.state_path}")
            
        except Exception as e:
            print(f"⚠️  Failed to load adaptation state: {e}")
            print("   Starting with fresh state")
    
    def shutdown(self):
        """
        Gracefully shutdown (save state, stop background threads).
        """
        if not self.enabled:
            return
        
        print("🛑 Shutting down adaptive learning...")
        
        # Stop background training
        self.lookahead.stop_background_training()
        
        # Save final state
        self.save_state()
        
        print("✅ Adaptive learning shutdown complete")
