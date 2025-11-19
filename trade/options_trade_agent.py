"""
Options Trade Agent - Super Gnosis DHPE v3

Implements complete 28-strategy decision logic that maps Hedge Engine v3 + Composer Agent
signals to actionable options trades.

Author: Super Gnosis AI Developer
Created: 2025-01-19
"""

from __future__ import annotations
import uuid
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import math

from schemas.core_schemas import (
    OptionsOrderRequest,
    OptionsLeg,
    StandardSnapshot
)


class OptionsTradeAgent:
    """
    Core options trading agent implementing 28-strategy decision tree.
    
    Inputs:
        - Hedge Engine v3 snapshot (elasticity, movement_energy, energy_asymmetry, etc.)
        - Composer Agent decision (BUY/SELL/HOLD) + confidence
        - Current market data (price, IV rank/percentile)
    
    Output:
        - Complete OptionsOrderRequest with 1-4 legs, strikes, expirations, sizing
    """
    
    # Strategy categorization
    DIRECTIONAL_STRATEGIES = list(range(1, 8))  # 1-7
    PREMIUM_COLLECTION_STRATEGIES = list(range(8, 15))  # 8-14
    TIME_SPREAD_STRATEGIES = list(range(15, 17))  # 15-16
    IRON_STRUCTURE_STRATEGIES = list(range(17, 23))  # 17-22
    SYNTHETIC_STRATEGIES = list(range(23, 25))  # 23-24
    AGGRESSIVE_STRATEGIES = list(range(25, 29))  # 25-28
    
    # Delta targets for strike selection
    DELTA_TARGETS = {
        'deep_itm': 0.80,
        'itm': 0.70,
        'itm_near': 0.60,
        'atm': 0.50,
        'otm_near': 0.30,
        'otm': 0.25,
        'otm_far': 0.16
    }
    
    def __init__(
        self,
        portfolio_value: float = 30000.0,
        risk_per_trade_pct: float = 1.5,
        max_portfolio_options_pct: float = 20.0,
        default_dte_min: int = 7,
        default_dte_max: int = 45,
        paper_trading: bool = True,
        learning_orchestrator=None
    ):
        """
        Initialize Options Trade Agent.
        
        Args:
            portfolio_value: Total account equity
            risk_per_trade_pct: Risk percentage per trade (1-2%)
            max_portfolio_options_pct: Max 20% of portfolio in options BPR
            default_dte_min: Minimum days to expiration
            default_dte_max: Maximum days to expiration
            paper_trading: Enable paper trading mode
            learning_orchestrator: Optional LearningOrchestrator for adaptive strategy selection
        """
        self.portfolio_value = portfolio_value
        self.risk_per_trade_pct = risk_per_trade_pct
        self.max_portfolio_options_pct = max_portfolio_options_pct
        self.default_dte_min = default_dte_min
        self.default_dte_max = default_dte_max
        self.paper_trading = paper_trading
        self.learning_orchestrator = learning_orchestrator
        
        print(f"✅ Options Trade Agent initialized")
        print(f"   Portfolio: ${portfolio_value:,.2f}")
        print(f"   Risk per trade: {risk_per_trade_pct}%")
        print(f"   Mode: {'PAPER' if paper_trading else 'LIVE'}")
        if learning_orchestrator:
            print(f"   🧠 Adaptive Learning: ENABLED")
    
    def select_strategy(
        self,
        symbol: str,
        hedge_snapshot: Dict[str, float],
        composer_signal: str,
        composer_confidence: float,
        current_price: float,
        iv_rank: Optional[float] = None,
        iv_percentile: Optional[float] = None
    ) -> Optional[OptionsOrderRequest]:
        """
        Main decision tree: Map Hedge Engine + Composer signals to one of 28 strategies.
        
        Args:
            symbol: Underlying ticker
            hedge_snapshot: Full Hedge Engine v3 output
            composer_signal: BUY/SELL/HOLD
            composer_confidence: 0.0 to 1.0
            current_price: Current stock price
            iv_rank: IV rank (0-100)
            iv_percentile: IV percentile (0-100)
        
        Returns:
            Complete OptionsOrderRequest or None if no strategy selected
        """
        
        # Extract Hedge Engine features
        elasticity = hedge_snapshot.get('elasticity', 1.0)
        movement_energy = hedge_snapshot.get('movement_energy', 0.0)
        movement_energy_up = hedge_snapshot.get('movement_energy_up', 0.0)
        movement_energy_down = hedge_snapshot.get('movement_energy_down', 0.0)
        energy_asymmetry = hedge_snapshot.get('energy_asymmetry', 0.0)
        dealer_gamma_sign = hedge_snapshot.get('dealer_gamma_sign', 0.0)
        pressure_up = hedge_snapshot.get('pressure_up', 0.0)
        pressure_down = hedge_snapshot.get('pressure_down', 0.0)
        net_pressure = hedge_snapshot.get('net_pressure', 0.0)
        
        # Default IV metrics if not provided
        if iv_rank is None:
            iv_rank = 50.0
        if iv_percentile is None:
            iv_percentile = 50.0
        
        # Classify market conditions
        is_low_elasticity = elasticity < 0.5
        is_mid_elasticity = 0.5 <= elasticity <= 1.5
        is_high_elasticity = elasticity > 1.5
        
        is_stabilizing_gamma = dealer_gamma_sign > 0
        is_destabilizing_gamma = dealer_gamma_sign < 0
        
        is_high_iv = iv_rank > 70 or iv_percentile > 70
        is_low_iv = iv_rank < 30 or iv_percentile < 30
        
        is_bullish = composer_signal == "BUY"
        is_bearish = composer_signal == "SELL"
        is_neutral = composer_signal == "HOLD"
        
        is_strong_conviction = composer_confidence > 0.75
        is_moderate_conviction = 0.5 <= composer_confidence <= 0.75
        is_weak_conviction = composer_confidence < 0.5
        
        is_positive_asymmetry = energy_asymmetry > 0.3
        is_negative_asymmetry = energy_asymmetry < -0.3
        is_neutral_asymmetry = -0.3 <= energy_asymmetry <= 0.3
        
        # Main decision tree - exact if/elif logic
        strategy_number = None
        rationale = ""
        
        # ==================== CATEGORY 1: PURE DIRECTIONAL ====================
        
        if is_bullish and is_strong_conviction and is_low_elasticity and is_positive_asymmetry and is_destabilizing_gamma:
            # Strategy 1: Long ATM Call
            strategy_number = 1
            rationale = "Strong bullish conviction + explosive conditions + destabilizing gamma → Long ATM Call"
        
        elif is_bullish and is_strong_conviction and movement_energy_up > movement_energy_down * 1.5:
            # Strategy 2: Bull Call Spread
            strategy_number = 2
            rationale = "Strong bullish + high upward energy → Bull Call Spread (reduced cost)"
        
        elif is_bullish and is_strong_conviction and is_stabilizing_gamma and is_low_elasticity:
            # Strategy 3: Call Ratio Backspread
            strategy_number = 3
            rationale = "Strong bullish + stabilizing gamma + explosive setup → Call Ratio Backspread"
        
        elif is_bullish and is_moderate_conviction and is_high_elasticity and is_negative_asymmetry:
            # Strategy 4: Poor Man's Covered Call
            strategy_number = 4
            rationale = "Moderate bullish + stock replacement needed → Poor Man's Covered Call"
        
        elif is_bearish and is_strong_conviction and is_low_elasticity and is_negative_asymmetry:
            # Strategy 5: Long ATM Put
            strategy_number = 5
            rationale = "Strong bearish conviction + explosive downside conditions → Long ATM Put"
        
        elif is_bearish and is_strong_conviction and movement_energy_down > movement_energy_up * 1.5:
            # Strategy 6: Bear Put Spread
            strategy_number = 6
            rationale = "Strong bearish + high downward energy → Bear Put Spread (reduced cost)"
        
        elif is_bearish and is_strong_conviction and is_stabilizing_gamma:
            # Strategy 7: Put Ratio Backspread
            strategy_number = 7
            rationale = "Strong bearish + stabilizing gamma → Put Ratio Backspread"
        
        # ==================== CATEGORY 2: PREMIUM COLLECTION ====================
        
        elif is_neutral and is_high_elasticity and is_low_elasticity == False and is_high_iv:
            # Strategy 8: Short Strangle
            strategy_number = 8
            rationale = "Neutral + high elasticity + high IV → Short Strangle (premium collection)"
        
        elif is_neutral and is_high_elasticity and is_high_iv and abs(net_pressure) < 0.2:
            # Strategy 9: Short Straddle
            strategy_number = 9
            rationale = "Neutral + high elasticity + pinned price + high IV → Short Straddle (max theta)"
        
        elif is_neutral and is_high_elasticity and is_low_iv:
            # Strategy 10: Long Strangle
            strategy_number = 10
            rationale = "Neutral + high elasticity + low IV → Long Strangle (IV expansion play)"
        
        elif is_bullish and is_moderate_conviction and is_high_elasticity and is_stabilizing_gamma:
            # Strategy 11: Jade Lizard
            strategy_number = 11
            rationale = "Mild bullish + high elasticity + stabilizing gamma → Jade Lizard (no upside risk)"
        
        elif is_bearish and is_moderate_conviction and is_high_elasticity and is_stabilizing_gamma:
            # Strategy 12: Reverse Jade Lizard
            strategy_number = 12
            rationale = "Mild bearish + high elasticity + stabilizing gamma → Reverse Jade Lizard"
        
        elif is_bullish and is_moderate_conviction and movement_energy < 0.5:
            # Strategy 13: Covered Call
            strategy_number = 13
            rationale = "Mild bullish + low movement energy → Covered Call (income on long position)"
        
        elif is_bearish and is_moderate_conviction and movement_energy < 0.5:
            # Strategy 14: Cash-Secured Put
            strategy_number = 14
            rationale = "Mild bearish + low movement energy → Cash-Secured Put (wheel strategy)"
        
        # ==================== CATEGORY 3: TIME SPREADS ====================
        
        elif (is_neutral or is_bullish) and is_moderate_conviction and iv_rank < 50 and is_mid_elasticity:
            # Strategy 15: Call Calendar
            strategy_number = 15
            rationale = "Neutral-bullish + rising IV expected → Call Calendar (time spread)"
        
        elif (is_neutral or is_bearish) and is_moderate_conviction and iv_rank < 50 and is_mid_elasticity:
            # Strategy 16: Put Calendar
            strategy_number = 16
            rationale = "Neutral-bearish + rising IV expected → Put Calendar (time spread)"
        
        # ==================== CATEGORY 4: IRON STRUCTURES ====================
        
        elif is_neutral and is_high_elasticity and is_stabilizing_gamma and abs(net_pressure) < 0.3:
            # Strategy 17: Iron Condor
            strategy_number = 17
            rationale = "Neutral + high elasticity + stabilizing gamma → Iron Condor (defined risk)"
        
        elif is_bullish and is_weak_conviction and is_high_elasticity:
            # Strategy 18: Broken-Wing Butterfly Call
            strategy_number = 18
            rationale = "Mild bullish + high elasticity → Broken-Wing Butterfly Call (free/credit)"
        
        elif is_bearish and is_weak_conviction and is_high_elasticity:
            # Strategy 19: Broken-Wing Butterfly Put
            strategy_number = 19
            rationale = "Mild bearish + high elasticity → Broken-Wing Butterfly Put (free/credit)"
        
        elif is_bullish and movement_energy > 1.5 and is_positive_asymmetry:
            # Strategy 20: Long Call Butterfly
            strategy_number = 20
            rationale = "High energy + positive asymmetry → Long Call Butterfly (cheap lottery)"
        
        elif is_bearish and movement_energy > 1.5 and is_negative_asymmetry:
            # Strategy 21: Long Put Butterfly
            strategy_number = 21
            rationale = "High energy + negative asymmetry → Long Put Butterfly (cheap lottery)"
        
        elif is_neutral and is_high_elasticity and elasticity > 2.0:
            # Strategy 22: Double Diagonal
            strategy_number = 22
            rationale = "Neutral + extremely high elasticity → Double Diagonal (advanced theta/vega)"
        
        # ==================== CATEGORY 5: SYNTHETIC & REVERSALS ====================
        
        elif is_bullish and is_moderate_conviction and is_destabilizing_gamma:
            # Strategy 23: Risk Reversal (Synthetic Long)
            strategy_number = 23
            rationale = "Bullish + destabilizing gamma → Risk Reversal (zero-cost directional)"
        
        elif is_bearish and is_moderate_conviction and is_destabilizing_gamma:
            # Strategy 24: Risk Reversal (Synthetic Short)
            strategy_number = 24
            rationale = "Bearish + destabilizing gamma → Risk Reversal (zero-cost directional)"
        
        # ==================== CATEGORY 6: AGGRESSIVE PREMIUM SELLING ====================
        
        elif is_neutral and is_low_elasticity and is_high_iv and iv_rank > 80:
            # Strategy 25: Short Guts
            strategy_number = 25
            rationale = "Neutral + trapped market + very high IV → Short Guts (aggressive premium)"
        
        elif is_bearish and is_strong_conviction and is_low_elasticity and self.paper_trading:
            # Strategy 26: Naked Call (PAPER ONLY)
            strategy_number = 26
            rationale = "Strong bearish + very low elasticity → Naked Call (PAPER ONLY - extreme risk)"
        
        elif is_bullish and is_strong_conviction and is_low_elasticity:
            # Strategy 27: Naked Put (Wheel Continuation)
            strategy_number = 27
            rationale = "Strong bullish + low elasticity → Naked Put (aggressive wheel strategy)"
        
        elif abs(hedge_snapshot.get('position_delta', 0.0)) > 50:
            # Strategy 28: Delta-Neutral Adjustment
            strategy_number = 28
            rationale = "Existing position delta requires hedging → Delta-Neutral Adjustment"
        
        else:
            # No strategy matched - insufficient signal strength or ambiguous conditions
            print(f"⚠️  No options strategy selected for {symbol} - insufficient signal clarity")
            return None
        
        # 🧠 ADAPTIVE LEARNING OVERRIDE: Bandit Strategy Selection
        # If learning orchestrator is enabled, use bandit to override deterministic choice
        # with 20% exploration rate
        original_strategy = strategy_number
        if self.learning_orchestrator and self.learning_orchestrator.enabled:
            bandit_strategy = self.learning_orchestrator.get_bandit_strategy(
                symbol=symbol,
                deterministic_choice=strategy_number
            )
            if bandit_strategy != strategy_number:
                print(f"🧠 Bandit Override: Strategy #{strategy_number} → #{bandit_strategy} (exploration)")
                strategy_number = bandit_strategy
                rationale = f"[BANDIT EXPLORATION] {rationale} (original: #{original_strategy})"
        
        # Build the complete options order based on selected strategy
        print(f"✅ Selected Strategy #{strategy_number} for {symbol}: {rationale}")
        
        order_request = self._build_strategy(
            strategy_number=strategy_number,
            symbol=symbol,
            current_price=current_price,
            hedge_snapshot=hedge_snapshot,
            composer_signal=composer_signal,
            composer_confidence=composer_confidence,
            rationale=rationale,
            iv_rank=iv_rank
        )
        
        return order_request
    
    def _build_strategy(
        self,
        strategy_number: int,
        symbol: str,
        current_price: float,
        hedge_snapshot: Dict[str, float],
        composer_signal: str,
        composer_confidence: float,
        rationale: str,
        iv_rank: float
    ) -> OptionsOrderRequest:
        """
        Build complete OptionsOrderRequest for a specific strategy.
        
        Maps strategy number (1-28) to exact leg structure, strikes, expirations.
        """
        
        # Route to category-specific builder
        if strategy_number in self.DIRECTIONAL_STRATEGIES:
            return self._build_directional_strategy(
                strategy_number, symbol, current_price, hedge_snapshot,
                composer_signal, composer_confidence, rationale
            )
        elif strategy_number in self.PREMIUM_COLLECTION_STRATEGIES:
            return self._build_premium_collection_strategy(
                strategy_number, symbol, current_price, hedge_snapshot,
                composer_signal, composer_confidence, rationale, iv_rank
            )
        elif strategy_number in self.TIME_SPREAD_STRATEGIES:
            return self._build_time_spread_strategy(
                strategy_number, symbol, current_price, hedge_snapshot,
                composer_signal, composer_confidence, rationale
            )
        elif strategy_number in self.IRON_STRUCTURE_STRATEGIES:
            return self._build_iron_structure_strategy(
                strategy_number, symbol, current_price, hedge_snapshot,
                composer_signal, composer_confidence, rationale
            )
        elif strategy_number in self.SYNTHETIC_STRATEGIES:
            return self._build_synthetic_strategy(
                strategy_number, symbol, current_price, hedge_snapshot,
                composer_signal, composer_confidence, rationale
            )
        elif strategy_number in self.AGGRESSIVE_STRATEGIES:
            return self._build_aggressive_strategy(
                strategy_number, symbol, current_price, hedge_snapshot,
                composer_signal, composer_confidence, rationale
            )
        else:
            raise ValueError(f"Unknown strategy number: {strategy_number}")
    
    # ============================================================================
    # CATEGORY 1: DIRECTIONAL STRATEGIES (1-7)
    # ============================================================================
    
    def _build_directional_strategy(
        self,
        strategy_number: int,
        symbol: str,
        current_price: float,
        hedge_snapshot: Dict[str, float],
        composer_signal: str,
        composer_confidence: float,
        rationale: str
    ) -> OptionsOrderRequest:
        """Build strategies 1-7: Pure directional plays"""
        
        legs: List[OptionsLeg] = []
        strategy_name = ""
        max_loss = 0.0
        max_profit = None
        
        # Select expiration
        expiration_date = self._select_expiration(dte_min=21, dte_max=45)
        
        if strategy_number == 1:
            # Long ATM Call
            strategy_name = "Long ATM Call"
            atm_strike = self._find_strike_by_delta(symbol, current_price, 0.50, 'call')
            
            legs.append(OptionsLeg(
                symbol=self._build_options_symbol(symbol, expiration_date, 'call', atm_strike),
                side="buy",
                quantity=1,
                option_type="call",
                strike=atm_strike,
                expiration_date=expiration_date,
                delta=0.50
            ))
            
            # Estimate max loss (premium paid - using simplified model)
            max_loss = self._estimate_option_premium(current_price, atm_strike, 'call', expiration_date) * 100
            max_profit = None  # Unlimited
        
        elif strategy_number == 2:
            # Bull Call Spread
            strategy_name = "Bull Call Spread"
            long_strike = self._find_strike_by_delta(symbol, current_price, 0.30, 'call')
            short_strike = self._find_strike_by_delta(symbol, current_price, 0.50, 'call')
            
            legs.append(OptionsLeg(
                symbol=self._build_options_symbol(symbol, expiration_date, 'call', long_strike),
                side="buy",
                quantity=1,
                option_type="call",
                strike=long_strike,
                expiration_date=expiration_date,
                delta=0.30
            ))
            
            legs.append(OptionsLeg(
                symbol=self._build_options_symbol(symbol, expiration_date, 'call', short_strike),
                side="sell",
                quantity=1,
                option_type="call",
                strike=short_strike,
                expiration_date=expiration_date,
                delta=0.50
            ))
            
            spread_width = short_strike - long_strike
            long_premium = self._estimate_option_premium(current_price, long_strike, 'call', expiration_date)
            short_premium = self._estimate_option_premium(current_price, short_strike, 'call', expiration_date)
            max_loss = (long_premium - short_premium) * 100
            max_profit = (spread_width * 100) - max_loss
        
        elif strategy_number == 3:
            # Call Ratio Backspread
            strategy_name = "Call Ratio Backspread"
            short_strike = self._find_strike_by_delta(symbol, current_price, 0.55, 'call')
            long_strike = self._find_strike_by_delta(symbol, current_price, 0.30, 'call')
            
            legs.append(OptionsLeg(
                symbol=self._build_options_symbol(symbol, expiration_date, 'call', short_strike),
                side="sell",
                quantity=1,
                option_type="call",
                strike=short_strike,
                expiration_date=expiration_date,
                delta=0.55
            ))
            
            legs.append(OptionsLeg(
                symbol=self._build_options_symbol(symbol, expiration_date, 'call', long_strike),
                side="buy",
                quantity=2,
                option_type="call",
                strike=long_strike,
                expiration_date=expiration_date,
                delta=0.30
            ))
            
            short_premium = self._estimate_option_premium(current_price, short_strike, 'call', expiration_date)
            long_premium = self._estimate_option_premium(current_price, long_strike, 'call', expiration_date)
            net_debit = (2 * long_premium - short_premium) * 100
            max_loss = max(net_debit, 0)  # Or unlimited on downside
            max_profit = None  # Unlimited upside
        
        elif strategy_number == 4:
            # Poor Man's Covered Call
            strategy_name = "Poor Man's Covered Call"
            leap_expiration = self._select_expiration(dte_min=180, dte_max=365)
            leap_strike = self._find_strike_by_delta(symbol, current_price, 0.80, 'call')
            short_strike = self._find_strike_by_delta(symbol, current_price, 0.30, 'call')
            
            legs.append(OptionsLeg(
                symbol=self._build_options_symbol(symbol, leap_expiration, 'call', leap_strike),
                side="buy",
                quantity=1,
                option_type="call",
                strike=leap_strike,
                expiration_date=leap_expiration,
                delta=0.80
            ))
            
            legs.append(OptionsLeg(
                symbol=self._build_options_symbol(symbol, expiration_date, 'call', short_strike),
                side="sell",
                quantity=1,
                option_type="call",
                strike=short_strike,
                expiration_date=expiration_date,
                delta=0.30
            ))
            
            leap_premium = self._estimate_option_premium(current_price, leap_strike, 'call', leap_expiration)
            short_premium = self._estimate_option_premium(current_price, short_strike, 'call', expiration_date)
            max_loss = (leap_premium - short_premium) * 100  # Simplified
            max_profit = (short_strike - leap_strike) * 100
        
        elif strategy_number == 5:
            # Long ATM Put
            strategy_name = "Long ATM Put"
            atm_strike = self._find_strike_by_delta(symbol, current_price, 0.50, 'put')
            
            legs.append(OptionsLeg(
                symbol=self._build_options_symbol(symbol, expiration_date, 'put', atm_strike),
                side="buy",
                quantity=1,
                option_type="put",
                strike=atm_strike,
                expiration_date=expiration_date,
                delta=-0.50
            ))
            
            max_loss = self._estimate_option_premium(current_price, atm_strike, 'put', expiration_date) * 100
            max_profit = (atm_strike * 100) - max_loss  # Stock goes to zero
        
        elif strategy_number == 6:
            # Bear Put Spread
            strategy_name = "Bear Put Spread"
            long_strike = self._find_strike_by_delta(symbol, current_price, 0.50, 'put')
            short_strike = self._find_strike_by_delta(symbol, current_price, 0.30, 'put')
            
            legs.append(OptionsLeg(
                symbol=self._build_options_symbol(symbol, expiration_date, 'put', long_strike),
                side="buy",
                quantity=1,
                option_type="put",
                strike=long_strike,
                expiration_date=expiration_date,
                delta=-0.50
            ))
            
            legs.append(OptionsLeg(
                symbol=self._build_options_symbol(symbol, expiration_date, 'put', short_strike),
                side="sell",
                quantity=1,
                option_type="put",
                strike=short_strike,
                expiration_date=expiration_date,
                delta=-0.30
            ))
            
            spread_width = long_strike - short_strike
            long_premium = self._estimate_option_premium(current_price, long_strike, 'put', expiration_date)
            short_premium = self._estimate_option_premium(current_price, short_strike, 'put', expiration_date)
            max_loss = (long_premium - short_premium) * 100
            max_profit = (spread_width * 100) - max_loss
        
        elif strategy_number == 7:
            # Put Ratio Backspread
            strategy_name = "Put Ratio Backspread"
            short_strike = self._find_strike_by_delta(symbol, current_price, 0.55, 'put')
            long_strike = self._find_strike_by_delta(symbol, current_price, 0.30, 'put')
            
            legs.append(OptionsLeg(
                symbol=self._build_options_symbol(symbol, expiration_date, 'put', short_strike),
                side="sell",
                quantity=1,
                option_type="put",
                strike=short_strike,
                expiration_date=expiration_date,
                delta=-0.55
            ))
            
            legs.append(OptionsLeg(
                symbol=self._build_options_symbol(symbol, expiration_date, 'put', long_strike),
                side="buy",
                quantity=2,
                option_type="put",
                strike=long_strike,
                expiration_date=expiration_date,
                delta=-0.30
            ))
            
            short_premium = self._estimate_option_premium(current_price, short_strike, 'put', expiration_date)
            long_premium = self._estimate_option_premium(current_price, long_strike, 'put', expiration_date)
            net_debit = (2 * long_premium - short_premium) * 100
            max_loss = max(net_debit, 0)
            max_profit = None  # Unlimited downside
        
        # Calculate position size and BPR
        quantity = self._calculate_position_size(max_loss)
        bpr = self._calculate_buying_power_reduction(strategy_name, legs, quantity)
        
        # Build order request
        order_request = OptionsOrderRequest(
            order_id=str(uuid.uuid4()),
            symbol=symbol,
            strategy_name=strategy_name,
            strategy_number=strategy_number,
            legs=legs,
            order_type="market",
            max_loss=max_loss,
            max_profit=max_profit,
            buying_power_reduction=bpr,
            hedge_engine_snapshot=hedge_snapshot,
            composer_signal=composer_signal,
            composer_confidence=composer_confidence,
            rationale=rationale,
            tags=["directional", composer_signal.lower()]
        )
        
        return order_request
    
    # ============================================================================
    # CATEGORY 2: PREMIUM COLLECTION STRATEGIES (8-14)
    # ============================================================================
    
    def _build_premium_collection_strategy(
        self,
        strategy_number: int,
        symbol: str,
        current_price: float,
        hedge_snapshot: Dict[str, float],
        composer_signal: str,
        composer_confidence: float,
        rationale: str,
        iv_rank: float
    ) -> OptionsOrderRequest:
        """Build strategies 8-14: Premium collection and theta decay"""
        
        legs: List[OptionsLeg] = []
        strategy_name = ""
        max_loss = None  # Many premium strategies have undefined max loss
        max_profit = 0.0
        
        expiration_date = self._select_expiration(dte_min=30, dte_max=45)
        
        if strategy_number == 8:
            # Short Strangle
            strategy_name = "Short Strangle"
            call_strike = self._find_strike_by_delta(symbol, current_price, 0.16, 'call')
            put_strike = self._find_strike_by_delta(symbol, current_price, 0.16, 'put')
            
            legs.append(OptionsLeg(
                symbol=self._build_options_symbol(symbol, expiration_date, 'call', call_strike),
                side="sell",
                quantity=1,
                option_type="call",
                strike=call_strike,
                expiration_date=expiration_date,
                delta=0.16
            ))
            
            legs.append(OptionsLeg(
                symbol=self._build_options_symbol(symbol, expiration_date, 'put', put_strike),
                side="sell",
                quantity=1,
                option_type="put",
                strike=put_strike,
                expiration_date=expiration_date,
                delta=-0.16
            ))
            
            call_premium = self._estimate_option_premium(current_price, call_strike, 'call', expiration_date)
            put_premium = self._estimate_option_premium(current_price, put_strike, 'put', expiration_date)
            max_profit = (call_premium + put_premium) * 100
            max_loss = None  # Unlimited on both sides
        
        elif strategy_number == 9:
            # Short Straddle
            strategy_name = "Short Straddle"
            atm_strike = self._find_strike_by_delta(symbol, current_price, 0.50, 'call')
            
            legs.append(OptionsLeg(
                symbol=self._build_options_symbol(symbol, expiration_date, 'call', atm_strike),
                side="sell",
                quantity=1,
                option_type="call",
                strike=atm_strike,
                expiration_date=expiration_date,
                delta=0.50
            ))
            
            legs.append(OptionsLeg(
                symbol=self._build_options_symbol(symbol, expiration_date, 'put', atm_strike),
                side="sell",
                quantity=1,
                option_type="put",
                strike=atm_strike,
                expiration_date=expiration_date,
                delta=-0.50
            ))
            
            call_premium = self._estimate_option_premium(current_price, atm_strike, 'call', expiration_date)
            put_premium = self._estimate_option_premium(current_price, atm_strike, 'put', expiration_date)
            max_profit = (call_premium + put_premium) * 100
            max_loss = None  # Unlimited
        
        elif strategy_number == 10:
            # Long Strangle
            strategy_name = "Long Strangle"
            call_strike = self._find_strike_by_delta(symbol, current_price, 0.30, 'call')
            put_strike = self._find_strike_by_delta(symbol, current_price, 0.30, 'put')
            
            legs.append(OptionsLeg(
                symbol=self._build_options_symbol(symbol, expiration_date, 'call', call_strike),
                side="buy",
                quantity=1,
                option_type="call",
                strike=call_strike,
                expiration_date=expiration_date,
                delta=0.30
            ))
            
            legs.append(OptionsLeg(
                symbol=self._build_options_symbol(symbol, expiration_date, 'put', put_strike),
                side="buy",
                quantity=1,
                option_type="put",
                strike=put_strike,
                expiration_date=expiration_date,
                delta=-0.30
            ))
            
            call_premium = self._estimate_option_premium(current_price, call_strike, 'call', expiration_date)
            put_premium = self._estimate_option_premium(current_price, put_strike, 'put', expiration_date)
            max_loss = (call_premium + put_premium) * 100
            max_profit = None  # Unlimited on breakout
        
        elif strategy_number == 11:
            # Jade Lizard
            strategy_name = "Jade Lizard"
            put_strike = self._find_strike_by_delta(symbol, current_price, 0.30, 'put')
            short_call_strike = self._find_strike_by_delta(symbol, current_price, 0.30, 'call')
            long_call_strike = self._find_strike_by_delta(symbol, current_price, 0.15, 'call')
            
            legs.append(OptionsLeg(
                symbol=self._build_options_symbol(symbol, expiration_date, 'put', put_strike),
                side="sell",
                quantity=1,
                option_type="put",
                strike=put_strike,
                expiration_date=expiration_date,
                delta=-0.30
            ))
            
            legs.append(OptionsLeg(
                symbol=self._build_options_symbol(symbol, expiration_date, 'call', short_call_strike),
                side="sell",
                quantity=1,
                option_type="call",
                strike=short_call_strike,
                expiration_date=expiration_date,
                delta=0.30
            ))
            
            legs.append(OptionsLeg(
                symbol=self._build_options_symbol(symbol, expiration_date, 'call', long_call_strike),
                side="buy",
                quantity=1,
                option_type="call",
                strike=long_call_strike,
                expiration_date=expiration_date,
                delta=0.15
            ))
            
            put_premium = self._estimate_option_premium(current_price, put_strike, 'put', expiration_date)
            short_call_premium = self._estimate_option_premium(current_price, short_call_strike, 'call', expiration_date)
            long_call_premium = self._estimate_option_premium(current_price, long_call_strike, 'call', expiration_date)
            max_profit = (put_premium + short_call_premium - long_call_premium) * 100
            max_loss = (long_call_strike - short_call_strike) * 100  # Call spread width
        
        elif strategy_number == 12:
            # Reverse Jade Lizard
            strategy_name = "Reverse Jade Lizard"
            call_strike = self._find_strike_by_delta(symbol, current_price, 0.30, 'call')
            short_put_strike = self._find_strike_by_delta(symbol, current_price, 0.30, 'put')
            long_put_strike = self._find_strike_by_delta(symbol, current_price, 0.15, 'put')
            
            legs.append(OptionsLeg(
                symbol=self._build_options_symbol(symbol, expiration_date, 'call', call_strike),
                side="sell",
                quantity=1,
                option_type="call",
                strike=call_strike,
                expiration_date=expiration_date,
                delta=0.30
            ))
            
            legs.append(OptionsLeg(
                symbol=self._build_options_symbol(symbol, expiration_date, 'put', short_put_strike),
                side="sell",
                quantity=1,
                option_type="put",
                strike=short_put_strike,
                expiration_date=expiration_date,
                delta=-0.30
            ))
            
            legs.append(OptionsLeg(
                symbol=self._build_options_symbol(symbol, expiration_date, 'put', long_put_strike),
                side="buy",
                quantity=1,
                option_type="put",
                strike=long_put_strike,
                expiration_date=expiration_date,
                delta=-0.15
            ))
            
            call_premium = self._estimate_option_premium(current_price, call_strike, 'call', expiration_date)
            short_put_premium = self._estimate_option_premium(current_price, short_put_strike, 'put', expiration_date)
            long_put_premium = self._estimate_option_premium(current_price, long_put_strike, 'put', expiration_date)
            max_profit = (call_premium + short_put_premium - long_put_premium) * 100
            max_loss = (short_put_strike - long_put_strike) * 100  # Put spread width
        
        elif strategy_number == 13:
            # Covered Call (requires existing stock position)
            strategy_name = "Covered Call"
            call_strike = self._find_strike_by_delta(symbol, current_price, 0.30, 'call')
            
            # Note: This assumes we own 100 shares. In pure options mode, this may not apply
            legs.append(OptionsLeg(
                symbol=self._build_options_symbol(symbol, expiration_date, 'call', call_strike),
                side="sell",
                quantity=1,
                option_type="call",
                strike=call_strike,
                expiration_date=expiration_date,
                delta=0.30
            ))
            
            call_premium = self._estimate_option_premium(current_price, call_strike, 'call', expiration_date)
            max_profit = call_premium * 100
            max_loss = current_price * 100  # Stock goes to zero (minus premium)
        
        elif strategy_number == 14:
            # Cash-Secured Put
            strategy_name = "Cash-Secured Put"
            put_strike = self._find_strike_by_delta(symbol, current_price, 0.30, 'put')
            
            legs.append(OptionsLeg(
                symbol=self._build_options_symbol(symbol, expiration_date, 'put', put_strike),
                side="sell",
                quantity=1,
                option_type="put",
                strike=put_strike,
                expiration_date=expiration_date,
                delta=-0.30
            ))
            
            put_premium = self._estimate_option_premium(current_price, put_strike, 'put', expiration_date)
            max_profit = put_premium * 100
            max_loss = (put_strike * 100) - max_profit  # Assigned at strike
        
        # Position sizing
        if max_loss is not None:
            quantity = self._calculate_position_size(max_loss)
        else:
            # For undefined risk strategies, use conservative estimate
            quantity = 1
        
        bpr = self._calculate_buying_power_reduction(strategy_name, legs, quantity)
        
        order_request = OptionsOrderRequest(
            order_id=str(uuid.uuid4()),
            symbol=symbol,
            strategy_name=strategy_name,
            strategy_number=strategy_number,
            legs=legs,
            order_type="market",
            max_loss=max_loss or bpr,  # Use BPR as proxy if max_loss undefined
            max_profit=max_profit if max_profit > 0 else None,
            buying_power_reduction=bpr,
            hedge_engine_snapshot=hedge_snapshot,
            composer_signal=composer_signal,
            composer_confidence=composer_confidence,
            rationale=rationale,
            tags=["premium_collection", "theta_decay"]
        )
        
        return order_request
    
    # ============================================================================
    # CATEGORY 3: TIME SPREAD STRATEGIES (15-16)
    # ============================================================================
    
    def _build_time_spread_strategy(
        self,
        strategy_number: int,
        symbol: str,
        current_price: float,
        hedge_snapshot: Dict[str, float],
        composer_signal: str,
        composer_confidence: float,
        rationale: str
    ) -> OptionsOrderRequest:
        """Build strategies 15-16: Calendar and diagonal spreads"""
        
        legs: List[OptionsLeg] = []
        strategy_name = ""
        
        near_expiration = self._select_expiration(dte_min=21, dte_max=30)
        far_expiration = self._select_expiration(dte_min=60, dte_max=90)
        
        if strategy_number == 15:
            # Call Calendar
            strategy_name = "Call Calendar"
            strike = self._find_strike_by_delta(symbol, current_price, 0.50, 'call')
            
            # Sell near-term call
            legs.append(OptionsLeg(
                symbol=self._build_options_symbol(symbol, near_expiration, 'call', strike),
                side="sell",
                quantity=1,
                option_type="call",
                strike=strike,
                expiration_date=near_expiration,
                delta=0.50
            ))
            
            # Buy far-term call
            legs.append(OptionsLeg(
                symbol=self._build_options_symbol(symbol, far_expiration, 'call', strike),
                side="buy",
                quantity=1,
                option_type="call",
                strike=strike,
                expiration_date=far_expiration,
                delta=0.50
            ))
            
            near_premium = self._estimate_option_premium(current_price, strike, 'call', near_expiration)
            far_premium = self._estimate_option_premium(current_price, strike, 'call', far_expiration)
            max_loss = (far_premium - near_premium) * 100
            max_profit = None  # Undefined
        
        elif strategy_number == 16:
            # Put Calendar
            strategy_name = "Put Calendar"
            strike = self._find_strike_by_delta(symbol, current_price, 0.50, 'put')
            
            # Sell near-term put
            legs.append(OptionsLeg(
                symbol=self._build_options_symbol(symbol, near_expiration, 'put', strike),
                side="sell",
                quantity=1,
                option_type="put",
                strike=strike,
                expiration_date=near_expiration,
                delta=-0.50
            ))
            
            # Buy far-term put
            legs.append(OptionsLeg(
                symbol=self._build_options_symbol(symbol, far_expiration, 'put', strike),
                side="buy",
                quantity=1,
                option_type="put",
                strike=strike,
                expiration_date=far_expiration,
                delta=-0.50
            ))
            
            near_premium = self._estimate_option_premium(current_price, strike, 'put', near_expiration)
            far_premium = self._estimate_option_premium(current_price, strike, 'put', far_expiration)
            max_loss = (far_premium - near_premium) * 100
            max_profit = None
        
        quantity = self._calculate_position_size(max_loss)
        bpr = self._calculate_buying_power_reduction(strategy_name, legs, quantity)
        
        order_request = OptionsOrderRequest(
            order_id=str(uuid.uuid4()),
            symbol=symbol,
            strategy_name=strategy_name,
            strategy_number=strategy_number,
            legs=legs,
            order_type="market",
            max_loss=max_loss,
            max_profit=max_profit,
            buying_power_reduction=bpr,
            hedge_engine_snapshot=hedge_snapshot,
            composer_signal=composer_signal,
            composer_confidence=composer_confidence,
            rationale=rationale,
            tags=["time_spread", "vega_play"]
        )
        
        return order_request
    
    # ============================================================================
    # CATEGORY 4: IRON STRUCTURES (17-22)
    # ============================================================================
    
    def _build_iron_structure_strategy(
        self,
        strategy_number: int,
        symbol: str,
        current_price: float,
        hedge_snapshot: Dict[str, float],
        composer_signal: str,
        composer_confidence: float,
        rationale: str
    ) -> OptionsOrderRequest:
        """Build strategies 17-22: Iron condors, butterflies, defined-risk structures"""
        
        legs: List[OptionsLeg] = []
        strategy_name = ""
        max_loss = 0.0
        max_profit = 0.0
        
        expiration_date = self._select_expiration(dte_min=30, dte_max=45)
        
        if strategy_number == 17:
            # Iron Condor
            strategy_name = "Iron Condor"
            
            # Put spread
            short_put = self._find_strike_by_delta(symbol, current_price, 0.30, 'put')
            long_put = self._find_strike_by_delta(symbol, current_price, 0.16, 'put')
            
            # Call spread
            short_call = self._find_strike_by_delta(symbol, current_price, 0.30, 'call')
            long_call = self._find_strike_by_delta(symbol, current_price, 0.16, 'call')
            
            legs.extend([
                OptionsLeg(
                    symbol=self._build_options_symbol(symbol, expiration_date, 'put', short_put),
                    side="sell",
                    quantity=1,
                    option_type="put",
                    strike=short_put,
                    expiration_date=expiration_date,
                    delta=-0.30
                ),
                OptionsLeg(
                    symbol=self._build_options_symbol(symbol, expiration_date, 'put', long_put),
                    side="buy",
                    quantity=1,
                    option_type="put",
                    strike=long_put,
                    expiration_date=expiration_date,
                    delta=-0.16
                ),
                OptionsLeg(
                    symbol=self._build_options_symbol(symbol, expiration_date, 'call', short_call),
                    side="sell",
                    quantity=1,
                    option_type="call",
                    strike=short_call,
                    expiration_date=expiration_date,
                    delta=0.30
                ),
                OptionsLeg(
                    symbol=self._build_options_symbol(symbol, expiration_date, 'call', long_call),
                    side="buy",
                    quantity=1,
                    option_type="call",
                    strike=long_call,
                    expiration_date=expiration_date,
                    delta=0.16
                )
            ])
            
            put_width = short_put - long_put
            call_width = long_call - short_call
            max_spread_width = max(put_width, call_width)
            
            # Credit received (simplified)
            total_credit = (
                self._estimate_option_premium(current_price, short_put, 'put', expiration_date) +
                self._estimate_option_premium(current_price, short_call, 'call', expiration_date) -
                self._estimate_option_premium(current_price, long_put, 'put', expiration_date) -
                self._estimate_option_premium(current_price, long_call, 'call', expiration_date)
            ) * 100
            
            max_profit = total_credit
            max_loss = (max_spread_width * 100) - total_credit
        
        elif strategy_number == 18:
            # Broken-Wing Butterfly Call
            strategy_name = "Broken-Wing Butterfly Call"
            lower = self._find_strike_by_delta(symbol, current_price, 0.60, 'call')
            middle = self._find_strike_by_delta(symbol, current_price, 0.50, 'call')
            higher = self._find_strike_by_delta(symbol, current_price, 0.30, 'call')
            
            # Skew the higher strike wider
            higher = higher + (higher - middle) * 0.2
            
            legs.extend([
                OptionsLeg(
                    symbol=self._build_options_symbol(symbol, expiration_date, 'call', lower),
                    side="buy",
                    quantity=1,
                    option_type="call",
                    strike=lower,
                    expiration_date=expiration_date,
                    delta=0.60
                ),
                OptionsLeg(
                    symbol=self._build_options_symbol(symbol, expiration_date, 'call', middle),
                    side="sell",
                    quantity=2,
                    option_type="call",
                    strike=middle,
                    expiration_date=expiration_date,
                    delta=0.50
                ),
                OptionsLeg(
                    symbol=self._build_options_symbol(symbol, expiration_date, 'call', higher),
                    side="buy",
                    quantity=1,
                    option_type="call",
                    strike=higher,
                    expiration_date=expiration_date,
                    delta=0.30
                )
            ])
            
            # Simplified P&L calculation
            max_loss = (middle - lower) * 100
            max_profit = (higher - middle) * 100
        
        elif strategy_number == 19:
            # Broken-Wing Butterfly Put
            strategy_name = "Broken-Wing Butterfly Put"
            higher = self._find_strike_by_delta(symbol, current_price, 0.60, 'put')
            middle = self._find_strike_by_delta(symbol, current_price, 0.50, 'put')
            lower = self._find_strike_by_delta(symbol, current_price, 0.30, 'put')
            
            # Skew lower strike
            lower = lower - (middle - lower) * 0.2
            
            legs.extend([
                OptionsLeg(
                    symbol=self._build_options_symbol(symbol, expiration_date, 'put', higher),
                    side="buy",
                    quantity=1,
                    option_type="put",
                    strike=higher,
                    expiration_date=expiration_date,
                    delta=-0.60
                ),
                OptionsLeg(
                    symbol=self._build_options_symbol(symbol, expiration_date, 'put', middle),
                    side="sell",
                    quantity=2,
                    option_type="put",
                    strike=middle,
                    expiration_date=expiration_date,
                    delta=-0.50
                ),
                OptionsLeg(
                    symbol=self._build_options_symbol(symbol, expiration_date, 'put', lower),
                    side="buy",
                    quantity=1,
                    option_type="put",
                    strike=lower,
                    expiration_date=expiration_date,
                    delta=-0.30
                )
            ])
            
            max_loss = (higher - middle) * 100
            max_profit = (middle - lower) * 100
        
        elif strategy_number == 20:
            # Long Call Butterfly
            strategy_name = "Long Call Butterfly"
            lower = self._find_strike_by_delta(symbol, current_price, 0.60, 'call')
            middle = self._find_strike_by_delta(symbol, current_price, 0.50, 'call')
            higher = self._find_strike_by_delta(symbol, current_price, 0.40, 'call')
            
            legs.extend([
                OptionsLeg(
                    symbol=self._build_options_symbol(symbol, expiration_date, 'call', lower),
                    side="buy",
                    quantity=1,
                    option_type="call",
                    strike=lower,
                    expiration_date=expiration_date,
                    delta=0.60
                ),
                OptionsLeg(
                    symbol=self._build_options_symbol(symbol, expiration_date, 'call', middle),
                    side="sell",
                    quantity=2,
                    option_type="call",
                    strike=middle,
                    expiration_date=expiration_date,
                    delta=0.50
                ),
                OptionsLeg(
                    symbol=self._build_options_symbol(symbol, expiration_date, 'call', higher),
                    side="buy",
                    quantity=1,
                    option_type="call",
                    strike=higher,
                    expiration_date=expiration_date,
                    delta=0.40
                )
            ])
            
            net_debit = (
                self._estimate_option_premium(current_price, lower, 'call', expiration_date) +
                self._estimate_option_premium(current_price, higher, 'call', expiration_date) -
                2 * self._estimate_option_premium(current_price, middle, 'call', expiration_date)
            ) * 100
            
            max_loss = abs(net_debit)
            max_profit = ((middle - lower) * 100) - max_loss
        
        elif strategy_number == 21:
            # Long Put Butterfly
            strategy_name = "Long Put Butterfly"
            higher = self._find_strike_by_delta(symbol, current_price, 0.60, 'put')
            middle = self._find_strike_by_delta(symbol, current_price, 0.50, 'put')
            lower = self._find_strike_by_delta(symbol, current_price, 0.40, 'put')
            
            legs.extend([
                OptionsLeg(
                    symbol=self._build_options_symbol(symbol, expiration_date, 'put', higher),
                    side="buy",
                    quantity=1,
                    option_type="put",
                    strike=higher,
                    expiration_date=expiration_date,
                    delta=-0.60
                ),
                OptionsLeg(
                    symbol=self._build_options_symbol(symbol, expiration_date, 'put', middle),
                    side="sell",
                    quantity=2,
                    option_type="put",
                    strike=middle,
                    expiration_date=expiration_date,
                    delta=-0.50
                ),
                OptionsLeg(
                    symbol=self._build_options_symbol(symbol, expiration_date, 'put', lower),
                    side="buy",
                    quantity=1,
                    option_type="put",
                    strike=lower,
                    expiration_date=expiration_date,
                    delta=-0.40
                )
            ])
            
            net_debit = (
                self._estimate_option_premium(current_price, higher, 'put', expiration_date) +
                self._estimate_option_premium(current_price, lower, 'put', expiration_date) -
                2 * self._estimate_option_premium(current_price, middle, 'put', expiration_date)
            ) * 100
            
            max_loss = abs(net_debit)
            max_profit = ((higher - middle) * 100) - max_loss
        
        elif strategy_number == 22:
            # Double Diagonal
            strategy_name = "Double Diagonal"
            
            near_expiration = self._select_expiration(dte_min=21, dte_max=30)
            far_expiration = self._select_expiration(dte_min=60, dte_max=90)
            
            # Near-term short strangle
            near_call = self._find_strike_by_delta(symbol, current_price, 0.30, 'call')
            near_put = self._find_strike_by_delta(symbol, current_price, 0.30, 'put')
            
            # Far-term long strangle
            far_call = self._find_strike_by_delta(symbol, current_price, 0.30, 'call')
            far_put = self._find_strike_by_delta(symbol, current_price, 0.30, 'put')
            
            legs.extend([
                OptionsLeg(
                    symbol=self._build_options_symbol(symbol, near_expiration, 'call', near_call),
                    side="sell",
                    quantity=1,
                    option_type="call",
                    strike=near_call,
                    expiration_date=near_expiration,
                    delta=0.30
                ),
                OptionsLeg(
                    symbol=self._build_options_symbol(symbol, near_expiration, 'put', near_put),
                    side="sell",
                    quantity=1,
                    option_type="put",
                    strike=near_put,
                    expiration_date=near_expiration,
                    delta=-0.30
                ),
                OptionsLeg(
                    symbol=self._build_options_symbol(symbol, far_expiration, 'call', far_call),
                    side="buy",
                    quantity=1,
                    option_type="call",
                    strike=far_call,
                    expiration_date=far_expiration,
                    delta=0.30
                ),
                OptionsLeg(
                    symbol=self._build_options_symbol(symbol, far_expiration, 'put', far_put),
                    side="buy",
                    quantity=1,
                    option_type="put",
                    strike=far_put,
                    expiration_date=far_expiration,
                    delta=-0.30
                )
            ])
            
            # Complex P&L - use conservative estimate
            max_loss = 500.0  # Placeholder
            max_profit = None
        
        quantity = self._calculate_position_size(max_loss)
        bpr = self._calculate_buying_power_reduction(strategy_name, legs, quantity)
        
        order_request = OptionsOrderRequest(
            order_id=str(uuid.uuid4()),
            symbol=symbol,
            strategy_name=strategy_name,
            strategy_number=strategy_number,
            legs=legs,
            order_type="market",
            max_loss=max_loss,
            max_profit=max_profit,
            buying_power_reduction=bpr,
            hedge_engine_snapshot=hedge_snapshot,
            composer_signal=composer_signal,
            composer_confidence=composer_confidence,
            rationale=rationale,
            tags=["iron_structure", "defined_risk"]
        )
        
        return order_request
    
    # ============================================================================
    # CATEGORY 5: SYNTHETIC STRATEGIES (23-24)
    # ============================================================================
    
    def _build_synthetic_strategy(
        self,
        strategy_number: int,
        symbol: str,
        current_price: float,
        hedge_snapshot: Dict[str, float],
        composer_signal: str,
        composer_confidence: float,
        rationale: str
    ) -> OptionsOrderRequest:
        """Build strategies 23-24: Risk reversals (synthetic positions)"""
        
        legs: List[OptionsLeg] = []
        strategy_name = ""
        
        expiration_date = self._select_expiration(dte_min=30, dte_max=45)
        
        if strategy_number == 23:
            # Risk Reversal (Synthetic Long)
            strategy_name = "Risk Reversal (Synthetic Long)"
            put_strike = self._find_strike_by_delta(symbol, current_price, 0.25, 'put')
            call_strike = self._find_strike_by_delta(symbol, current_price, 0.25, 'call')
            
            legs.append(OptionsLeg(
                symbol=self._build_options_symbol(symbol, expiration_date, 'put', put_strike),
                side="sell",
                quantity=1,
                option_type="put",
                strike=put_strike,
                expiration_date=expiration_date,
                delta=-0.25
            ))
            
            legs.append(OptionsLeg(
                symbol=self._build_options_symbol(symbol, expiration_date, 'call', call_strike),
                side="buy",
                quantity=1,
                option_type="call",
                strike=call_strike,
                expiration_date=expiration_date,
                delta=0.25
            ))
            
            put_premium = self._estimate_option_premium(current_price, put_strike, 'put', expiration_date)
            call_premium = self._estimate_option_premium(current_price, call_strike, 'call', expiration_date)
            net_cost = (call_premium - put_premium) * 100
            
            max_loss = None  # Unlimited on downside
            max_profit = None  # Unlimited on upside
        
        elif strategy_number == 24:
            # Risk Reversal (Synthetic Short)
            strategy_name = "Risk Reversal (Synthetic Short)"
            put_strike = self._find_strike_by_delta(symbol, current_price, 0.25, 'put')
            call_strike = self._find_strike_by_delta(symbol, current_price, 0.25, 'call')
            
            legs.append(OptionsLeg(
                symbol=self._build_options_symbol(symbol, expiration_date, 'put', put_strike),
                side="buy",
                quantity=1,
                option_type="put",
                strike=put_strike,
                expiration_date=expiration_date,
                delta=-0.25
            ))
            
            legs.append(OptionsLeg(
                symbol=self._build_options_symbol(symbol, expiration_date, 'call', call_strike),
                side="sell",
                quantity=1,
                option_type="call",
                strike=call_strike,
                expiration_date=expiration_date,
                delta=0.25
            ))
            
            put_premium = self._estimate_option_premium(current_price, put_strike, 'put', expiration_date)
            call_premium = self._estimate_option_premium(current_price, call_strike, 'call', expiration_date)
            net_cost = (put_premium - call_premium) * 100
            
            max_loss = None  # Unlimited on upside
            max_profit = None  # Unlimited on downside
        
        # Conservative sizing for undefined risk
        quantity = 1
        bpr = self._calculate_buying_power_reduction(strategy_name, legs, quantity)
        
        order_request = OptionsOrderRequest(
            order_id=str(uuid.uuid4()),
            symbol=symbol,
            strategy_name=strategy_name,
            strategy_number=strategy_number,
            legs=legs,
            order_type="market",
            max_loss=bpr,  # Use BPR as proxy
            max_profit=None,
            buying_power_reduction=bpr,
            hedge_engine_snapshot=hedge_snapshot,
            composer_signal=composer_signal,
            composer_confidence=composer_confidence,
            rationale=rationale,
            tags=["synthetic", "directional"]
        )
        
        return order_request
    
    # ============================================================================
    # CATEGORY 6: AGGRESSIVE STRATEGIES (25-28)
    # ============================================================================
    
    def _build_aggressive_strategy(
        self,
        strategy_number: int,
        symbol: str,
        current_price: float,
        hedge_snapshot: Dict[str, float],
        composer_signal: str,
        composer_confidence: float,
        rationale: str
    ) -> OptionsOrderRequest:
        """Build strategies 25-28: Aggressive premium selling and hedging"""
        
        legs: List[OptionsLeg] = []
        strategy_name = ""
        max_loss = None
        max_profit = 0.0
        
        expiration_date = self._select_expiration(dte_min=21, dte_max=30)
        
        if strategy_number == 25:
            # Short Guts
            strategy_name = "Short Guts"
            call_strike = self._find_strike_by_delta(symbol, current_price, 0.70, 'call')
            put_strike = self._find_strike_by_delta(symbol, current_price, 0.70, 'put')
            
            legs.append(OptionsLeg(
                symbol=self._build_options_symbol(symbol, expiration_date, 'call', call_strike),
                side="sell",
                quantity=1,
                option_type="call",
                strike=call_strike,
                expiration_date=expiration_date,
                delta=0.70
            ))
            
            legs.append(OptionsLeg(
                symbol=self._build_options_symbol(symbol, expiration_date, 'put', put_strike),
                side="sell",
                quantity=1,
                option_type="put",
                strike=put_strike,
                expiration_date=expiration_date,
                delta=-0.70
            ))
            
            call_premium = self._estimate_option_premium(current_price, call_strike, 'call', expiration_date)
            put_premium = self._estimate_option_premium(current_price, put_strike, 'put', expiration_date)
            max_profit = (call_premium + put_premium) * 100
            max_loss = None  # Unlimited
        
        elif strategy_number == 26:
            # Naked Call (PAPER ONLY)
            strategy_name = "Naked Call (PAPER ONLY)"
            call_strike = self._find_strike_by_delta(symbol, current_price, 0.25, 'call')
            
            if not self.paper_trading:
                raise ValueError("Strategy 26 (Naked Call) only allowed in paper trading mode")
            
            legs.append(OptionsLeg(
                symbol=self._build_options_symbol(symbol, expiration_date, 'call', call_strike),
                side="sell",
                quantity=1,
                option_type="call",
                strike=call_strike,
                expiration_date=expiration_date,
                delta=0.25
            ))
            
            call_premium = self._estimate_option_premium(current_price, call_strike, 'call', expiration_date)
            max_profit = call_premium * 100
            max_loss = None  # Unlimited
        
        elif strategy_number == 27:
            # Naked Put (Wheel Continuation)
            strategy_name = "Naked Put (Wheel)"
            put_strike = self._find_strike_by_delta(symbol, current_price, 0.30, 'put')
            
            legs.append(OptionsLeg(
                symbol=self._build_options_symbol(symbol, expiration_date, 'put', put_strike),
                side="sell",
                quantity=1,
                option_type="put",
                strike=put_strike,
                expiration_date=expiration_date,
                delta=-0.30
            ))
            
            put_premium = self._estimate_option_premium(current_price, put_strike, 'put', expiration_date)
            max_profit = put_premium * 100
            max_loss = (put_strike * 100) - max_profit
        
        elif strategy_number == 28:
            # Delta-Neutral Adjustment
            strategy_name = "Delta-Neutral Adjustment"
            
            # This is a hedging strategy - would need existing position context
            # For now, create a simple delta hedge using ATM straddle
            atm_strike = self._find_strike_by_delta(symbol, current_price, 0.50, 'call')
            
            # Placeholder: buy shares or futures to neutralize delta
            # In practice, this would calculate position delta and add offsetting delta
            legs.append(OptionsLeg(
                symbol=self._build_options_symbol(symbol, expiration_date, 'call', atm_strike),
                side="buy",
                quantity=1,
                option_type="call",
                strike=atm_strike,
                expiration_date=expiration_date,
                delta=0.50
            ))
            
            max_loss = 500.0  # Placeholder
            max_profit = None
        
        quantity = 1  # Conservative for aggressive strategies
        bpr = self._calculate_buying_power_reduction(strategy_name, legs, quantity)
        
        order_request = OptionsOrderRequest(
            order_id=str(uuid.uuid4()),
            symbol=symbol,
            strategy_name=strategy_name,
            strategy_number=strategy_number,
            legs=legs,
            order_type="market",
            max_loss=max_loss or bpr,
            max_profit=max_profit if max_profit > 0 else None,
            buying_power_reduction=bpr,
            hedge_engine_snapshot=hedge_snapshot,
            composer_signal=composer_signal,
            composer_confidence=composer_confidence,
            rationale=rationale,
            tags=["aggressive", "high_risk"]
        )
        
        return order_request
    
    # ============================================================================
    # HELPER METHODS
    # ============================================================================
    
    def _select_expiration(self, dte_min: int = 7, dte_max: int = 45) -> str:
        """
        Select expiration date within DTE range.
        
        For now, uses simple calculation. Production should query available expirations.
        """
        target_dte = (dte_min + dte_max) // 2
        expiration = datetime.now() + timedelta(days=target_dte)
        
        # Round to next Friday (typical options expiration)
        days_until_friday = (4 - expiration.weekday()) % 7
        if days_until_friday == 0:
            days_until_friday = 7
        expiration = expiration + timedelta(days=days_until_friday)
        
        return expiration.strftime("%Y-%m-%d")
    
    def _find_strike_by_delta(
        self,
        symbol: str,
        current_price: float,
        target_delta: float,
        option_type: str
    ) -> float:
        """
        Find strike price closest to target delta.
        
        Uses simplified model. Production should use real options chain + Greeks.
        """
        # Determine strike increment
        if symbol in ['SPY', 'QQQ', 'IWM', 'DIA']:
            increment = 1.0
        elif symbol in ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA']:
            increment = 5.0
        elif current_price < 50:
            increment = 0.50
        elif current_price < 100:
            increment = 1.0
        else:
            increment = 5.0
        
        # Approximate strike from delta
        if option_type == 'call':
            # For calls: higher delta = more ITM = lower strike
            if abs(target_delta) > 0.7:  # ITM
                offset = -0.05 * current_price
            elif abs(target_delta) > 0.45:  # ATM
                offset = 0.0
            else:  # OTM
                offset = 0.05 * current_price * (1 - abs(target_delta) / 0.5)
        else:  # put
            # For puts: higher delta = more ITM = higher strike
            if abs(target_delta) > 0.7:  # ITM
                offset = 0.05 * current_price
            elif abs(target_delta) > 0.45:  # ATM
                offset = 0.0
            else:  # OTM
                offset = -0.05 * current_price * (1 - abs(target_delta) / 0.5)
        
        strike = current_price + offset
        strike = round(strike / increment) * increment
        
        return strike
    
    def _build_options_symbol(
        self,
        underlying: str,
        expiration: str,
        option_type: str,
        strike: float
    ) -> str:
        """
        Build Alpaca options symbol format.
        
        Format: "SYMBOL  YYMMDDX00000000"
        Example: "AAPL  251219C00250000"
        """
        exp_date = datetime.strptime(expiration, "%Y-%m-%d")
        yymmdd = exp_date.strftime("%y%m%d")
        opt_type = "C" if option_type.lower() == "call" else "P"
        strike_str = f"{int(strike * 1000):08d}"
        underlying_padded = underlying.ljust(6)
        
        return f"{underlying_padded}{yymmdd}{opt_type}{strike_str}"
    
    def _estimate_option_premium(
        self,
        current_price: float,
        strike: float,
        option_type: str,
        expiration_date: str,
        iv: float = 0.30
    ) -> float:
        """
        Estimate option premium using simplified Black-Scholes.
        
        Production should use real market data and accurate Greeks calculation.
        """
        exp_dt = datetime.strptime(expiration_date, "%Y-%m-%d")
        dte = (exp_dt - datetime.now()).days
        time_to_expiry = dte / 365.0
        
        # Intrinsic value
        if option_type == 'call':
            intrinsic = max(0, current_price - strike)
        else:
            intrinsic = max(0, strike - current_price)
        
        # Time value (simplified)
        time_value = current_price * iv * math.sqrt(time_to_expiry)
        
        # Moneyness adjustment
        moneyness = abs(current_price - strike) / current_price
        time_value *= math.exp(-moneyness * 2)
        
        return intrinsic + time_value
    
    def _calculate_position_size(self, max_loss: float) -> int:
        """
        Calculate number of contracts based on risk percentage.
        
        Risk 1-2% of portfolio per trade.
        """
        target_risk = self.portfolio_value * (self.risk_per_trade_pct / 100.0)
        contracts = int(target_risk / max_loss)
        return max(1, contracts)
    
    def _calculate_buying_power_reduction(
        self,
        strategy_name: str,
        legs: List[OptionsLeg],
        quantity: int
    ) -> float:
        """
        Calculate buying power reduction for strategy.
        
        Uses conservative estimates. Production should use broker's margin requirements.
        """
        # Simplified BPR calculation
        if "Spread" in strategy_name or "Iron" in strategy_name:
            # Defined risk - BPR = max loss
            max_leg_value = max([leg.strike for leg in legs]) - min([leg.strike for leg in legs])
            bpr = max_leg_value * 100 * quantity
        elif "Strangle" in strategy_name or "Straddle" in strategy_name:
            # Undefined risk - use notional
            strikes = [leg.strike for leg in legs]
            bpr = max(strikes) * 100 * quantity * 0.2  # 20% of notional
        else:
            # Generic: 20% of portfolio max
            bpr = self.portfolio_value * 0.05 * quantity
        
        return bpr
