"""
Options Trading Validation Workflow
====================================

This script demonstrates the complete workflow for:
1. Using options Greeks to predict stock movement (DHPE framework)
2. Backtesting predictions against actual stock prices
3. Trading options based on validated predictions

Workflow:
---------
STEP 1: Fetch options chain (Greeks: Gamma, Vanna, Charm)
STEP 2: Calculate energy states (DHPE framework)
STEP 3: Predict stock movement (to low-energy zones)
STEP 4: Backtest: Did stock actually move there?
STEP 5: If accurate → Trade options on future predictions

Author: Super Gnosis Development Team
Version: 3.0.0
"""

from datetime import datetime, date, timedelta
from typing import List, Dict
import polars as pl
import numpy as np
from loguru import logger

# Super Gnosis v3.0 Engines
from engines.inputs.yahoo_options_adapter import YahooOptionsAdapter
from engines.inputs.yfinance_adapter import YFinanceAdapter
from engines.inputs.dix_gex_adapter import DIXGEXAdapter
from engines.hedge.universal_energy_interpreter import (
    UniversalEnergyInterpreter,
    GreekExposure,
    EnergyState
)
from engines.backtest.universal_backtest_engine import UniversalBacktestEngine
from engines.liquidity.universal_liquidity_interpreter import UniversalLiquidityInterpreter


