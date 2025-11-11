"""
Trade Constructor
Maps regime + direction -> candidate strategies, prices legs, computes costs/PNL bands, and sizes.
"""

from typing import List
from ..schemas.signals import ComposerOutput
from ..schemas.options import OptionSnapshot
from ..schemas.bars import Bar
from ..schemas.trades import TradeIdea


def construct_trade_ideas(
    thesis: ComposerOutput,
    options: List[OptionSnapshot],
    bars: List[Bar]
) -> List[TradeIdea]:
    """
    Map regime + direction → candidate strategies, price legs, compute costs/PNL bands, and size.
    
    Parameters
    ----------
    thesis : ComposerOutput
        Unified thesis from composer
    options : list[OptionSnapshot]
        Available options chain
    bars : list[Bar]
        Recent price bars for context
        
    Returns
    -------
    list[TradeIdea]
        List of trade ideas (may be empty if neutral or no suitable trades)
    """
    ideas = []
    
    if not bars:
        return ideas
    
    current_price = bars[-1].close
    
    # Directional trades
    if thesis.direction in ("long", "short") and thesis.conviction >= 0.5:
        idea = construct_directional_idea(
            thesis, options, current_price, bars
        )
        if idea:
            ideas.append(idea)
    
    # Neutral/range-bound trades
    if thesis.direction == "neutral" or thesis.conviction < 0.6:
        idea = construct_neutral_idea(
            thesis, options, current_price, bars
        )
        if idea:
            ideas.append(idea)
    
    return ideas


def construct_directional_idea(
    thesis: ComposerOutput,
    options: List[OptionSnapshot],
    current_price: float,
    bars: List[Bar]
) -> TradeIdea:
    """
    Construct directional trade idea (call/put debit spread or stock position).
    
    Returns
    -------
    TradeIdea or None
    """
    direction = thesis.direction
    symbol = thesis.symbol
    
    # If no options available, use stock position
    if not options or len(options) < 2:
        return construct_stock_idea(thesis, current_price, bars)
    
    # Use options: debit spread
    # Select near-term expiry
    options_sorted = sorted(options, key=lambda o: o.expiry)
    near_expiry = options_sorted[0].expiry
    near_options = [o for o in options if o.expiry == near_expiry]
    
    if direction == "long":
        # Call debit spread
        right = "C"
        strategy = "call_debit_spread"
    else:
        # Put debit spread
        right = "P"
        strategy = "put_debit_spread"
    
    # Filter by right
    filtered = [o for o in near_options if o.right == right]
    if len(filtered) < 2:
        return construct_stock_idea(thesis, current_price, bars)
    
    # Buy ATM, sell OTM
    filtered_sorted = sorted(filtered, key=lambda o: abs(o.strike - current_price))
    
    buy_option = filtered_sorted[0]  # closest to ATM
    # Find OTM option (above for calls, below for puts)
    if right == "C":
        sell_candidates = [o for o in filtered_sorted if o.strike > buy_option.strike]
    else:
        sell_candidates = [o for o in filtered_sorted if o.strike < buy_option.strike]
    
    if not sell_candidates:
        return construct_stock_idea(thesis, current_price, bars)
    
    sell_option = sell_candidates[0]
    
    # Compute costs
    buy_cost = (buy_option.ask + buy_option.bid) / 2.0
    sell_credit = (sell_option.ask + sell_option.bid) / 2.0
    entry_cost = buy_cost - sell_credit
    
    # Max profit is the spread width minus entry cost
    spread_width = abs(sell_option.strike - buy_option.strike)
    exit_target = spread_width  # max profit per contract
    
    # Stop loss: lose the debit paid
    stop_loss = 0.0
    
    projected_pnl = exit_target - entry_cost
    
    # Size recommendation (placeholder: 1 contract)
    recommended_size = 1
    
    # TTL based on expiry (simplified: assume weekly options = 7 days)
    ttl_days = thesis.horizon_hours / 24.0
    
    legs = [
        {"action": "BUY", "right": right, "strike": float(buy_option.strike), "expiry": near_expiry},
        {"action": "SELL", "right": right, "strike": float(sell_option.strike), "expiry": near_expiry},
    ]
    
    return TradeIdea(
        ts=thesis.ts,
        symbol=symbol,
        idea_type="options",
        strategy=strategy,
        legs=legs,
        entry_cost=float(entry_cost * 100),  # per contract (100 shares)
        exit_target=float(exit_target * 100),
        stop_loss=float(stop_loss),
        projected_pnl=float(projected_pnl * 100),
        recommended_size=recommended_size,
        ttl_days=ttl_days
    )


