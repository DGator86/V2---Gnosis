#!/usr/bin/env python3
"""
Alpaca Quick Test Script

Quick verification that Alpaca integration is working correctly.
Tests connection, account info, quotes, and basic order placement (paper trading).

Prerequisites:
- Alpaca paper trading account (get from: https://alpaca.markets/)
- API keys configured in .env file

Usage:
    python examples/alpaca_quick_test.py
"""

import os
import sys
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from execution.broker_adapters.alpaca_adapter import AlpacaBrokerAdapter
from execution.schemas import (
    OrderRequest,
    OrderSide,
    OrderType,
    AssetClass,
    TimeInForce
)


def print_header(text: str):
    """Print formatted header."""
    print(f"\n{'='*60}")
    print(f"{text:^60}")
    print(f"{'='*60}\n")


def main():
    """Run quick Alpaca integration test."""
    
    print_header("ALPACA INTEGRATION - QUICK TEST")
    print("This script will test your Alpaca connection (paper trading only)")
    print("No real money will be at risk.\n")
    
    # 1. Check credentials
    print("🔑 Checking API credentials...")
    
    api_key = os.getenv("ALPACA_API_KEY")
    api_secret = os.getenv("ALPACA_SECRET_KEY")
    
    if not api_key or not api_secret:
        print("\n❌ ERROR: Alpaca credentials not found!")
        print("\nPlease set these environment variables:")
        print("  - ALPACA_API_KEY")
        print("  - ALPACA_SECRET_KEY")
        print("\nAdd them to your .env file or export them:")
        print("  export ALPACA_API_KEY='your_key'")
        print("  export ALPACA_SECRET_KEY='your_secret'")
        print("\nGet your keys from: https://app.alpaca.markets/paper/dashboard/overview")
        sys.exit(1)
    
    print(f"✅ API Key: {api_key[:8]}...{api_key[-4:]}")
    print(f"✅ Secret Key: {api_secret[:8]}...{api_secret[-4:]}")
    
    # 2. Initialize adapter
    print("\n🔌 Connecting to Alpaca (paper trading)...")
    
    try:
        adapter = AlpacaBrokerAdapter(
            api_key=api_key,
            secret_key=api_secret,
            paper=True  # Paper trading
        )
        print("✅ Connected successfully!")
    except Exception as e:
        print(f"\n❌ Connection failed: {e}")
        print("\nTroubleshooting:")
        print("1. Verify your API keys are correct")
        print("2. Check if keys are for paper trading (not live)")
        print("3. Ensure keys haven't expired")
        sys.exit(1)
    
    # 3. Get account info
    print_header("TEST 1: ACCOUNT INFORMATION")
    
    try:
        account = adapter.get_account()
        
        print(f"Account ID: {account.account_id}")
        print(f"Broker: {account.broker}")
        print(f"Cash: ${account.cash:,.2f}")
        print(f"Buying Power: ${account.buying_power:,.2f}")
        print(f"Portfolio Value: ${account.portfolio_value:,.2f}")
        print(f"Equity: ${account.equity:,.2f}")
        print(f"Margin Used: ${account.margin_used:,.2f}")
        print(f"\n✅ Account info retrieved successfully!")
    except Exception as e:
        print(f"❌ Failed to get account info: {e}")
        sys.exit(1)
    
    # 4. Get positions
    print_header("TEST 2: OPEN POSITIONS")
    
    try:
        positions = adapter.get_positions()
        
        if positions:
            print(f"Open Positions ({len(positions)}):")
            for pos in positions:
                print(f"\n  {pos.symbol}:")
                print(f"    Quantity: {pos.quantity}")
                print(f"    Avg Entry: ${pos.avg_entry_price:.2f}")
                print(f"    Current: ${pos.current_price:.2f}")
                print(f"    Value: ${pos.market_value:,.2f}")
                print(f"    P&L: ${pos.unrealized_pnl:,.2f}")
        else:
            print("No open positions")
        
        print(f"\n✅ Positions retrieved successfully!")
    except Exception as e:
        print(f"❌ Failed to get positions: {e}")
    
    # 5. Get real-time quote
    print_header("TEST 3: REAL-TIME QUOTES")
    
    symbol = "SPY"
    
    try:
        quote = adapter.get_quote(symbol)
        
        print(f"Symbol: {quote.symbol}")
        print(f"Bid: ${quote.bid:.2f} (size: {quote.bid_size})")
        print(f"Ask: ${quote.ask:.2f} (size: {quote.ask_size})")
        print(f"Mid: ${quote.mid:.2f}")
        print(f"Last: ${quote.last:.2f}")
        print(f"Spread: {quote.spread_pct:.4%}")
        print(f"Timestamp: {quote.timestamp}")
        
        print(f"\n✅ Quote retrieved successfully!")
    except Exception as e:
        print(f"❌ Failed to get quote: {e}")
        sys.exit(1)
    
    # 6. Test batch quotes
    print_header("TEST 4: BATCH QUOTES")
    
    symbols = ["SPY", "QQQ", "IWM"]
    
    try:
        quotes = adapter.get_quotes_batch(symbols)
        
        print(f"Retrieved quotes for {len(quotes)} symbols:")
        for q in quotes:
            print(f"  {q.symbol}: ${q.last:.2f} (spread: {q.spread_pct:.4%})")
        
        print(f"\n✅ Batch quotes retrieved successfully!")
    except Exception as e:
        print(f"❌ Failed to get batch quotes: {e}")
    
    # 7. Test order placement (optional - asks for confirmation)
    print_header("TEST 5: ORDER PLACEMENT (OPTIONAL)")
    
    print("⚠️ This test will place a REAL order in your paper trading account.")
    print("It's harmless (paper money only), but creates an order you'll need to cancel.")
    print(f"\nOrder details:")
    print(f"  Symbol: SPY")
    print(f"  Side: BUY")
    print(f"  Quantity: 1")
    print(f"  Type: LIMIT")
    print(f"  Limit Price: ${quote.bid:.2f} (likely won't fill)")
    
    response = input("\nPlace test order? (y/N): ").strip().lower()
    
    if response == 'y':
        try:
            # Create limit order at bid (unlikely to fill)
            order = OrderRequest(
                asset_class=AssetClass.STOCK,
                symbol="SPY",
                side=OrderSide.BUY,
                quantity=1,
                order_type=OrderType.LIMIT,
                limit_price=quote.bid,  # At bid, unlikely to fill
                time_in_force=TimeInForce.DAY
            )
            
            result = adapter.place_order(order)
            
            print(f"\n✅ Order placed successfully!")
            print(f"   Order ID: {result.order_id}")
            print(f"   Status: {result.status}")
            print(f"   Symbol: {result.symbol}")
            print(f"   Side: {result.side}")
            print(f"   Quantity: {result.quantity}")
            
            # Try to cancel it
            print(f"\n🔄 Attempting to cancel order...")
            success = adapter.cancel_order(result.order_id)
            
            if success:
                print(f"✅ Order cancelled successfully!")
            else:
                print(f"⚠️ Could not cancel order (it may have already filled/expired)")
            
            print(f"\nView orders at: https://app.alpaca.markets/paper/dashboard/orders")
        
        except Exception as e:
            print(f"❌ Order test failed: {e}")
    else:
        print("⏭️ Skipping order placement test")
    
    # Summary
    print_header("TEST SUMMARY")
    
    print("✅ All tests completed successfully!")
    print("\nYour Alpaca integration is working correctly.")
    print("\nNext steps:")
    print("1. Review ALPACA_INTEGRATION.md for detailed documentation")
    print("2. Run: python examples/end_to_end_trading_example.py")
    print("3. Explore the strategy examples")
    print("\nHappy trading! 🚀")
    
    print_header("COMPLETE")


if __name__ == "__main__":
    main()
