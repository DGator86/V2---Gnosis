"""
Trade Agent Router

Routes trade decisions to either stock trading (TradeAgentV1) or options trading 
(OptionsTradeAgent) based on config settings.

Author: Super Gnosis AI Developer
Created: 2025-01-19
"""

from __future__ import annotations
from typing import Dict, List, Optional, Any
import yaml
import os

from schemas.core_schemas import (
    Suggestion, 
    TradeIdea,
    OptionsOrderRequest,
    StandardSnapshot
)

# Conditional imports based on config
try:
    from trade.trade_agent_v1 import TradeAgentV1
    STOCK_AGENT_AVAILABLE = True
except ImportError:
    STOCK_AGENT_AVAILABLE = False

try:
    from trade.options_trade_agent import OptionsTradeAgent
    OPTIONS_AGENT_AVAILABLE = True
except ImportError:
    OPTIONS_AGENT_AVAILABLE = False


class TradeAgentRouter:
    """
    Routes trade generation to appropriate agent based on configuration.
    
    If config.execution.use_options is True:
        → Use OptionsTradeAgent (28 strategies)
    Else:
        → Use TradeAgentV1 (stock and basic spreads)
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize router with configuration.
        
        Args:
            config: Configuration dict. If None, loads from config/config.yaml
        """
        if config is None:
            config = self._load_config()
        
        self.config = config
        
        # Determine which agent to use
        self.use_options = config.get("execution", {}).get("use_options", False)
        
        if self.use_options:
            if not OPTIONS_AGENT_AVAILABLE:
                raise RuntimeError(
                    "Options trading enabled but OptionsTradeAgent not available. "
                    "Check trade/options_trade_agent.py"
                )
            
            # Initialize options agent
            options_config = config.get("execution", {}).get("options", {})
            portfolio_value = config.get("execution", {}).get("portfolio_value", 30000.0)
            
            self.options_agent = OptionsTradeAgent(
                portfolio_value=portfolio_value,
                risk_per_trade_pct=options_config.get("risk_per_trade_pct", 1.5),
                max_portfolio_options_pct=options_config.get("max_portfolio_options_pct", 20.0),
                default_dte_min=options_config.get("default_dte_min", 7),
                default_dte_max=options_config.get("default_dte_max", 45),
                paper_trading=config.get("execution", {}).get("mode", "paper") == "paper"
            )
            
            print(f"✅ Trade Agent Router initialized: OPTIONS MODE")
            print(f"   Portfolio: ${portfolio_value:,.2f}")
            print(f"   Risk per trade: {options_config.get('risk_per_trade_pct', 1.5)}%")
        else:
            if not STOCK_AGENT_AVAILABLE:
                raise RuntimeError(
                    "Stock trading mode but TradeAgentV1 not available. "
                    "Check trade/trade_agent_v1.py"
                )
            
            # Initialize stock agent (requires OptionsChainAdapter)
            from engines.inputs.options_chain_adapter import OptionsChainAdapter
            
            adapter = OptionsChainAdapter()
            trade_config = config.get("agents", {}).get("trade", {})
            
            self.stock_agent = TradeAgentV1(adapter=adapter, config=trade_config)
            
            print(f"✅ Trade Agent Router initialized: STOCK MODE")
    
    def generate_trade(
        self,
        suggestion: Suggestion,
        hedge_snapshot: Optional[Dict[str, float]] = None,
        current_price: Optional[float] = None,
        iv_rank: Optional[float] = None,
        iv_percentile: Optional[float] = None
    ) -> Optional[OptionsOrderRequest | List[TradeIdea]]:
        """
        Generate trade based on suggestion and market context.
        
        Args:
            suggestion: Composer Agent suggestion (BUY/SELL/HOLD)
            hedge_snapshot: Full Hedge Engine v3 snapshot (for options)
            current_price: Current stock price (for options)
            iv_rank: IV rank 0-100 (for options)
            iv_percentile: IV percentile 0-100 (for options)
        
        Returns:
            - If options mode: OptionsOrderRequest or None
            - If stock mode: List[TradeIdea]
        """
        if self.use_options:
            return self._generate_options_trade(
                suggestion,
                hedge_snapshot,
                current_price,
                iv_rank,
                iv_percentile
            )
        else:
            return self._generate_stock_trades(suggestion)
    
    def _generate_options_trade(
        self,
        suggestion: Suggestion,
        hedge_snapshot: Optional[Dict[str, float]],
        current_price: Optional[float],
        iv_rank: Optional[float],
        iv_percentile: Optional[float]
    ) -> Optional[OptionsOrderRequest]:
        """
        Generate options trade using OptionsTradeAgent.
        
        Maps Suggestion action to composer_signal:
        - "long" → "BUY"
        - "short" → "SELL"
        - "flat" / "spread" / "complex" → "HOLD"
        """
        if hedge_snapshot is None:
            hedge_snapshot = {}
        
        if current_price is None:
            current_price = 100.0  # Fallback
        
        # Map suggestion action to composer signal
        action_to_signal = {
            "long": "BUY",
            "short": "SELL",
            "flat": "HOLD",
            "spread": "HOLD",
            "complex": "HOLD"
        }
        
        composer_signal = action_to_signal.get(suggestion.action, "HOLD")
        
        # Call options agent
        order_request = self.options_agent.select_strategy(
            symbol=suggestion.symbol,
            hedge_snapshot=hedge_snapshot,
            composer_signal=composer_signal,
            composer_confidence=suggestion.confidence,
            current_price=current_price,
            iv_rank=iv_rank,
            iv_percentile=iv_percentile
        )
        
        return order_request
    
    def _generate_stock_trades(self, suggestion: Suggestion) -> List[TradeIdea]:
        """
        Generate stock trades using TradeAgentV1.
        """
        return self.stock_agent.generate_trades(suggestion)
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from config/config.yaml"""
        config_path = os.path.join(os.path.dirname(__file__), "..", "config", "config.yaml")
        
        if not os.path.exists(config_path):
            # Default config
            return {
                "execution": {
                    "use_options": False,
                    "mode": "paper",
                    "portfolio_value": 30000.0,
                    "options": {
                        "risk_per_trade_pct": 1.5,
                        "max_portfolio_options_pct": 20.0,
                        "default_dte_min": 7,
                        "default_dte_max": 45
                    }
                },
                "agents": {
                    "trade": {
                        "min_confidence": 0.5,
                        "max_legs": 4
                    }
                }
            }
        
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
        
        return config


# ============================================================================
# CONVENIENCE FUNCTION FOR EASY INTEGRATION
# ============================================================================

def create_trade_agent(config: Optional[Dict[str, Any]] = None) -> TradeAgentRouter:
    """
    Factory function to create trade agent router.
    
    Usage:
        trade_agent = create_trade_agent()
        
        # Options mode (if config.execution.use_options = true)
        order = trade_agent.generate_trade(
            suggestion=composer_suggestion,
            hedge_snapshot=hedge_engine_output,
            current_price=150.25,
            iv_rank=65.0
        )
        
        # Stock mode (if config.execution.use_options = false)
        ideas = trade_agent.generate_trade(
            suggestion=composer_suggestion
        )
    """
    return TradeAgentRouter(config=config)