class OptionsValidationWorkflow:
    """
    Complete workflow for validating DHPE model and trading options.
    
    Process:
    1. Fetch options chain → Get Greeks
    2. Calculate energy states → Predict stock moves
    3. Backtest → Validate predictions
    4. Trade options → Profit from validated predictions
    """
    
    def __init__(self):
        """Initialize all required components."""
        
        # Data sources
        self.options_adapter = YahooOptionsAdapter()  # FREE options data
        self.stock_adapter = YFinanceAdapter()        # FREE stock data
        self.dix_gex_adapter = DIXGEXAdapter()        # DIX/GEX market sentiment
        
        # DHPE Engine
        self.energy_engine = UniversalEnergyInterpreter(
            risk_free_rate=0.05,
            use_vollib=True  # Use precise Greeks
        )
        
        # Backtest Engine
        self.backtest_engine = UniversalBacktestEngine()
        
        # Liquidity Engine (filters illiquid options)
        self.liquidity_engine = UniversalLiquidityInterpreter(
            impact_scaling=1.0,
            slippage_scaling=1.0
        )
        
        logger.info("✅ Options Validation Workflow initialized")
    
    
    # ========================================================================
    # STEP 1: FETCH OPTIONS DATA (Greeks)
    # ========================================================================
    
    def fetch_options_chain(
        self,
        symbol: str,
        days_to_expiry: int = 30,
        filter_liquid: bool = True,
        min_liquidity_score: float = 0.6,
        min_open_interest: int = 100,
        max_spread_pct: float = 5.0,
        min_volume: int = 50
    ) -> pl.DataFrame:
        """
        Fetch options chain with Greeks and liquidity filtering.
        
        Args:
            symbol: Stock symbol (e.g., "SPY", "AAPL")
            days_to_expiry: Target days to expiration
            filter_liquid: If True, filter to only liquid options
            min_liquidity_score: Minimum liquidity score (0-1)
            min_open_interest: Minimum open interest
            max_spread_pct: Maximum bid-ask spread %
            min_volume: Minimum daily volume
        
        Returns:
            DataFrame with strikes, Greeks, OI, and liquidity metrics
        """
        logger.info(f"📊 Fetching options chain for {symbol} (~{days_to_expiry} DTE)")
        
        # Fetch from Yahoo Finance (FREE, 15-min delay)
        options_chain = self.options_adapter.fetch_options_chain(
            symbol=symbol,
            min_days_to_expiry=days_to_expiry - 7,
            max_days_to_expiry=days_to_expiry + 7
        )
        
        logger.info(f"   Retrieved {len(options_chain)} option contracts")
        
        # Apply liquidity filtering (CRITICAL - prevents illiquid trades)
        if filter_liquid:
            logger.info(f"   🔍 Applying liquidity filters...")
            options_chain = self.liquidity_engine.filter_liquid_options(
                options_chain,
                min_liquidity_score=min_liquidity_score,
                min_open_interest=min_open_interest,
                max_spread_pct=max_spread_pct,
                min_volume=min_volume
            )
            logger.info(f"   ✅ Filtered to {len(options_chain)} liquid options")
        
        return options_chain
    
    def fetch_dix_gex_context(
        self,
        lookback_days: int = 30
    ) -> Dict[str, any]:
        """
        Fetch DIX/GEX market sentiment data.
        
        DIX (Dark Index):
        - Measures institutional dark pool buying pressure
        - Higher DIX = Institutions accumulating (bullish)
        - Lower DIX = Institutions distributing (bearish)
        
        GEX (Gamma Exposure):
        - Measures net gamma from options market makers
        - Positive GEX = Low volatility, range-bound
        - Negative GEX = High volatility, explosive moves
        
        Args:
            lookback_days: Days of historical data to fetch
        
        Returns:
            Dict with current DIX/GEX values and interpretation
        """
        logger.info(f"📊 Fetching DIX/GEX market sentiment...")
        
        try:
            # Fetch DIX/GEX data
            df = self.dix_gex_adapter.fetch_dix_gex(lookback_days=lookback_days)
            
            if len(df) == 0:
                logger.warning("   ⚠️  No DIX/GEX data available")
                return {
                    'dix': None,
                    'gex': None,
                    'interpretations': {},
                    'data_available': False
                }
            
            # Get current values
            current_dix = df['dix'][-1] if 'dix' in df.columns else None
            current_gex = df['gex'][-1] if 'gex' in df.columns else None
            
            # Get interpretations
            if current_dix is not None and current_gex is not None:
                interpretations = self.dix_gex_adapter.interpret_dix_gex(
                    current_dix,
                    current_gex
                )
            else:
                interpretations = {}
            
            logger.info(f"   Current DIX: {current_dix:.3f if current_dix else 'N/A'}")
            logger.info(f"   Current GEX: ${current_gex:.2f}B" if current_gex else "   Current GEX: N/A")
            
            if interpretations:
                logger.info(f"   Signal: {interpretations.get('combined', 'Unknown')}")
            
            return {
                'dix': current_dix,
                'gex': current_gex,
                'dix_avg': df['dix'].mean() if 'dix' in df.columns else None,
                'gex_avg': df['gex'].mean() if 'gex' in df.columns else None,
                'interpretations': interpretations,
                'historical_data': df,
                'data_available': True,
                'source': df['source'][0] if 'source' in df.columns else 'unknown'
            }
            
        except Exception as e:
            logger.error(f"   Failed to fetch DIX/GEX: {e}")
            return {
                'dix': None,
                'gex': None,
                'interpretations': {},
                'data_available': False
            }
    
    
    # ========================================================================
    # STEP 2: CALCULATE ENERGY STATES (DHPE Framework)
    # ========================================================================
    
    def calculate_energy_state(
        self,
        symbol: str,
        options_chain: pl.DataFrame,
        spot_price: float,
        vix: float
    ) -> EnergyState:
        """
        Calculate energy state from options Greeks.
        
        This is the CORE of the DHPE framework:
        - Greeks → Force fields
        - Force fields → Energy landscape
        - Energy landscape → Predicted stock movement
        
        Args:
            symbol: Stock symbol
            options_chain: Options chain DataFrame
            spot_price: Current stock price
            vix: VIX level
        
        Returns:
            EnergyState with predictions
        """
        logger.info(f"🔬 Calculating energy state for {symbol} @ ${spot_price:.2f}")
        
        # Convert options chain to GreekExposure objects
        exposures = self._convert_to_exposures(options_chain)
        
        # Calculate days to expiry
        expiry_date = options_chain['expiry'][0]
        if isinstance(expiry_date, str):
            expiry_date = datetime.fromisoformat(expiry_date).date()
        days_to_expiry = (expiry_date - date.today()).days
        
        # Calculate energy state using DHPE framework
        energy_state = self.energy_engine.interpret(
            spot=spot_price,
            exposures=exposures,
            vix=vix,
            time_to_expiry=days_to_expiry,
            dealer_sign=-1.0,  # Dealers typically short gamma
            move_size=0.01     # Calculate for 1% moves
        )
        
        # Log predictions
        logger.info(f"   Regime: {energy_state.regime}")
        logger.info(f"   Movement Energy: {energy_state.movement_energy:.2f}")
        logger.info(f"   Energy Up: {energy_state.movement_energy_up:.2f}")
        logger.info(f"   Energy Down: {energy_state.movement_energy_down:.2f}")
        logger.info(f"   Asymmetry: {energy_state.energy_asymmetry:.2f}")
        
        # Interpret prediction
        if energy_state.energy_asymmetry > 0:
            logger.info(f"   💡 PREDICTION: Easier to move UP (lower resistance)")
        elif energy_state.energy_asymmetry < 0:
            logger.info(f"   💡 PREDICTION: Easier to move DOWN (lower resistance)")
        else:
            logger.info(f"   💡 PREDICTION: Balanced (no directional bias)")
        
        return energy_state
    
    
    # ========================================================================
    # STEP 3: IDENTIFY PREDICTED PRICE TARGETS
    # ========================================================================
    
    def identify_price_targets(
        self,
        spot_price: float,
        energy_state: EnergyState,
        options_chain: pl.DataFrame
    ) -> Dict[str, float]:
        """
        Identify specific price targets based on energy landscape.
        
        Finds:
        - Support levels (low energy zones, price attracted)
        - Resistance levels (high energy zones, price repelled)
        
        Args:
            spot_price: Current stock price
            energy_state: Calculated energy state
            options_chain: Options chain with strike data
        
        Returns:
            Dict with support/resistance targets
        """
        logger.info(f"🎯 Identifying price targets from energy landscape")
        
        # Get strikes sorted by total gamma
        strikes_df = options_chain.group_by('strike').agg([
            pl.col('call_gamma').sum().alias('total_call_gamma'),
            pl.col('put_gamma').sum().alias('total_put_gamma'),
            pl.col('call_oi').sum().alias('total_call_oi'),
            pl.col('put_oi').sum().alias('total_put_oi')
        ])
        
        strikes_df = strikes_df.with_columns([
            (pl.col('total_call_gamma') + pl.col('total_put_gamma')).alias('total_gamma')
        ]).sort('strike')
        
        # Find high gamma strikes (dealers pinned)
        strikes_sorted_by_gamma = strikes_df.sort('total_gamma', descending=True)
        
        # Support (below spot, high gamma)
        support_strikes = strikes_sorted_by_gamma.filter(
            pl.col('strike') < spot_price
        ).head(3)
        
        # Resistance (above spot, high gamma)
        resistance_strikes = strikes_sorted_by_gamma.filter(
            pl.col('strike') > spot_price
        ).head(3)
        
        targets = {
            'current_price': spot_price,
            'support_1': support_strikes['strike'][0] if len(support_strikes) > 0 else spot_price * 0.98,
            'support_2': support_strikes['strike'][1] if len(support_strikes) > 1 else spot_price * 0.96,
            'resistance_1': resistance_strikes['strike'][0] if len(resistance_strikes) > 0 else spot_price * 1.02,
            'resistance_2': resistance_strikes['strike'][1] if len(resistance_strikes) > 1 else spot_price * 1.04,
        }
        
        logger.info(f"   Current: ${targets['current_price']:.2f}")
        logger.info(f"   Support 1: ${targets['support_1']:.2f}")
        logger.info(f"   Support 2: ${targets['support_2']:.2f}")
        logger.info(f"   Resistance 1: ${targets['resistance_1']:.2f}")
        logger.info(f"   Resistance 2: ${targets['resistance_2']:.2f}")
        
        return targets
    
    
    # ========================================================================
    # STEP 4: BACKTEST - VALIDATE PREDICTIONS
    # ========================================================================
    
    def backtest_predictions(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        lookback_days: int = 60
    ) -> Dict[str, float]:
        """
        Backtest the DHPE model predictions against actual stock moves.
        
        Process:
        1. For each historical day:
           a. Fetch options chain (Greeks)
           b. Calculate energy state → Predict direction
           c. Check if stock actually moved in predicted direction
        2. Calculate accuracy metrics
        
        Args:
            symbol: Stock symbol
            start_date: Backtest start date
            end_date: Backtest end date
            lookback_days: Days to look ahead for validation
        
        Returns:
            Dict with accuracy metrics
        """
        logger.info(f"📈 Backtesting DHPE predictions for {symbol}")
        logger.info(f"   Period: {start_date} to {end_date}")
        
        # Fetch historical stock prices
        stock_data = self.stock_adapter.fetch_ohlcv(
            symbol=symbol,
            period="1y",  # Get full year of data
            interval="1d"
        )
        
        # Filter to backtest period
        stock_data = stock_data.filter(
            (pl.col('timestamp') >= start_date.isoformat()) &
            (pl.col('timestamp') <= end_date.isoformat())
        )
        
        predictions_correct = 0
        total_predictions = 0
        
        # For each day in backtest period
        for i in range(len(stock_data) - lookback_days):
            current_day = stock_data[i]
            current_price = current_day['close']
            
            # Get future price (N days ahead)
            future_day = stock_data[i + lookback_days]
            future_price = future_day['close']
            actual_move = future_price - current_price
            
            # Fetch options chain for this day (SIMPLIFIED - in reality, need historical options)
            # For demo, we'll use current options and adjust
            logger.info(f"   Day {i+1}: Price ${current_price:.2f}")
            
            # NOTE: This is simplified. In production, you'd need historical options data
            # For now, we'll use current options chain as a proxy
            try:
                options_chain = self.fetch_options_chain(symbol, days_to_expiry=30)
                vix = 15.0  # Simplified, should fetch historical VIX
                
                energy_state = self.calculate_energy_state(
                    symbol=symbol,
                    options_chain=options_chain,
                    spot_price=current_price,
                    vix=vix
                )
                
                # Predict direction from energy asymmetry
                predicted_direction = "up" if energy_state.energy_asymmetry > 0 else "down"
                actual_direction = "up" if actual_move > 0 else "down"
                
                # Check if prediction was correct
                if predicted_direction == actual_direction:
                    predictions_correct += 1
                
                total_predictions += 1
                
                logger.info(f"      Predicted: {predicted_direction}, Actual: {actual_direction}")
                
            except Exception as e:
                logger.warning(f"   Skipping day {i+1}: {e}")
                continue
        
        # Calculate accuracy
        accuracy = predictions_correct / total_predictions if total_predictions > 0 else 0.0
        
        results = {
            'total_predictions': total_predictions,
            'correct_predictions': predictions_correct,
            'accuracy': accuracy,
            'edge_over_random': accuracy - 0.5  # Edge over coin flip
        }
        
        logger.info(f"\n📊 BACKTEST RESULTS:")
        logger.info(f"   Total Predictions: {total_predictions}")
        logger.info(f"   Correct: {predictions_correct}")
        logger.info(f"   Accuracy: {accuracy:.1%}")
        logger.info(f"   Edge over Random: {results['edge_over_random']:.1%}")
        
        if accuracy > 0.55:
            logger.info(f"   ✅ MODEL IS PREDICTIVE! (>55% accuracy)")
        else:
            logger.info(f"   ⚠️  Model needs improvement (<55% accuracy)")
        
        return results
    
    
    # ========================================================================
    # STEP 5: GENERATE OPTIONS TRADE RECOMMENDATIONS
    # ========================================================================
    
    def generate_options_trades(
        self,
        symbol: str,
        energy_state: EnergyState,
        price_targets: Dict[str, float],
        options_chain: pl.DataFrame,
        risk_capital: float = 1000.0
    ) -> List[Dict]:
        """
        Generate specific options trade recommendations.
        
        Based on validated DHPE predictions, recommend:
        - Which options to buy/sell
        - Strike prices
        - Expiration dates
        - Position sizes
        
        NOTE: options_chain should already be filtered for liquidity
        via fetch_options_chain() with filter_liquid=True
        
        Args:
            symbol: Stock symbol
            energy_state: Calculated energy state
            price_targets: Support/resistance levels
            options_chain: Current options chain (liquidity filtered)
            risk_capital: Capital to risk per trade
        
        Returns:
            List of trade recommendations
        """
        logger.info(f"💰 Generating options trade recommendations")
        
        # Verify options chain has liquidity metrics
        if 'liquidity_score' not in options_chain.columns:
            logger.warning("⚠️  Options chain missing liquidity metrics! Re-filtering...")
            options_chain = self.liquidity_engine.interpret_options_liquidity(options_chain)
        
        trades = []
        current_price = price_targets['current_price']
        
        # Check if we have any liquid options to trade
        if len(options_chain) == 0:
            logger.warning("⚠️  NO LIQUID OPTIONS AVAILABLE! Cannot generate trades.")
            return trades
        
        # Strategy 1: Directional play based on energy asymmetry
        if abs(energy_state.energy_asymmetry) > 0.1:  # Significant directional bias
            
            if energy_state.energy_asymmetry > 0:
                # Bullish: Buy calls
                target_strike = price_targets['resistance_1']
                
                # Find liquid call near target strike
                liquid_calls = options_chain.filter(
                    (pl.col('option_type') == 'call') &
                    (pl.col('strike') >= target_strike * 0.98) &
                    (pl.col('strike') <= target_strike * 1.02)
                ).sort('liquidity_score', descending=True)
                
                if len(liquid_calls) > 0:
                    best_call = liquid_calls[0]
                    trade = {
                        'strategy': 'Long Call',
                        'direction': 'BULLISH',
                        'reasoning': f'Energy asymmetry {energy_state.energy_asymmetry:.2f} suggests upward move easier',
                        'action': 'BUY TO OPEN',
                        'option_type': 'CALL',
                        'strike': best_call['strike'][0],
                        'bid': best_call['bid'][0],
                        'ask': best_call['ask'][0],
                        'spread_pct': best_call['spread_pct'][0],
                        'liquidity_score': best_call['liquidity_score'][0],
                        'open_interest': best_call['open_interest'][0],
                        'expiry_days': 30,
                        'contracts': int(risk_capital / 100),  # Simplified sizing
                        'max_risk': risk_capital,
                        'target_price': target_strike,
                        'stop_loss': current_price * 0.98
                    }
                    trades.append(trade)
                    
                    logger.info(f"   💚 BULLISH TRADE:")
                    logger.info(f"      Buy {trade['contracts']} x {symbol} ${trade['strike']:.0f} Calls")
                    logger.info(f"      Bid/Ask: ${trade['bid']:.2f}/${trade['ask']:.2f} (spread: {trade['spread_pct']:.1f}%)")
                    logger.info(f"      Liquidity Score: {trade['liquidity_score']:.2f}")
                    logger.info(f"      Open Interest: {trade['open_interest']:,}")
                    logger.info(f"      Target: ${trade['target_price']:.2f}")
                else:
                    logger.warning(f"   ⚠️  No liquid calls found near ${target_strike:.0f}")
                
            else:
                # Bearish: Buy puts
                target_strike = price_targets['support_1']
                
                # Find liquid put near target strike
                liquid_puts = options_chain.filter(
                    (pl.col('option_type') == 'put') &
                    (pl.col('strike') >= target_strike * 0.98) &
                    (pl.col('strike') <= target_strike * 1.02)
                ).sort('liquidity_score', descending=True)
                
                if len(liquid_puts) > 0:
                    best_put = liquid_puts[0]
                    trade = {
                        'strategy': 'Long Put',
                        'direction': 'BEARISH',
                        'reasoning': f'Energy asymmetry {energy_state.energy_asymmetry:.2f} suggests downward move easier',
                        'action': 'BUY TO OPEN',
                        'option_type': 'PUT',
                        'strike': best_put['strike'][0],
                        'bid': best_put['bid'][0],
                        'ask': best_put['ask'][0],
                        'spread_pct': best_put['spread_pct'][0],
                        'liquidity_score': best_put['liquidity_score'][0],
                        'open_interest': best_put['open_interest'][0],
                        'expiry_days': 30,
                        'contracts': int(risk_capital / 100),
                        'max_risk': risk_capital,
                        'target_price': target_strike,
                        'stop_loss': current_price * 1.02
                    }
                    trades.append(trade)
                    
                    logger.info(f"   ❤️ BEARISH TRADE:")
                    logger.info(f"      Buy {trade['contracts']} x {symbol} ${trade['strike']:.0f} Puts")
                    logger.info(f"      Bid/Ask: ${trade['bid']:.2f}/${trade['ask']:.2f} (spread: {trade['spread_pct']:.1f}%)")
                    logger.info(f"      Liquidity Score: {trade['liquidity_score']:.2f}")
                    logger.info(f"      Open Interest: {trade['open_interest']:,}")
                    logger.info(f"      Target: ${trade['target_price']:.2f}")
                else:
                    logger.warning(f"   ⚠️  No liquid puts found near ${target_strike:.0f}")
        
        # Strategy 2: Sell premium at high-energy zones (resistance)
        if energy_state.regime in ['elastic', 'high_energy']:
            # High energy = strong resistance, sell OTM calls
            resistance_strike = price_targets['resistance_2']
            
            # Find liquid call near resistance
            liquid_calls = options_chain.filter(
                (pl.col('option_type') == 'call') &
                (pl.col('strike') >= resistance_strike * 0.98) &
                (pl.col('strike') <= resistance_strike * 1.02)
            ).sort('liquidity_score', descending=True)
            
            if len(liquid_calls) > 0:
                best_call = liquid_calls[0]
                trade = {
                    'strategy': 'Short Call (Covered)',
                    'direction': 'NEUTRAL_BEARISH',
                    'reasoning': f'High energy at ${resistance_strike:.2f} suggests strong resistance',
                    'action': 'SELL TO OPEN',
                    'option_type': 'CALL',
                    'strike': best_call['strike'][0],
                    'bid': best_call['bid'][0],
                    'ask': best_call['ask'][0],
                    'spread_pct': best_call['spread_pct'][0],
                    'liquidity_score': best_call['liquidity_score'][0],
                    'open_interest': best_call['open_interest'][0],
                    'expiry_days': 15,  # Shorter for premium collection
                    'contracts': 1,
                    'max_risk': 'Unlimited (use with stock)',
                    'target_price': resistance_strike,
                    'management': 'Close at 50% profit or if stock approaches strike'
                }
                trades.append(trade)
                
                logger.info(f"   🟡 PREMIUM COLLECTION:")
                logger.info(f"      Sell {trade['contracts']} x {symbol} ${trade['strike']:.0f} Calls")
                logger.info(f"      Bid/Ask: ${trade['bid']:.2f}/${trade['ask']:.2f} (spread: {trade['spread_pct']:.1f}%)")
                logger.info(f"      Liquidity Score: {trade['liquidity_score']:.2f}")
                logger.info(f"      Reason: Strong resistance at high-energy zone")
        
        if len(trades) == 0:
            logger.info(f"   ⚪ NO TRADES: Insufficient edge or no liquid options available")
        
        return trades
    
    
    # ========================================================================
    # HELPER METHODS
    # ========================================================================
    
    def _convert_to_exposures(self, options_chain: pl.DataFrame) -> List[GreekExposure]:
        """Convert options chain DataFrame to GreekExposure objects."""
        
        exposures = []
        
        # Group by strike
        grouped = options_chain.group_by('strike').agg([
            pl.col('call_delta').first().alias('call_delta'),
            pl.col('call_gamma').first().alias('call_gamma'),
            pl.col('call_vega').first().alias('call_vega'),
            pl.col('call_theta').first().alias('call_theta'),
            pl.col('put_delta').first().alias('put_delta'),
            pl.col('put_gamma').first().alias('put_gamma'),
            pl.col('put_vega').first().alias('put_vega'),
            pl.col('put_theta').first().alias('put_theta'),
            pl.col('call_oi').sum().alias('call_oi'),
            pl.col('put_oi').sum().alias('put_oi'),
        ])
        
        for row in grouped.iter_rows(named=True):
            exposure = GreekExposure(
                strike=row['strike'],
                call_delta=row.get('call_delta', 0.0) or 0.0,
                call_gamma=row.get('call_gamma', 0.0) or 0.0,
                call_vega=row.get('call_vega', 0.0) or 0.0,
                call_theta=row.get('call_theta', 0.0) or 0.0,
                put_delta=row.get('put_delta', 0.0) or 0.0,
                put_gamma=row.get('put_gamma', 0.0) or 0.0,
                put_vega=row.get('put_vega', 0.0) or 0.0,
                put_theta=row.get('put_theta', 0.0) or 0.0,
                call_oi=int(row.get('call_oi', 0) or 0),
                put_oi=int(row.get('put_oi', 0) or 0)
            )
            exposures.append(exposure)
        
        return exposures


