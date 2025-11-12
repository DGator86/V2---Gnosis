"""
Pipeline runner
Orchestrates the complete DHPE pipeline flow
Inputs -> Engines -> Standardization -> Primary Agents -> Composer -> Tracking -> Feedback
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid

from schemas import RawInputs, StandardSnapshot, Suggestion, Position, Result
from engines.inputs.demo_inputs_engine import DemoInputsEngine
from engines.hedge.hedge_engine import HedgeEngine
from engines.volume.volume_engine import VolumeEngine
from engines.sentiment.sentiment_engine import SentimentEngine
from engines.standardization.standardizer_engine import StandardizerEngine
from engines.lookahead.lookahead_engine import LookaheadEngine
from engines.tracking.ledger_engine import LedgerEngine
from engines.feedback.feedback_engine import FeedbackEngine
from engines.orchestration.checkpoint_engine import CheckpointEngine
from engines.orchestration.config_loader import get_config
from engines.orchestration.logger import LoggerEngine

from agents.primary_hedge.agent import PrimaryHedgeAgent
from agents.primary_volume.agent import PrimaryVolumeAgent
from agents.primary_sentiment.agent import PrimarySentimentAgent
from agents.composer.agent import ComposerAgent


class PipelineRunner:
    """
    Main pipeline runner
    Orchestrates end-to-end execution with checkpointing and feedback
    """
    
    def __init__(self, config_path: Optional[str] = None):
        # Load config
        self.config = get_config(config_path)
        
        # Setup logging
        log_level = self.config.get("runtime.log_level", "INFO")
        self.loggers = LoggerEngine.setup_pipeline_logging(log_level)
        self.logger = self.loggers['orchestration']
        
        # Initialize engines
        self.logger.info("Initializing engines...")
        self.inputs_engine = DemoInputsEngine()
        self.hedge_engine = HedgeEngine(
            polars_threads=self.config.get("engines.hedge.polars_threads", 4)
        )
        self.volume_engine = VolumeEngine(
            window_bars=self.config.get("engines.volume.window_bars", 20)
        )
        self.sentiment_engine = SentimentEngine(
            decay_half_life_days=self.config.get("engines.sentiment.decay_half_life_days", 7.0),
            max_memory_items=self.config.get("engines.sentiment.max_memory_items", 5000),
            min_confidence=self.config.get("engines.sentiment.min_confidence", 0.3)
        )
        self.standardizer = StandardizerEngine()
        self.lookahead_engine = LookaheadEngine(
            horizons=self.config.get("lookahead.horizons", [1, 5, 20, 60]),
            scenarios=self.config.get("lookahead.scenarios", ["base", "vol_up", "vol_down"])
        )
        
        # Initialize tracking and feedback
        self.ledger = LedgerEngine(
            ledger_path=self.config.get("tracking.ledger_path", "data/ledger.jsonl")
        )
        self.feedback = FeedbackEngine(
            reward_metric=self.config.get("feedback.reward_metric", "sharpe"),
            learning_rate=self.config.get("feedback.learning_rate", 0.2)
        )
        
        # Initialize checkpointing
        if self.config.get("runtime.enable_checkpointing", True):
            self.checkpoint = CheckpointEngine(
                checkpoint_dir=self.config.get("runtime.checkpoints_dir", "logs/checkpoints")
            )
        else:
            self.checkpoint = None
        
        # Initialize agents
        self.logger.info("Initializing agents...")
        self.hedge_agent = PrimaryHedgeAgent(
            confidence_threshold=self.config.get("agents.primary_hedge.confidence_threshold", 0.5),
            lookahead_engine=self.lookahead_engine
        )
        self.volume_agent = PrimaryVolumeAgent(
            confidence_threshold=self.config.get("agents.primary_volume.confidence_threshold", 0.5),
            lookahead_engine=self.lookahead_engine
        )
        self.sentiment_agent = PrimarySentimentAgent(
            confidence_threshold=self.config.get("agents.primary_sentiment.confidence_threshold", 0.5),
            lookahead_engine=self.lookahead_engine
        )
        self.composer = ComposerAgent(
            voting_method=self.config.get("agents.composer.voting_method", "weighted_confidence"),
            min_agreement_score=self.config.get("agents.composer.min_agreement_score", 0.6),
            lookahead_engine=self.lookahead_engine
        )
        
        self.logger.info("Pipeline runner initialized")
    
    def run_single_symbol(self, 
                         symbol: str,
                         raw_inputs: Optional[RawInputs] = None,
                         run_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Run complete pipeline for a single symbol
        
        Returns dict with snapshot, suggestions, composed, position, result
        """
        run_id = run_id or str(uuid.uuid4())[:8]
        self.logger.info(f"=== Starting run {run_id} for {symbol} ===")
        
        # Step 1: Get raw inputs
        if raw_inputs is None:
            raw_inputs = self.inputs_engine.get_raw_inputs(symbol)
        
        # Step 2: Run engines
        self.logger.info("Running engines...")
        hedge_output = self.hedge_engine.run(raw_inputs.options)
        volume_output = self.volume_engine.run(raw_inputs.trades, raw_inputs.orderbook)
        sentiment_output = self.sentiment_engine.run(raw_inputs.news)
        
        # Step 3: Standardize
        snapshot = self.standardizer.standardize(symbol, hedge_output, volume_output, sentiment_output)
        self.logger.info(f"Standardized snapshot | regime={snapshot.regime}")
        
        # Step 4: Run primary agents
        self.logger.info("Running primary agents...")
        horizons = self.config.get("lookahead.horizons", [1, 5, 20])
        
        hedge_suggestion = self.hedge_agent.step(snapshot, horizons)
        volume_suggestion = self.volume_agent.step(snapshot, horizons)
        sentiment_suggestion = self.sentiment_agent.step(snapshot, horizons)
        
        primary_suggestions = [hedge_suggestion, volume_suggestion, sentiment_suggestion]
        
        # Step 5: Composer
        self.logger.info("Running composer...")
        composed_suggestion = self.composer.compose(symbol, primary_suggestions, snapshot)
        
        # Step 6: Tracking - log suggestions
        self.logger.info("Logging to ledger...")
        for suggestion in primary_suggestions:
            self.ledger.log_suggestion(suggestion)
        self.ledger.log_suggestion(composed_suggestion)
        
        # Step 7: Simulate position (in real system, this would be actual execution)
        if composed_suggestion.action != "no_action" and composed_suggestion.action != "hold":
            position = Position(
                id=composed_suggestion.id,
                symbol=symbol,
                side="long" if "long" in composed_suggestion.action or "call" in composed_suggestion.action else "short",
                size=1.0,
                entry_price=450.0,  # Demo price
                entry_time=datetime.now().timestamp(),
                strategy_type=composed_suggestion.action,
                legs=[],
                metadata={"suggestion_id": composed_suggestion.id}
            )
            self.ledger.log_position(position)
            self.logger.info(f"Opened position: {position.side} {position.strategy_type}")
        else:
            position = None
            self.logger.info("No position opened (hold/no_action)")
        
        # Step 8: Simulate result (in real system, this happens later)
        result = None
        if position:
            # Demo: random outcome
            import random
            exit_price = position.entry_price + random.uniform(-2, 3)
            pnl = (exit_price - position.entry_price) * position.size
            if position.side == "short":
                pnl *= -1
            
            result = Result(
                id=composed_suggestion.id,
                exit_price=exit_price,
                exit_time=datetime.now().timestamp(),
                pnl=pnl,
                pnl_pct=pnl / position.entry_price,
                realized_horizon=max(horizons),
                metrics={"slippage": 0.0}
            )
            self.ledger.log_result(result)
            self.logger.info(f"Closed position: pnl=${pnl:.2f}")
            
            # Step 9: Feedback
            reward = self.feedback.compute_reward(result.to_dict())
            
            # Update per-agent scores
            self.feedback.update_agent_score("primary_hedge", reward * hedge_suggestion.confidence)
            self.feedback.update_agent_score("primary_volume", reward * volume_suggestion.confidence)
            self.feedback.update_agent_score("primary_sentiment", reward * sentiment_suggestion.confidence)
            self.feedback.update_agent_score("composer", reward)
            
            # Update regime-specific scores
            for agent_name in ["primary_hedge", "primary_volume", "primary_sentiment"]:
                self.feedback.update_regime_score(agent_name, snapshot.regime, reward)
            
            self.logger.info(f"Feedback updated: reward={reward:.4f}")
        
        self.logger.info(f"=== Completed run {run_id} ===\n")
        
        return {
            "run_id": run_id,
            "symbol": symbol,
            "snapshot": snapshot,
            "primary_suggestions": primary_suggestions,
            "composed_suggestion": composed_suggestion,
            "position": position,
            "result": result,
            "feedback_summary": self.feedback.get_learning_summary()
        }
    
    def run_backtest(self, symbol: str, num_runs: int = 10) -> Dict[str, Any]:
        """Run multiple iterations for backtesting"""
        self.logger.info(f"=== Starting backtest: {num_runs} runs for {symbol} ===")
        
        results = []
        for i in range(num_runs):
            run_result = self.run_single_symbol(symbol)
            results.append(run_result)
        
        # Aggregate metrics
        metrics = self.ledger.get_metrics(symbol=symbol)
        learning = self.feedback.get_learning_summary()
        
        self.logger.info(f"=== Backtest complete ===")
        self.logger.info(f"Metrics: {metrics}")
        
        return {
            "symbol": symbol,
            "num_runs": num_runs,
            "results": results,
            "aggregate_metrics": metrics,
            "learning_summary": learning
        }