def construct_stock_idea(
    thesis: ComposerOutput,
    current_price: float,
    bars: List[Bar]
) -> TradeIdea:
    """
    Construct stock position trade idea.
    
    Returns
    -------
    TradeIdea
    """
    import numpy as np
    
    direction = thesis.direction
    symbol = thesis.symbol
    
    # Compute ATR for stop/target
    if len(bars) > 14:
        highs = np.array([b.high for b in bars[-14:]])
        lows = np.array([b.low for b in bars[-14:]])
        closes = np.array([b.close for b in bars[-14:]])
        
        tr1 = highs - lows
        tr2 = np.abs(highs - np.roll(closes, 1))
        tr3 = np.abs(lows - np.roll(closes, 1))
        
        tr = np.maximum(tr1, np.maximum(tr2, tr3))
        atr = float(np.mean(tr[1:]))  # skip first due to roll
    else:
        atr = current_price * 0.02  # 2% default
    
    entry_cost = current_price
    
    if direction == "long":
        strategy = "long_stock"
        exit_target = current_price + (2 * atr)
        stop_loss = current_price - atr
    else:
        strategy = "short_stock"
        exit_target = current_price - (2 * atr)
        stop_loss = current_price + atr
    
    projected_pnl = abs(exit_target - entry_cost)
    
    # Size: placeholder 100 shares
    recommended_size = 100
    
    legs = [
        {"action": "BUY" if direction == "long" else "SELL_SHORT", "quantity": 100}
    ]
    
    ttl_days = thesis.horizon_hours / 24.0
    
    return TradeIdea(
        ts=thesis.ts,
        symbol=symbol,
        idea_type="stock",
        strategy=strategy,
        legs=legs,
        entry_cost=float(entry_cost),
        exit_target=float(exit_target),
        stop_loss=float(stop_loss),
        projected_pnl=float(projected_pnl * recommended_size),
        recommended_size=recommended_size,
        ttl_days=ttl_days
    )


def construct_neutral_idea(
    thesis: ComposerOutput,
    options: List[OptionSnapshot],
    current_price: float,
    bars: List[Bar]
) -> TradeIdea:
    """
    Construct neutral/range-bound trade idea (iron condor, short strangle).
    
    Returns
    -------
    TradeIdea or None
    """
    # Simplified: iron condor
    if not options or len(options) < 4:
        return None
    
    symbol = thesis.symbol
    strategy = "iron_condor"
    
    # Select near-term expiry
    options_sorted = sorted(options, key=lambda o: o.expiry)
    near_expiry = options_sorted[0].expiry
    near_options = [o for o in options if o.expiry == near_expiry]
    
    calls = sorted([o for o in near_options if o.right == "C"], key=lambda o: o.strike)
    puts = sorted([o for o in near_options if o.right == "P"], key=lambda o: o.strike)
    
    if len(calls) < 2 or len(puts) < 2:
        return None
    
    # Find OTM strikes
    otm_calls = [c for c in calls if c.strike > current_price]
    otm_puts = [p for p in puts if p.strike < current_price]
    
    if len(otm_calls) < 2 or len(otm_puts) < 2:
        return None
    
    # Iron condor: sell closer OTM, buy further OTM
    sell_call = otm_calls[0]
    buy_call = otm_calls[1] if len(otm_calls) > 1 else otm_calls[0]
    
    sell_put = otm_puts[-1]
    buy_put = otm_puts[-2] if len(otm_puts) > 1 else otm_puts[-1]
    
    # Net credit received
    credit = (
        (sell_call.bid + sell_call.ask) / 2.0 +
        (sell_put.bid + sell_put.ask) / 2.0 -
        (buy_call.bid + buy_call.ask) / 2.0 -
        (buy_put.bid + buy_put.ask) / 2.0
    )
    
    entry_cost = -credit  # negative because we receive credit
    exit_target = 0.0  # ideal exit: options expire worthless
    
    # Max loss: width of widest spread minus credit
    call_spread_width = buy_call.strike - sell_call.strike
    put_spread_width = sell_put.strike - buy_put.strike
    max_loss = max(call_spread_width, put_spread_width) - credit
    
    stop_loss = abs(entry_cost) + max_loss
    projected_pnl = abs(credit)
    
    legs = [
        {"action": "SELL", "right": "C", "strike": float(sell_call.strike), "expiry": near_expiry},
        {"action": "BUY", "right": "C", "strike": float(buy_call.strike), "expiry": near_expiry},
        {"action": "SELL", "right": "P", "strike": float(sell_put.strike), "expiry": near_expiry},
        {"action": "BUY", "right": "P", "strike": float(buy_put.strike), "expiry": near_expiry},
    ]
    
    recommended_size = 1
    ttl_days = thesis.horizon_hours / 24.0
    
    return TradeIdea(
        ts=thesis.ts,
        symbol=symbol,
        idea_type="options",
        strategy=strategy,
        legs=legs,
        entry_cost=float(entry_cost * 100),
        exit_target=float(exit_target * 100),
        stop_loss=float(stop_loss * 100),
        projected_pnl=float(projected_pnl * 100),
        recommended_size=recommended_size,
        ttl_days=ttl_days
    )
