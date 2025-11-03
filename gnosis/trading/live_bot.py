"""
Live Paper Trading Bot

Real-time trading with:
- WebSocket data stream from Alpaca
- Agent evaluation every bar
- Position management
- Risk controls
- Memory integration
- State persistence
"""

from __future__ import annotations
import asyncio
import signal
import sys
from datetime import datetime, timedelta
from typing import Optional, Dict
import uuid
import json
from pathlib import Path

try:
    from alpaca.data.live import StockDataStream
    from alpaca.data.timeframe import TimeFrame
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import MarketOrderRequest
    from alpaca.trading.enums import OrderSide, TimeInForce
    ALPACA_AVAILABLE = True
except ImportError:
    ALPACA_AVAILABLE = False
    print("⚠️  alpaca-py not installed. Install with: pip install alpaca-py")

import os
from dotenv import load_dotenv
import pandas as pd

# Load environment
load_dotenv()

# Import our components
from gnosis.trading.position_manager import PositionManager, Position
from gnosis.trading.risk_manager import RiskManager
from gnosis.regime import RegimeDetector, RegimeState
from gnosis.engines.hedge_v0 import compute_hedge_v0
from gnosis.engines.liquidity_v0 import compute_liquidity_v0
from gnosis.engines.sentiment_v0 import compute_sentiment_v0
from gnosis.engines.wyckoff_v0 import compute_wyckoff_v0
from gnosis.engines.markov_regime_v0 import compute_markov_regime_v0, SimpleHMM

# Try to import memory (optional)
try:
    from gnosis.memory import (
        Episode, AgentView, write_episode,
        reflect_on_episode, index_episode,
        augment_with_memory
    )
    MEMORY_AVAILABLE = True
except ImportError:
    MEMORY_AVAILABLE = False
    # Fallback AgentView dataclass if memory not available
    from dataclasses import dataclass
    from typing import Any
    
    @dataclass
    class AgentView:
        agent_name: str
        signal: int
        confidence: float
        reasoning: str
        features: dict