# ========================================================================
# EXAMPLE USAGE
# ========================================================================

def run_complete_workflow():
    """
    Complete example workflow:
    1. Fetch options → Calculate energy → Predict moves
    2. Backtest → Validate accuracy
    3. Generate options trades
    """
    
    logger.info("="*60)
    logger.info("SUPER GNOSIS v3.0 - OPTIONS VALIDATION WORKFLOW")
    logger.info("="*60)
    
    workflow = OptionsValidationWorkflow()
    
    # Configuration
    SYMBOL = "SPY"  # S&P 500 ETF (liquid options)
    RISK_PER_TRADE = 1000.0  # $1000 risk capital per trade
    
    # STEP 1: Fetch current options chain
    logger.info("\n" + "="*60)
    logger.info("STEP 1: FETCH OPTIONS CHAIN (Greeks)")
    logger.info("="*60)
    
    options_chain = workflow.fetch_options_chain(
        symbol=SYMBOL,
        days_to_expiry=30
    )
    
    # Get current stock price and VIX
    spot_price = 450.0  # Placeholder - fetch from market
    vix = 15.0  # Placeholder - fetch from VIX ticker
    
    # STEP 1.5: Fetch DIX/GEX market sentiment (NEW)
    logger.info("\n" + "="*60)
    logger.info("STEP 1.5: FETCH DIX/GEX MARKET SENTIMENT")
    logger.info("="*60)
    
    dix_gex_context = workflow.fetch_dix_gex_context(lookback_days=30)
    
    if dix_gex_context['data_available']:
        logger.info(f"\n📊 MARKET SENTIMENT:")
        logger.info(f"   DIX: {dix_gex_context['dix']:.3f}")
        logger.info(f"   GEX: ${dix_gex_context['gex']:.2f}B")
        logger.info(f"   Signal: {dix_gex_context['interpretations'].get('combined', 'Unknown')}")
    else:
        logger.warning("\n⚠️  DIX/GEX data unavailable, proceeding without market sentiment")
    
    # STEP 2: Calculate energy state (DHPE)
    logger.info("\n" + "="*60)
    logger.info("STEP 2: CALCULATE ENERGY STATE (DHPE Framework)")
    logger.info("="*60)
    
    energy_state = workflow.calculate_energy_state(
        symbol=SYMBOL,
        options_chain=options_chain,
        spot_price=spot_price,
        vix=vix
    )
    
    # STEP 3: Identify price targets
    logger.info("\n" + "="*60)
    logger.info("STEP 3: IDENTIFY PRICE TARGETS")
    logger.info("="*60)
    
    price_targets = workflow.identify_price_targets(
        spot_price=spot_price,
        energy_state=energy_state,
        options_chain=options_chain
    )
    
    # STEP 4: Backtest (validate model)
    logger.info("\n" + "="*60)
    logger.info("STEP 4: BACKTEST - VALIDATE PREDICTIONS")
    logger.info("="*60)
    
    backtest_results = workflow.backtest_predictions(
        symbol=SYMBOL,
        start_date=date.today() - timedelta(days=90),
        end_date=date.today(),
        lookback_days=5  # Validate 5-day predictions
    )
    
    # STEP 5: Generate options trades (if model is accurate)
    if backtest_results['accuracy'] > 0.55:
        logger.info("\n" + "="*60)
        logger.info("STEP 5: GENERATE OPTIONS TRADES")
        logger.info("="*60)
        
        trades = workflow.generate_options_trades(
            symbol=SYMBOL,
            energy_state=energy_state,
            price_targets=price_targets,
            options_chain=options_chain,
            risk_capital=RISK_PER_TRADE
        )
        
        logger.info(f"\n✅ Generated {len(trades)} trade recommendation(s)")
    else:
        logger.info("\n⚠️  Model accuracy insufficient, no trades generated")
    
    logger.info("\n" + "="*60)
    logger.info("WORKFLOW COMPLETE")
    logger.info("="*60)


if __name__ == "__main__":
    run_complete_workflow()
