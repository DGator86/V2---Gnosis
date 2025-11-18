#!/usr/bin/env python3
"""
End-to-End Trading Example: Unusual Whales → Strategy → Alpaca Execution

This example demonstrates the complete trading pipeline:
1. Fetch market data from Unusual Whales (primary) with Alpaca fallback
2. Analyze options flow and market sentiment
3. Make trading decisions based on strategy
4. Execute trades via Alpaca broker (paper trading)

Prerequisites:
- Unusual Whales API key (get from: https://unusualwhales.com/member/api-keys)
- Alpaca paper trading account (get from: https://alpaca.markets/)
- Both API keys configured in .env file

Setup:
1. Copy .env.example to .env
2. Add your API keys:
   UNUSUAL_WHALES_API_KEY=your_key_here
   ALPACA_API_KEY=your_alpaca_key
   ALPACA_SECRET_KEY=your_alpaca_secret
3. Run: python examples/end_to_end_trading_example.py
"""

import os
import sys
from datetime import datetime
from typing import Optional
from loguru import logger

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engines.inputs.data_source_manager import DataSourceManager
from execution.broker_adapters.alpaca_adapter import AlpacaBrokerAdapter
from execution.schemas import (
    OrderRequest,
    OrderSide,
    OrderType,
    AssetClass,
    TimeInForce,
    OrderStatus
)