class LiveTradingBot:
    """
    Live paper trading bot
    
    Lifecycle:
    1. Connect to Alpaca WebSocket
    2. Aggregate 1-min bars
    3. Compute features every bar
    4. Evaluate agents
    5. Make decisions (with memory)
    6. Manage positions
    7. Log episodes
    """
    
    def __init__(
        self,
        symbol: str = "SPY",
        bar_interval: str = "1Min",
        enable_memory: bool = True,
        enable_trading: bool = True,
        paper_mode: bool = True
    ):
        if not ALPACA_AVAILABLE:
            raise RuntimeError("alpaca-py required. Install: pip install alpaca-py")
        
        self.symbol = symbol
        self.bar_interval = bar_interval
        self.enable_memory = enable_memory and MEMORY_AVAILABLE
        self.enable_trading = enable_trading
        self.paper_mode = paper_mode
        
        # Alpaca clients
        api_key = os.getenv("ALPACA_API_KEY")
        secret_key = os.getenv("ALPACA_SECRET_KEY")
        
        self.stream = StockDataStream(api_key, secret_key, raw_data=False)
        self.trading_client = TradingClient(api_key, secret_key, paper=paper_mode)
        
        # Components
        self.position_mgr = PositionManager(
            state_file="live_trading_state.json",
            max_positions=3,
            max_daily_loss=-0.05
        )
        self.risk_mgr = RiskManager(capital=30000.0)
        self.regime_detector = RegimeDetector()
        self.markov_hmm = SimpleHMM()  # Stateful HMM for markov agent
        
        # Data buffers
        self.bars: list = []  # Recent bars for feature computation
        self.current_bar = None
        
        # State
        self.running = False
        self.trades_today = 0
        
        print(f"🤖 Live Trading Bot Initialized")
        print(f"   Symbol: {self.symbol}")
        print(f"   Interval: {self.bar_interval}")
        print(f"   Memory: {'✅' if self.enable_memory else '❌'}")
        print(f"   Trading: {'✅' if self.enable_trading else '❌ (dry run)'}")
        print(f"   Mode: {'📄 PAPER' if paper_mode else '💰 LIVE'}")
    
    async def on_bar(self, bar):
        """Handle new bar from WebSocket"""
        try:
            # Convert to dict
            bar_data = {
                "t_event": bar.timestamp,
                "symbol": bar.symbol,
                "price": bar.close,
                "volume": bar.volume,
                "high": bar.high,
                "low": bar.low,
                "open": bar.open
            }
            
            self.bars.append(bar_data)
            
            # Keep last 100 bars
            if len(self.bars) > 100:
                self.bars = self.bars[-100:]
            
            # Process bar
            await self.process_bar(bar_data)
            
        except Exception as e:
            print(f"❌ Error in on_bar: {e}")
            import traceback
            traceback.print_exc()
    
    async def process_bar(self, bar: dict):
        """
        Process new bar: compute features, evaluate agents, make decisions
        """
        timestamp = bar["t_event"]
        price = bar["price"]
        
        print(f"\n{'='*60}")
        print(f"⏰ {timestamp} | {self.symbol} @ ${price:.2f}")
        
        # Reset daily counters if new day
        self.position_mgr.reset_daily()
        
        # Update existing positions
        self.position_mgr.update_positions({self.symbol: price})
        
        # Check for exits
        exits = self.position_mgr.check_exits()
        for symbol, reason in exits:
            await self.close_position(symbol, price, reason)
        
        # Don't evaluate new entries if we need more bars
        if len(self.bars) < 50:
            print(f"📊 Warming up... ({len(self.bars)}/50 bars)")
            return
        
        # Compute features
        features = self.compute_features(bar)
        if features is None:
            return
        
        # Evaluate agents
        agent_views = self.evaluate_agents(features, price)
        
        # Make decision
        decision = self.make_decision(agent_views, features, price, timestamp)
        
        # Execute if decision made
        if decision and decision["action"] != 0:
            await self.execute_decision(decision, price, timestamp)
    
    def compute_features(self, current_bar: dict) -> Optional[Dict]:
        """Compute L3 features from recent bars"""
        try:
            # Convert bars to DataFrame
            df = pd.DataFrame(self.bars)
            df["t_event"] = pd.to_datetime(df["t_event"])
            
            # Compute features (simplified - you'd use full pipeline)
            features = {
                "price": current_bar["price"],
                "volume": current_bar["volume"],
                "sent_momentum": 0.0,  # Placeholder
                "liq_amihud": 0.02,    # Placeholder
                "hedge_gamma": 0.0,    # Placeholder
            }
            
            # You would call actual engines here:
            # hedge = compute_hedge_v0(self.symbol, timestamp, price, chain)
            # liq = compute_liquidity_v0(self.symbol, timestamp, df)
            # sent = compute_sentiment_v0(self.symbol, timestamp, df)
            
            return features
            
        except Exception as e:
            print(f"⚠️  Feature computation failed: {e}")
            return None
    
    def evaluate_agents(self, features: Dict, price: float) -> list:
        """
        Evaluate agents (conditionally based on regime)
        
        Base agents (always active): hedge, liquidity, sentiment
        Conditional agents: wyckoff (trends), markov (clear regimes)
        """
        agent_views = []
        
        # Detect regime first
        df = pd.DataFrame(self.bars)
        regime = self.regime_detector.detect(df)
        
        print(f"📊 Regime: {regime.primary} (conf={regime.confidence:.2f}, "
              f"trend={regime.trend_strength:+.2f})")
        
        # Simplified agent evaluation (you'd use actual agent classes)
        # For now, using dummy logic
        
        # Hedge agent
        hedge_signal = 0
        hedge_conf = 0.5
        if features.get("hedge_gamma", 0) > 0.3:
            hedge_signal = 1
            hedge_conf = 0.7
        
        agent_views.append(AgentView(
            "hedge", hedge_signal, hedge_conf,
            "Dummy hedge logic", {"gamma": features.get("hedge_gamma", 0)}
        ))
        
        # Liquidity agent
        liq_signal = 0
        liq_conf = 0.5
        if features.get("liq_amihud", 0.02) < 0.015:
            liq_signal = 1
            liq_conf = 0.65
        
        agent_views.append(AgentView(
            "liquidity", liq_signal, liq_conf,
            "Dummy liquidity logic", {"amihud": features.get("liq_amihud", 0)}
        ))
        
        # Sentiment agent  
        sent_signal = 0
        sent_conf = 0.5
        if features.get("sent_momentum", 0) > 0.2:
            sent_signal = 1
            sent_conf = 0.6
        
        agent_views.append(AgentView(
            "sentiment", sent_signal, sent_conf,
            "Dummy sentiment logic", {"momentum": features.get("sent_momentum", 0)}
        ))
        
        # Conditional: Wyckoff agent (active in trends)
        if self.regime_detector.should_use_wyckoff(regime):
            wyckoff_result = compute_wyckoff_v0(self.symbol, df["t_event"].iloc[-1], df)
            wyckoff_signal = 0
            wyckoff_conf = wyckoff_result["confidence"]
            
            # Signal logic based on phase
            if wyckoff_result["phase"] == "accumulation" and wyckoff_result["spring_detected"]:
                wyckoff_signal = 1
                wyckoff_conf = min(0.8, wyckoff_conf + 0.2)
            elif wyckoff_result["phase"] == "distribution" and wyckoff_result["upthrust_detected"]:
                wyckoff_signal = -1
                wyckoff_conf = min(0.8, wyckoff_conf + 0.2)
            elif wyckoff_result["phase"] == "markup":
                wyckoff_signal = 1
            elif wyckoff_result["phase"] == "markdown":
                wyckoff_signal = -1
            
            agent_views.append(AgentView(
                "wyckoff", wyckoff_signal, wyckoff_conf,
                f"Phase: {wyckoff_result['phase']}", {"phase": wyckoff_result["phase"]}
            ))
            print(f"   ✅ Wyckoff active: {wyckoff_result['phase']}")
        else:
            print(f"   ⏸️  Wyckoff inactive (regime: {regime.primary})")
        
        # Conditional: Markov agent (active in clear regimes)
        if self.regime_detector.should_use_markov(regime):
            markov_result = compute_markov_regime_v0(
                self.symbol, df["t_event"].iloc[-1], df, hmm=self.markov_hmm
            )
            markov_signal = 0
            markov_conf = markov_result["confidence"]
            
            # Signal logic based on state
            state = markov_result["current_state"]
            if state == "trending_up":
                markov_signal = 1
            elif state == "trending_down":
                markov_signal = -1
            elif state == "accumulation":
                markov_signal = 1
                markov_conf *= 0.8  # Lower confidence for accumulation
            elif state == "distribution":
                markov_signal = -1
                markov_conf *= 0.8
            
            agent_views.append(AgentView(
                "markov", markov_signal, markov_conf,
                f"State: {state}", {"state": state}
            ))
            print(f"   ✅ Markov active: {state}")
        else:
            print(f"   ⏸️  Markov inactive (regime: {regime.primary})")
        
        return agent_views
    
    def make_decision(
        self,
        agent_views: list,
        features: Dict,
        price: float,
        timestamp: datetime
    ) -> Optional[Dict]:
        """
        Make trading decision using agents + memory
        """
        # Dynamic consensus (2 votes minimum, scales with agent count)
        signals = [av.signal for av in agent_views]
        votes = {-1: signals.count(-1), 0: signals.count(0), 1: signals.count(1)}
        
        # Find majority
        base_decision = max(votes.items(), key=lambda x: x[1])[0]
        
        # Require at least 2 votes (works for 3-5 agents)
        min_votes = max(2, len(agent_views) // 2)
        if votes[base_decision] < min_votes:
            base_decision = 0
        
        # Average confidence
        matching_agents = [av for av in agent_views if av.signal == base_decision]
        base_confidence = sum(av.confidence for av in matching_agents) / len(matching_agents) if matching_agents else 0.5
        
        # Base size
        base_size = self.risk_mgr.calculate_position_size(
            base_confidence,
            volatility=0.15,
            existing_positions=len(self.position_mgr.positions)
        )
        
        # Augment with memory if available
        if self.enable_memory and MEMORY_AVAILABLE:
            decision, confidence, size, memory_ctx = augment_with_memory(
                self.symbol, features, agent_views,
                base_decision, base_confidence, base_size,
                timestamp
            )
            
            if memory_ctx.get("recall_count", 0) > 0:
                print(f"🧠 Memory: {memory_ctx['recall_count']} recalls, "
                      f"win rate={memory_ctx.get('recall_win_rate', 0):.2%}")
        else:
            decision = base_decision
            confidence = base_confidence
            size = base_size
            memory_ctx = {}
        
        # Print agent votes
        print(f"🗳️  Votes: {votes}")
        print(f"   Decision: {decision} (conf={confidence:.2f}, size={size:.2%})")
        
        if decision == 0:
            return None
        
        return {
            "action": decision,
            "confidence": confidence,
            "size": size,
            "agent_views": agent_views,
            "features": features,
            "memory_context": memory_ctx
        }
    
    async def execute_decision(
        self,
        decision: Dict,
        price: float,
        timestamp: datetime
    ):
        """Execute trading decision"""
        action = decision["action"]
        size = decision["size"]
        confidence = decision["confidence"]
        
        # Check if we can open position
        can_open, reason = self.position_mgr.can_open_position(self.symbol)
        if not can_open:
            print(f"⚠️  Cannot open position: {reason}")
            return
        
        # Calculate stops
        stop_loss = self.risk_mgr.calculate_stop_loss(price, action, confidence)
        take_profit = self.risk_mgr.calculate_take_profit(price, action, stop_loss)
        
        # Validate trade
        existing_risk = sum(p.size for p in self.position_mgr.positions.values())
        valid, msg = self.risk_mgr.validate_trade(
            self.symbol, action, size, confidence, existing_risk
        )
        
        if not valid:
            print(f"⚠️  Trade rejected: {msg}")
            return
        
        # Create episode if memory enabled
        episode_id = None
        if self.enable_memory and MEMORY_AVAILABLE:
            episode_id = str(uuid.uuid4())
            episode = Episode(
                episode_id=episode_id,
                symbol=self.symbol,
                t_open=timestamp,
                price_open=price,
                features_digest=decision["features"],
                agent_views=decision["agent_views"],
                decision=action,
                decision_confidence=confidence,
                position_size=size,
                consensus_logic="live_memory_augmented"
            )
            write_episode(episode)
        
        # Open position in position manager
        position = self.position_mgr.open_position(
            symbol=self.symbol,
            side=action,
            size=size,
            entry_price=price,
            confidence=confidence,
            stop_loss=stop_loss,
            take_profit=take_profit,
            episode_id=episode_id
        )
        
        # Execute actual order if trading enabled
        if self.enable_trading and position:
            await self.place_order(position)
    
    async def place_order(self, position: Position):
        """Place actual order with Alpaca"""
        try:
            # Calculate share quantity (simplified - using $10k notional)
            notional = 10000 * position.size
            qty = int(notional / position.entry_price)
            
            if qty < 1:
                print("⚠️  Quantity too small, skipping order")
                return
            
            # Create order request
            order_request = MarketOrderRequest(
                symbol=position.symbol,
                qty=qty,
                side=OrderSide.BUY if position.side == 1 else OrderSide.SELL,
                time_in_force=TimeInForce.DAY
            )
            
            # Submit order
            order = self.trading_client.submit_order(order_request)
            
            print(f"📤 Order submitted: {order.id}")
            print(f"   {order.side} {order.qty} {order.symbol} @ market")
            
        except Exception as e:
            print(f"❌ Order failed: {e}")
    
    async def close_position(self, symbol: str, price: float, reason: str):
        """Close position and update episode"""
        trade = self.position_mgr.close_position(symbol, price, reason)
        
        if not trade:
            return
        
        # Update episode if memory enabled
        if self.enable_memory and MEMORY_AVAILABLE and trade.get("episode_id"):
            from gnosis.memory import read_episode
            
            ep = read_episode(trade["episode_id"])
            if ep:
                ep.update_outcome(
                    t_close=trade["exit_time"],
                    price_close=price,
                    exit_reason=reason,
                    pnl=trade["realized_pnl"],
                    hit_target=(reason == "take_profit")
                )
                reflect_on_episode(ep)
                write_episode(ep)
                index_episode(ep)
                
                print(f"💭 Reflection: {ep.key_lesson}")
        
        # Close actual position if trading enabled
        if self.enable_trading:
            await self.close_alpaca_position(symbol)
    
    async def close_alpaca_position(self, symbol: str):
        """Close Alpaca position"""
        try:
            self.trading_client.close_position(symbol)
            print(f"📤 Closed Alpaca position: {symbol}")
        except Exception as e:
            print(f"⚠️  Could not close Alpaca position: {e}")
    
    async def run(self):
        """Main event loop"""
        self.running = True
        
        print(f"\n{'='*60}")
        print(f"🚀 Starting Live Trading Bot")
        print(f"{'='*60}")
        
        # Subscribe to bars
        self.stream.subscribe_bars(self.on_bar, self.symbol)
        
        # Start stream
        print(f"📡 Connecting to Alpaca WebSocket...")
        
        try:
            await self.stream._run_forever()
        except KeyboardInterrupt:
            print("\n⏹️  Shutting down...")
        finally:
            await self.shutdown()
    
    async def shutdown(self):
        """Clean shutdown"""
        self.running = False
        
        # Show final summary
        summary = self.position_mgr.get_portfolio_summary()
        print(f"\n{'='*60}")
        print(f"📊 Final Summary")
        print(f"{'='*60}")
        print(f"   Open Positions: {summary['positions']}")
        print(f"   Daily PnL: {summary['daily_pnl']:+.2%}")
        print(f"   Daily Trades: {summary['daily_trades']}")
        print(f"   Total PnL: {summary['total_pnl']:+.2%}")
        
        print("\n✅ Bot stopped gracefully")


async def main():
    """Entry point"""
    bot = LiveTradingBot(
        symbol="SPY",
        bar_interval="1Min",
        enable_memory=True,
        enable_trading=False,  # Set True to actually trade
        paper_mode=True
    )
    
    await bot.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