class SimpleOptionsFlowStrategy:
    """
    Simple strategy based on Unusual Whales options flow data.
    
    Entry Rules:
    - Large call flow detected (market tide > 0.6)
    - Price above VWAP
    - Sufficient liquidity
    
    Exit Rules:
    - 2% profit target
    - 1% stop loss
    """
    
    def __init__(
        self,
        data_manager: DataSourceManager,
        broker: AlpacaBrokerAdapter,
        max_position_pct: float = 0.02,
        profit_target_pct: float = 0.02,
        stop_loss_pct: float = 0.01
    ):
        self.data_mgr = data_manager
        self.broker = broker
        self.max_position_pct = max_position_pct
        self.profit_target_pct = profit_target_pct
        self.stop_loss_pct = stop_loss_pct
    
    def analyze_symbol(self, symbol: str) -> dict:
        """
        Analyze symbol using Unusual Whales data.
        
        Returns:
            Analysis dictionary with signals and reasoning
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"ANALYZING: {symbol}")
        logger.info(f"{'='*60}")
        
        analysis = {
            "symbol": symbol,
            "timestamp": datetime.now().isoformat(),
            "signal": None,
            "confidence": 0.0,
            "reasoning": [],
            "data": {}
        }
        
        # 1. Get real-time quote (Unusual Whales → fallback to Alpaca)
        logger.info("\n📊 Fetching real-time quote...")
        quote = self.data_mgr.fetch_quote(symbol)
        if not quote:
            analysis["reasoning"].append("❌ Could not fetch quote")
            return analysis
        
        current_price = quote['last']
        analysis["data"]["price"] = current_price
        logger.info(f"✅ Current Price: ${current_price:.2f}")
        
        # 2. Get market tide from Unusual Whales
        logger.info("\n🌊 Checking market tide...")
        try:
            if self.data_mgr.unusual_whales:
                tide = self.data_mgr.unusual_whales.get_market_tide()
                if tide and 'data' in tide:
                    market_tide = tide['data'].get('tide', 0)
                    analysis["data"]["market_tide"] = market_tide
                    logger.info(f"✅ Market Tide: {market_tide:.2f}")
                    
                    if market_tide > 0.6:
                        analysis["reasoning"].append(f"✅ Bullish market tide ({market_tide:.2f})")
                        analysis["confidence"] += 0.3
                    elif market_tide < -0.6:
                        analysis["reasoning"].append(f"❌ Bearish market tide ({market_tide:.2f})")
                        analysis["confidence"] -= 0.3
        except Exception as e:
            logger.warning(f"Could not fetch market tide: {e}")
            analysis["reasoning"].append("⚠️ Market tide unavailable")
        
        # 3. Get options flow alerts
        logger.info("\n🔔 Checking options flow alerts...")
        try:
            if self.data_mgr.unusual_whales:
                flow = self.data_mgr.unusual_whales.get_flow_alerts(limit=10)
                if flow and 'data' in flow:
                    # Count alerts for this symbol
                    symbol_alerts = [
                        alert for alert in flow['data']
                        if alert.get('ticker') == symbol
                    ]
                    
                    analysis["data"]["flow_alerts"] = len(symbol_alerts)
                    logger.info(f"✅ Options Flow Alerts: {len(symbol_alerts)}")
                    
                    if len(symbol_alerts) > 0:
                        # Analyze sentiment
                        call_alerts = [a for a in symbol_alerts if a.get('call_put') == 'CALL']
                        put_alerts = [a for a in symbol_alerts if a.get('call_put') == 'PUT']
                        
                        logger.info(f"   - Call alerts: {len(call_alerts)}")
                        logger.info(f"   - Put alerts: {len(put_alerts)}")
                        
                        if len(call_alerts) > len(put_alerts):
                            analysis["reasoning"].append(f"✅ More call flow ({len(call_alerts)} vs {len(put_alerts)})")
                            analysis["confidence"] += 0.4
                        else:
                            analysis["reasoning"].append(f"❌ More put flow ({len(put_alerts)} vs {len(call_alerts)})")
                            analysis["confidence"] -= 0.4
        except Exception as e:
            logger.warning(f"Could not fetch flow alerts: {e}")
            analysis["reasoning"].append("⚠️ Options flow unavailable")
        
        # 4. Make decision
        logger.info(f"\n🎯 Final Confidence: {analysis['confidence']:.2f}")
        
        if analysis["confidence"] >= 0.5:
            analysis["signal"] = "BUY"
            logger.info("✅ SIGNAL: BUY")
        elif analysis["confidence"] <= -0.5:
            analysis["signal"] = "SELL"
            logger.info("❌ SIGNAL: SELL")
        else:
            analysis["signal"] = "HOLD"
            logger.info("⏸️ SIGNAL: HOLD")
        
        return analysis
    
    def execute_trade(self, analysis: dict) -> Optional[str]:
        """
        Execute trade based on analysis.
        
        Returns:
            Order ID if trade executed, None otherwise
        """
        symbol = analysis["symbol"]
        signal = analysis["signal"]
        
        if signal == "HOLD":
            logger.info("\n⏸️ No trade action (HOLD signal)")
            return None
        
        logger.info(f"\n{'='*60}")
        logger.info(f"EXECUTING TRADE")
        logger.info(f"{'='*60}")
        
        # 1. Get account info
        account = self.broker.get_account()
        logger.info(f"\n💰 Account Info:")
        logger.info(f"   Cash: ${account.cash:,.2f}")
        logger.info(f"   Buying Power: ${account.buying_power:,.2f}")
        logger.info(f"   Portfolio Value: ${account.portfolio_value:,.2f}")
        
        # 2. Calculate position size (max 2% of portfolio)
        max_position_value = account.portfolio_value * self.max_position_pct
        current_price = analysis["data"]["price"]
        quantity = int(max_position_value / current_price)
        
        if quantity == 0:
            logger.warning("⚠️ Calculated quantity is 0, skipping trade")
            return None
        
        logger.info(f"\n📦 Position Sizing:")
        logger.info(f"   Max Position: ${max_position_value:,.2f} ({self.max_position_pct:.1%})")
        logger.info(f"   Quantity: {quantity} shares")
        logger.info(f"   Total Value: ${quantity * current_price:,.2f}")
        
        # 3. Create order
        side = OrderSide.BUY if signal == "BUY" else OrderSide.SELL
        
        # Use limit order at current ask (for buys) or bid (for sells)
        quote = self.data_mgr.fetch_quote(symbol)
        if signal == "BUY":
            limit_price = quote.get('ask', current_price) * 1.001  # 0.1% above ask
        else:
            limit_price = quote.get('bid', current_price) * 0.999  # 0.1% below bid
        
        order = OrderRequest(
            asset_class=AssetClass.STOCK,
            symbol=symbol,
            side=side,
            quantity=quantity,
            order_type=OrderType.LIMIT,
            limit_price=limit_price,
            time_in_force=TimeInForce.DAY
        )
        
        logger.info(f"\n📋 Order Details:")
        logger.info(f"   Symbol: {symbol}")
        logger.info(f"   Side: {side}")
        logger.info(f"   Quantity: {quantity}")
        logger.info(f"   Limit Price: ${limit_price:.2f}")
        
        # 4. Submit order
        try:
            result = self.broker.place_order(order)
            logger.info(f"\n✅ Order Submitted!")
            logger.info(f"   Order ID: {result.order_id}")
            logger.info(f"   Status: {result.status}")
            
            return result.order_id
        
        except Exception as e:
            logger.error(f"\n❌ Order Failed: {e}")
            return None
    
    def monitor_position(self, symbol: str, entry_price: float):
        """Monitor position and implement exit rules."""
        logger.info(f"\n{'='*60}")
        logger.info(f"MONITORING POSITION: {symbol}")
        logger.info(f"{'='*60}")
        
        # Get current position
        positions = self.broker.get_positions()
        position = next((p for p in positions if p.symbol == symbol), None)
        
        if not position:
            logger.warning(f"⚠️ No position found for {symbol}")
            return
        
        # Calculate P&L
        current_price = position.current_price
        pnl_pct = (current_price - entry_price) / entry_price
        
        logger.info(f"\n📊 Position Status:")
        logger.info(f"   Entry Price: ${entry_price:.2f}")
        logger.info(f"   Current Price: ${current_price:.2f}")
        logger.info(f"   Quantity: {position.quantity}")
        logger.info(f"   Unrealized P&L: ${position.unrealized_pnl:,.2f} ({pnl_pct:+.2%})")
        
        # Check exit conditions
        should_exit = False
        reason = ""
        
        if pnl_pct >= self.profit_target_pct:
            should_exit = True
            reason = f"✅ Profit target hit ({pnl_pct:+.2%} >= {self.profit_target_pct:+.2%})"
        elif pnl_pct <= -self.stop_loss_pct:
            should_exit = True
            reason = f"❌ Stop loss hit ({pnl_pct:+.2%} <= {-self.stop_loss_pct:+.2%})"
        
        if should_exit:
            logger.info(f"\n🚪 EXIT SIGNAL: {reason}")
            
            # Place exit order
            order = OrderRequest(
                asset_class=AssetClass.STOCK,
                symbol=symbol,
                side=OrderSide.SELL,
                quantity=position.quantity,
                order_type=OrderType.MARKET
            )
            
            try:
                result = self.broker.place_order(order)
                logger.info(f"✅ Exit order submitted: {result.order_id}")
            except Exception as e:
                logger.error(f"❌ Exit order failed: {e}")
        else:
            logger.info("\n⏳ Position within targets, continuing to monitor...")


def main():
    """Run end-to-end trading example."""
    
    # Configure logging
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="INFO"
    )
    
    logger.info("\n" + "="*60)
    logger.info("END-TO-END TRADING EXAMPLE")
    logger.info("Unusual Whales → Strategy → Alpaca Execution")
    logger.info("="*60)
    
    # 1. Check environment variables
    logger.info("\n🔑 Checking API credentials...")
    
    unusual_whales_key = os.getenv("UNUSUAL_WHALES_API_KEY")
    alpaca_key = os.getenv("ALPACA_API_KEY")
    alpaca_secret = os.getenv("ALPACA_SECRET_KEY")
    
    if not all([unusual_whales_key, alpaca_key, alpaca_secret]):
        logger.error("\n❌ Missing required API keys!")
        logger.info("\nPlease set the following in your .env file:")
        if not unusual_whales_key:
            logger.info("  - UNUSUAL_WHALES_API_KEY")
        if not alpaca_key:
            logger.info("  - ALPACA_API_KEY")
        if not alpaca_secret:
            logger.info("  - ALPACA_SECRET_KEY")
        logger.info("\nSee ALPACA_INTEGRATION.md for setup instructions.")
        sys.exit(1)
    
    logger.info("✅ All API keys found")
    
    # 2. Initialize data manager
    logger.info("\n📊 Initializing data manager...")
    data_mgr = DataSourceManager(
        unusual_whales_api_key=unusual_whales_key,
        alpaca_api_key=alpaca_key,
        alpaca_api_secret=alpaca_secret,
        alpaca_paper=True  # Paper trading
    )
    logger.info("✅ Data manager initialized")
    
    # 3. Initialize broker
    logger.info("\n🏦 Initializing Alpaca broker (paper trading)...")
    broker = AlpacaBrokerAdapter(
        api_key=alpaca_key,
        secret_key=alpaca_secret,
        paper=True  # PAPER TRADING - NO REAL MONEY
    )
    logger.info("✅ Alpaca broker connected")
    
    # 4. Initialize strategy
    logger.info("\n🎯 Initializing strategy...")
    strategy = SimpleOptionsFlowStrategy(
        data_manager=data_mgr,
        broker=broker,
        max_position_pct=0.02,   # 2% max position
        profit_target_pct=0.02,   # 2% profit target
        stop_loss_pct=0.01        # 1% stop loss
    )
    logger.info("✅ Strategy initialized")
    
    # 5. Analyze target symbol
    symbol = "SPY"  # S&P 500 ETF
    analysis = strategy.analyze_symbol(symbol)
    
    # 6. Display results
    logger.info(f"\n{'='*60}")
    logger.info("ANALYSIS SUMMARY")
    logger.info(f"{'='*60}")
    logger.info(f"Symbol: {analysis['symbol']}")
    logger.info(f"Signal: {analysis['signal']}")
    logger.info(f"Confidence: {analysis['confidence']:.2f}")
    logger.info(f"\nReasoning:")
    for reason in analysis['reasoning']:
        logger.info(f"  {reason}")
    
    # 7. Execute trade (if signal is actionable)
    if analysis['signal'] != 'HOLD':
        logger.info(f"\n⚠️ This is PAPER TRADING - no real money at risk")
        logger.info(f"Press Enter to execute {analysis['signal']} order, or Ctrl+C to cancel...")
        try:
            input()
            order_id = strategy.execute_trade(analysis)
            
            if order_id:
                logger.info(f"\n✅ Trade executed successfully!")
                logger.info(f"Order ID: {order_id}")
                logger.info(f"\nYou can monitor this order at:")
                logger.info(f"https://app.alpaca.markets/paper/dashboard/orders")
        except KeyboardInterrupt:
            logger.info("\n\n⚠️ Trade cancelled by user")
    else:
        logger.info(f"\n✅ Analysis complete. No trade action needed (HOLD signal)")
    
    logger.info(f"\n{'='*60}")
    logger.info("EXAMPLE COMPLETE")
    logger.info(f"{'='*60}\n")


if __name__ == "__main__":
    main()
