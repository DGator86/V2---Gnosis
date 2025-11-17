"""
Universal Policy Composer - Multi-Engine Trade Orchestration
=============================================================

The master orchestration system that integrates all v3 engines into cohesive trade ideas.

This module implements the policy composition framework:
1. Multi-Engine Integration → Unified Trade Signal
2. Energy + Liquidity + Sentiment → Position Sizing
3. Monte Carlo Simulation → Risk Assessment
4. Policy Validation → Trade Execution

Integration Architecture:
- Elasticity Engine v3: Movement energy, elasticity, force fields
- Liquidity Engine v3: Impact costs, slippage, depth profiles
- Sentiment Engine v3: Contrarian signals, crowd conviction
- Risk Engine: Position limits, Kelly criterion, vol targeting

Author: Super Gnosis Development Team
License: MIT
Version: 3.0.0
"""

from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
import numpy as np
from enum import Enum
from loguru import logger


class TradeDirection(str, Enum):
    """Trade direction."""
    LONG = "long"
    SHORT = "short"
    NEUTRAL = "neutral"
    AVOID = "avoid"


class PositionSizeMethod(str, Enum):
    """Position sizing methods."""
    FIXED = "fixed"
    KELLY = "kelly"
    VOL_TARGET = "vol_target"
    ENERGY_AWARE = "energy_aware"
    COMPOSITE = "composite"


@dataclass
class RiskParameters:
    """Risk management parameters."""
    
    # Position limits
    max_position_size: float = 10000.0  # Maximum position size ($)
    max_portfolio_exposure: float = 100000.0  # Total portfolio exposure
    max_position_pct: float = 0.10  # Max 10% of portfolio per position
    
    # Volatility targeting
    target_volatility: float = 0.15  # Target 15% annualized vol
    vol_lookback_days: int = 30  # Lookback for vol estimation
    
    # Kelly parameters
    kelly_fraction: float = 0.25  # Use 1/4 Kelly (conservative)
    min_edge: float = 0.05  # Minimum edge required (5%)
    
    # Energy-aware parameters
    max_movement_energy: float = 1000.0  # Avoid high-energy moves
    min_elasticity: float = 0.1  # Minimum market elasticity
    
    # Liquidity parameters
    max_impact_bps: float = 50.0  # Max 50 bps impact
    max_slippage_bps: float = 30.0  # Max 30 bps slippage
    
    # Sentiment parameters
    contrarian_threshold: float = 0.7  # Activate contrarian at |sentiment| > 0.7
    min_crowd_conviction: float = 0.6  # Minimum conviction for contrarian
    
    # Stop loss / take profit
    stop_loss_pct: float = 0.02  # 2% stop loss
    take_profit_pct: float = 0.06  # 6% take profit (3:1 R/R)


@dataclass
class MonteCarloResult:
    """Monte Carlo simulation results."""
    
    win_rate: float  # Probability of profit
    avg_pnl: float  # Average P&L
    median_pnl: float  # Median P&L
    std_pnl: float  # Standard deviation of P&L
    
    max_profit: float  # Best case
    max_loss: float  # Worst case
    
    sharpe_ratio: float  # Risk-adjusted return
    profit_factor: float  # Gross profit / gross loss
    
    var_95: float  # Value at Risk (95%)
    cvar_95: float  # Conditional VaR (95%)
    
    # Distribution
    pnl_distribution: List[float] = field(default_factory=list)
    num_simulations: int = 1000
    
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class TradeIdea:
    """Complete trade idea with all components."""
    
    # Basic info
    symbol: str
    direction: TradeDirection
    
    # Position sizing
    position_size: float  # Number of shares
    position_value: float  # Dollar value
    sizing_method: PositionSizeMethod
    
    # Entry parameters
    entry_price: float  # Recommended entry
    entry_price_min: float  # Entry range min
    entry_price_max: float  # Entry range max
    
    # Exit parameters
    stop_loss: float  # Stop loss price
    take_profit: float  # Take profit price
    
    # Expected costs
    expected_slippage_bps: float
    expected_impact_bps: float
    total_expected_cost_bps: float
    
    # Multi-engine signals
    energy_signal: float  # -1 to 1 (from elasticity)
    liquidity_signal: float  # -1 to 1 (from liquidity)
    sentiment_signal: float  # -1 to 1 (from sentiment)
    composite_signal: float  # Weighted average
    
    # Risk metrics
    expected_return: float  # Expected return (%)
    expected_volatility: float  # Expected volatility (%)
    sharpe_ratio: float  # Risk-adjusted return
    kelly_fraction: float  # Kelly criterion result
    
    # Regime alignment
    energy_regime: str  # From elasticity engine
    liquidity_regime: str  # From liquidity engine
    sentiment_regime: str  # From sentiment engine
    regime_consistency: float  # How aligned are regimes? (0-1)
    
    # Monte Carlo confidence
    mc_win_rate: float  # Probability of profit
    mc_avg_pnl: float  # Average P&L
    mc_sharpe: float  # Simulated Sharpe ratio
    mc_var_95: float  # Value at Risk
    
    # Validation flags
    is_valid: bool  # Passes all validation checks
    validation_warnings: List[str] = field(default_factory=list)
    validation_errors: List[str] = field(default_factory=list)
    
    # Metadata
    timestamp: datetime = field(default_factory=datetime.now)
    confidence: float = 1.0  # Overall confidence (0-1)


class UniversalPolicyComposer:
    """
    Universal policy composer for multi-engine trade orchestration.
    
    This is the master conductor that:
    1. Integrates signals from Elasticity, Liquidity, Sentiment engines
    2. Generates directional bias and position sizing
    3. Runs Monte Carlo simulations for risk assessment
    4. Validates trade ideas against risk parameters
    5. Produces executable trade recommendations
    
    Philosophy:
    - Energy-aware: Avoid high-energy moves (plastic markets)
    - Liquidity-aware: Account for slippage and impact
    - Sentiment-aware: Fade extreme crowd positioning
    - Risk-aware: Kelly criterion + vol targeting + hard limits
    """
    
    def __init__(
        self,
        risk_params: Optional[RiskParameters] = None,
        energy_weight: float = 0.4,
        liquidity_weight: float = 0.3,
        sentiment_weight: float = 0.3,
        enable_monte_carlo: bool = True,
        mc_simulations: int = 1000
    ):
        """
        Initialize universal policy composer.
        
        Args:
            risk_params: Risk management parameters
            energy_weight: Weight for elasticity engine (0-1)
            liquidity_weight: Weight for liquidity engine (0-1)
            sentiment_weight: Weight for sentiment engine (0-1)
            enable_monte_carlo: Run Monte Carlo simulations
            mc_simulations: Number of Monte Carlo simulations
        """
        self.risk_params = risk_params or RiskParameters()
        
        # Signal weights (must sum to 1.0)
        total_weight = energy_weight + liquidity_weight + sentiment_weight
        self.energy_weight = energy_weight / total_weight
        self.liquidity_weight = liquidity_weight / total_weight
        self.sentiment_weight = sentiment_weight / total_weight
        
        self.enable_monte_carlo = enable_monte_carlo
        self.mc_simulations = mc_simulations
        
        logger.info(
            f"🎼 Universal Policy Composer initialized | "
            f"Weights: Energy={self.energy_weight:.2f}, "
            f"Liquidity={self.liquidity_weight:.2f}, "
            f"Sentiment={self.sentiment_weight:.2f}"
        )
    
    def compose_trade_idea(
        self,
        symbol: str,
        current_price: float,
        energy_state: Any,  # EnergyState from elasticity engine
        liquidity_state: Any,  # LiquidityState from liquidity engine
        sentiment_state: Any,  # SentimentState from sentiment engine
        account_value: float,
        current_volatility: float = 0.20,
        historical_returns: Optional[List[float]] = None
    ) -> TradeIdea:
        """
        Compose complete trade idea from all engine states.
        
        Args:
            symbol: Trading symbol
            current_price: Current market price
            energy_state: State from elasticity engine v3
            liquidity_state: State from liquidity engine v3
            sentiment_state: State from sentiment engine v3
            account_value: Current account value
            current_volatility: Historical volatility (annualized)
            historical_returns: Historical returns for Kelly calculation
        
        Returns:
            TradeIdea with direction, sizing, entry/exit, and validation
        """
        logger.info(f"🎼 Composing trade idea for {symbol} @ ${current_price:.2f}")
        
        # Step 1: Extract signals from each engine
        energy_signal = self._extract_energy_signal(energy_state)
        liquidity_signal = self._extract_liquidity_signal(liquidity_state)
        sentiment_signal = self._extract_sentiment_signal(sentiment_state)
        
        # Step 2: Compute composite signal
        composite_signal = self._compute_composite_signal(
            energy_signal, liquidity_signal, sentiment_signal
        )
        
        # Step 3: Determine trade direction
        direction = self._determine_direction(
            composite_signal, energy_state, liquidity_state, sentiment_state
        )
        
        # Step 4: Calculate position size (multiple methods)
        position_size, sizing_method, kelly_frac = self._calculate_position_size(
            direction=direction,
            current_price=current_price,
            account_value=account_value,
            energy_state=energy_state,
            liquidity_state=liquidity_state,
            volatility=current_volatility,
            historical_returns=historical_returns
        )
        
        # Step 5: Determine entry range
        entry_price, entry_min, entry_max = self._determine_entry_range(
            current_price, direction, liquidity_state
        )
        
        # Step 6: Calculate stop loss and take profit
        stop_loss, take_profit = self._calculate_exit_levels(
            entry_price, direction
        )
        
        # Step 7: Estimate execution costs
        expected_slippage, expected_impact, total_cost = self._estimate_execution_costs(
            position_size, current_price, liquidity_state
        )
        
        # Step 8: Calculate expected return and risk metrics
        expected_return, expected_vol, sharpe = self._calculate_risk_metrics(
            entry_price, take_profit, stop_loss, current_volatility
        )
        
        # Step 9: Check regime consistency
        regime_consistency = self._check_regime_consistency(
            energy_state, liquidity_state, sentiment_state
        )
        
        # Step 10: Run Monte Carlo simulation (if enabled)
        mc_result = None
        if self.enable_monte_carlo:
            mc_result = self._run_monte_carlo(
                entry_price=entry_price,
                target_price=take_profit,
                stop_price=stop_loss,
                volatility=current_volatility,
                num_simulations=self.mc_simulations
            )
        
        # Step 11: Validate trade idea
        is_valid, warnings, errors = self._validate_trade_idea(
            direction=direction,
            position_size=position_size,
            position_value=position_size * current_price,
            account_value=account_value,
            energy_state=energy_state,
            liquidity_state=liquidity_state,
            sentiment_state=sentiment_state,
            expected_impact=expected_impact,
            expected_slippage=expected_slippage
        )
        
        # Step 12: Create trade idea
        trade_idea = TradeIdea(
            symbol=symbol,
            direction=direction,
            position_size=position_size,
            position_value=position_size * current_price,
            sizing_method=sizing_method,
            entry_price=entry_price,
            entry_price_min=entry_min,
            entry_price_max=entry_max,
            stop_loss=stop_loss,
            take_profit=take_profit,
            expected_slippage_bps=expected_slippage,
            expected_impact_bps=expected_impact,
            total_expected_cost_bps=total_cost,
            energy_signal=energy_signal,
            liquidity_signal=liquidity_signal,
            sentiment_signal=sentiment_signal,
            composite_signal=composite_signal,
            expected_return=expected_return,
            expected_volatility=expected_vol,
            sharpe_ratio=sharpe,
            kelly_fraction=kelly_frac,
            energy_regime=energy_state.regime,
            liquidity_regime=liquidity_state.regime,
            sentiment_regime=sentiment_state.regime,
            regime_consistency=regime_consistency,
            mc_win_rate=mc_result.win_rate if mc_result else 0.0,
            mc_avg_pnl=mc_result.avg_pnl if mc_result else 0.0,
            mc_sharpe=mc_result.sharpe_ratio if mc_result else 0.0,
            mc_var_95=mc_result.var_95 if mc_result else 0.0,
            is_valid=is_valid,
            validation_warnings=warnings,
            validation_errors=errors,
            confidence=self._calculate_confidence(
                energy_state, liquidity_state, sentiment_state, regime_consistency
            )
        )
        
        # Log result
        self._log_trade_idea(trade_idea)
        
        return trade_idea
    
    # ==================== Signal Extraction ====================
    
    def _extract_energy_signal(self, energy_state: Any) -> float:
        """
        Extract directional signal from energy state.
        
        Logic:
        - Low energy asymmetry → Easier to move in that direction
        - Positive asymmetry → Easier up (bullish)
        - Negative asymmetry → Easier down (bearish)
        - High elasticity → Strong restoring force (fade moves)
        
        Returns:
            Signal in range [-1, 1]
        """
        # Energy asymmetry: positive = easier up, negative = easier down
        asymmetry_signal = np.tanh(energy_state.energy_asymmetry / 100.0)
        
        # Elasticity asymmetry: positive = more resistance up (bearish)
        elasticity_signal = -np.tanh(energy_state.elasticity_asymmetry / 10.0)
        
        # Combine (70% asymmetry, 30% elasticity)
        signal = 0.7 * asymmetry_signal + 0.3 * elasticity_signal
        
        # Dampen signal if regime is unstable
        signal *= energy_state.stability
        
        return float(np.clip(signal, -1.0, 1.0))
    
    def _extract_liquidity_signal(self, liquidity_state: Any) -> float:
        """
        Extract directional signal from liquidity state.
        
        Logic:
        - Depth imbalance → More bids = bullish, more asks = bearish
        - Low impact cost → Easier to move (amplify signal)
        - High slippage → Dangerous (dampen signal)
        
        Returns:
            Signal in range [-1, 1]
        """
        # Depth imbalance: positive = more bids (bullish)
        imbalance_signal = liquidity_state.depth_imbalance
        
        # Adjust for impact cost (high impact = dampen)
        impact_adjustment = 1.0 - min(liquidity_state.impact_cost / 100.0, 1.0)
        
        signal = imbalance_signal * impact_adjustment
        
        # Dampen if regime is unstable
        signal *= liquidity_state.stability
        
        return float(np.clip(signal, -1.0, 1.0))
    
    def _extract_sentiment_signal(self, sentiment_state: Any) -> float:
        """
        Extract directional signal from sentiment state.
        
        Logic:
        - Use contrarian signal (fade extreme sentiment)
        - Momentum signal for trending moves
        - High conviction = stronger signal
        
        Returns:
            Signal in range [-1, 1]
        """
        # Primary: Use contrarian signal
        contrarian = sentiment_state.contrarian_signal
        
        # Secondary: Momentum (for trends)
        momentum = np.tanh(sentiment_state.sentiment_momentum / 0.5)
        
        # Blend: 70% contrarian, 30% momentum
        signal = 0.7 * contrarian + 0.3 * momentum
        
        # Amplify with crowd conviction (more conviction = stronger fade)
        signal *= (1.0 + sentiment_state.crowd_conviction) / 2.0
        
        # Dampen if regime unstable
        signal *= sentiment_state.stability
        
        return float(np.clip(signal, -1.0, 1.0))
    
    def _compute_composite_signal(
        self, energy_signal: float, liquidity_signal: float, sentiment_signal: float
    ) -> float:
        """Compute weighted composite signal."""
        composite = (
            self.energy_weight * energy_signal +
            self.liquidity_weight * liquidity_signal +
            self.sentiment_weight * sentiment_signal
        )
        return float(np.clip(composite, -1.0, 1.0))
    
    # ==================== Direction Determination ====================
    
    def _determine_direction(
        self, composite_signal: float, energy_state: Any, 
        liquidity_state: Any, sentiment_state: Any
    ) -> TradeDirection:
        """
        Determine trade direction from composite signal and regimes.
        
        Rules:
        - |signal| < 0.2 → NEUTRAL (no edge)
        - signal > 0.2 → LONG
        - signal < -0.2 → SHORT
        - Bad regimes → AVOID
        """
        # Check for bad regimes (avoid trading)
        if energy_state.regime == "plastic":
            logger.warning("⚠️  Energy regime is PLASTIC - avoiding trade")
            return TradeDirection.AVOID
        
        if liquidity_state.regime == "frozen":
            logger.warning("⚠️  Liquidity regime is FROZEN - avoiding trade")
            return TradeDirection.AVOID
        
        # Check signal strength
        if abs(composite_signal) < 0.2:
            return TradeDirection.NEUTRAL
        elif composite_signal > 0.2:
            return TradeDirection.LONG
        else:
            return TradeDirection.SHORT
    
    # ==================== Position Sizing ====================
    
    def _calculate_position_size(
        self,
        direction: TradeDirection,
        current_price: float,
        account_value: float,
        energy_state: Any,
        liquidity_state: Any,
        volatility: float,
        historical_returns: Optional[List[float]] = None
    ) -> Tuple[float, PositionSizeMethod, float]:
        """
        Calculate position size using multiple methods.
        
        Returns:
            (position_size, method_used, kelly_fraction)
        """
        if direction in [TradeDirection.NEUTRAL, TradeDirection.AVOID]:
            return 0.0, PositionSizeMethod.FIXED, 0.0
        
        # Method 1: Fixed dollar amount
        fixed_size = self.risk_params.max_position_size / current_price
        
        # Method 2: Kelly Criterion
        kelly_size = 0.0
        kelly_frac = 0.0
        if historical_returns and len(historical_returns) > 20:
            kelly_size, kelly_frac = self._kelly_criterion_size(
                historical_returns, account_value, current_price
            )
        
        # Method 3: Volatility targeting
        vol_target_size = self._vol_target_size(
            volatility, account_value, current_price
        )
        
        # Method 4: Energy-aware sizing
        energy_aware_size = self._energy_aware_size(
            base_size=vol_target_size,
            movement_energy=energy_state.movement_energy,
            elasticity=energy_state.elasticity
        )
        
        # Composite: Use minimum of all methods (most conservative)
        candidates = [
            (fixed_size, PositionSizeMethod.FIXED),
            (vol_target_size, PositionSizeMethod.VOL_TARGET),
            (energy_aware_size, PositionSizeMethod.ENERGY_AWARE)
        ]
        
        if kelly_size > 0:
            candidates.append((kelly_size, PositionSizeMethod.KELLY))
        
        # Take minimum (most conservative)
        position_size, method = min(candidates, key=lambda x: x[0])
        
        # Apply hard limits
        max_shares = self.risk_params.max_position_size / current_price
        max_pct_shares = (account_value * self.risk_params.max_position_pct) / current_price
        
        position_size = min(position_size, max_shares, max_pct_shares)
        
        # Round to whole shares
        position_size = int(position_size)
        
        logger.info(
            f"📊 Position sizing: {position_size} shares | Method: {method.value} | "
            f"Kelly: {kelly_frac:.3f}"
        )
        
        return float(position_size), method, kelly_frac
    
    def _kelly_criterion_size(
        self, historical_returns: List[float], account_value: float, current_price: float
    ) -> Tuple[float, float]:
        """
        Calculate position size using Kelly Criterion.
        
        Kelly % = (p*W - (1-p)*L) / W
        where:
        - p = win probability
        - W = average win
        - L = average loss
        """
        returns = np.array(historical_returns)
        
        # Calculate win rate
        wins = returns[returns > 0]
        losses = returns[returns < 0]
        
        if len(wins) == 0 or len(losses) == 0:
            return 0.0, 0.0
        
        p = len(wins) / len(returns)
        avg_win = np.mean(wins)
        avg_loss = abs(np.mean(losses))
        
        # Kelly formula
        if avg_win <= 0:
            return 0.0, 0.0
        
        kelly_pct = (p * avg_win - (1 - p) * avg_loss) / avg_win
        
        # Apply fractional Kelly
        kelly_pct *= self.risk_params.kelly_fraction
        
        # Minimum edge check
        edge = p * avg_win - (1 - p) * avg_loss
        if edge < self.risk_params.min_edge:
            logger.warning(f"⚠️  Insufficient edge: {edge:.3f} < {self.risk_params.min_edge}")
            return 0.0, 0.0
        
        # Convert to shares
        kelly_dollars = account_value * kelly_pct
        kelly_shares = kelly_dollars / current_price
        
        return float(kelly_shares), float(kelly_pct)
    
    def _vol_target_size(
        self, volatility: float, account_value: float, current_price: float
    ) -> float:
        """
        Calculate position size using volatility targeting.
        
        Position = (Target_Vol / Asset_Vol) * Account_Value / Price
        """
        if volatility <= 0:
            return 0.0
        
        vol_ratio = self.risk_params.target_volatility / volatility
        position_value = account_value * vol_ratio
        position_shares = position_value / current_price
        
        return float(position_shares)
    
    def _energy_aware_size(
        self, base_size: float, movement_energy: float, elasticity: float
    ) -> float:
        """
        Adjust position size based on movement energy.
        
        Logic: Size ∝ 1/movement_energy (avoid high-energy moves)
        """
        # Dampen size if energy is high
        if movement_energy > self.risk_params.max_movement_energy:
            energy_factor = self.risk_params.max_movement_energy / movement_energy
        else:
            energy_factor = 1.0
        
        # Dampen size if elasticity is low
        if elasticity < self.risk_params.min_elasticity:
            elasticity_factor = elasticity / self.risk_params.min_elasticity
        else:
            elasticity_factor = 1.0
        
        adjusted_size = base_size * energy_factor * elasticity_factor
        
        return float(adjusted_size)
    
    # ==================== Entry/Exit Levels ====================
    
    def _determine_entry_range(
        self, current_price: float, direction: TradeDirection, liquidity_state: Any
    ) -> Tuple[float, float, float]:
        """
        Determine entry price range based on liquidity.
        
        Returns:
            (entry_price, entry_min, entry_max)
        """
        # Use current price as base
        entry_price = current_price
        
        # Adjust for spread
        spread_adjustment = current_price * (liquidity_state.spread_bps / 10000.0)
        
        if direction == TradeDirection.LONG:
            # For long: can pay up to mid + spread/2
            entry_min = current_price
            entry_max = current_price + spread_adjustment
        elif direction == TradeDirection.SHORT:
            # For short: can receive down to mid - spread/2
            entry_max = current_price
            entry_min = current_price - spread_adjustment
        else:
            entry_min = current_price
            entry_max = current_price
        
        return entry_price, entry_min, entry_max
    
    def _calculate_exit_levels(
        self, entry_price: float, direction: TradeDirection
    ) -> Tuple[float, float]:
        """
        Calculate stop loss and take profit levels.
        
        Returns:
            (stop_loss, take_profit)
        """
        if direction == TradeDirection.LONG:
            stop_loss = entry_price * (1 - self.risk_params.stop_loss_pct)
            take_profit = entry_price * (1 + self.risk_params.take_profit_pct)
        elif direction == TradeDirection.SHORT:
            stop_loss = entry_price * (1 + self.risk_params.stop_loss_pct)
            take_profit = entry_price * (1 - self.risk_params.take_profit_pct)
        else:
            stop_loss = entry_price
            take_profit = entry_price
        
        return stop_loss, take_profit
    
    # ==================== Execution Costs ====================
    
    def _estimate_execution_costs(
        self, position_size: float, current_price: float, liquidity_state: Any
    ) -> Tuple[float, float, float]:
        """
        Estimate slippage and impact costs.
        
        Returns:
            (slippage_bps, impact_bps, total_cost_bps)
        """
        # Use liquidity engine estimates
        slippage_bps = liquidity_state.slippage
        impact_bps = liquidity_state.impact_cost
        
        # Adjust for position size (linear approximation)
        # Larger positions = more impact
        size_adjustment = 1.0 + (position_size * current_price / 100000.0)
        
        adjusted_slippage = slippage_bps * size_adjustment
        adjusted_impact = impact_bps * size_adjustment
        
        total_cost = adjusted_slippage + adjusted_impact
        
        return adjusted_slippage, adjusted_impact, total_cost
    
    # ==================== Risk Metrics ====================
    
    def _calculate_risk_metrics(
        self, entry_price: float, take_profit: float, 
        stop_loss: float, volatility: float
    ) -> Tuple[float, float, float]:
        """
        Calculate expected return, volatility, and Sharpe ratio.
        
        Returns:
            (expected_return, expected_volatility, sharpe_ratio)
        """
        # Expected return (probability-weighted)
        # Assume 50/50 win/loss for conservatism
        win_pct = (take_profit - entry_price) / entry_price
        loss_pct = (entry_price - stop_loss) / entry_price
        
        expected_return = 0.5 * win_pct - 0.5 * loss_pct
        
        # Expected volatility (use historical)
        expected_vol = volatility
        
        # Sharpe ratio (assume 5% risk-free rate)
        risk_free_rate = 0.05
        if expected_vol > 0:
            sharpe = (expected_return - risk_free_rate) / expected_vol
        else:
            sharpe = 0.0
        
        return expected_return, expected_vol, sharpe
    
    # ==================== Regime Consistency ====================
    
    def _check_regime_consistency(
        self, energy_state: Any, liquidity_state: Any, sentiment_state: Any
    ) -> float:
        """
        Check how well regimes align across engines.
        
        Returns:
            Consistency score (0-1)
        """
        # Map regimes to numeric scores
        regime_map = {
            # Bullish regimes
            "elastic": 0.5, "super_elastic": 1.0,
            "liquid": 0.5, "deep": 1.0,
            "neutral": 0.0, "bullish": 0.5, "extreme_bullish": 1.0,
            
            # Bearish regimes
            "brittle": -0.5, "plastic": -1.0, "chaotic": -1.0,
            "thin": -0.5, "frozen": -1.0,
            "bearish": -0.5, "extreme_bearish": -1.0,
        }
        
        energy_score = regime_map.get(energy_state.regime, 0.0)
        liquidity_score = regime_map.get(liquidity_state.regime, 0.0)
        sentiment_score = regime_map.get(sentiment_state.regime, 0.0)
        
        # Calculate variance (low variance = high consistency)
        scores = [energy_score, liquidity_score, sentiment_score]
        variance = np.var(scores)
        
        # Convert to consistency (0 variance = 1.0 consistency)
        consistency = np.exp(-variance)
        
        return float(consistency)
    
    # ==================== Monte Carlo Simulation ====================
    
    def _run_monte_carlo(
        self,
        entry_price: float,
        target_price: float,
        stop_price: float,
        volatility: float,
        num_simulations: int = 1000
    ) -> MonteCarloResult:
        """
        Run Monte Carlo simulation of trade outcomes.
        
        Uses geometric Brownian motion to simulate price paths.
        
        Args:
            entry_price: Entry price
            target_price: Take profit price
            stop_price: Stop loss price
            volatility: Annualized volatility
            num_simulations: Number of simulations
        
        Returns:
            MonteCarloResult with statistics
        """
        logger.info(f"🎲 Running Monte Carlo: {num_simulations} simulations")
        
        # Simulation parameters
        dt = 1/252  # Daily time step
        num_steps = 20  # Simulate 20 days
        mu = 0.0  # Assume zero drift (conservative)
        
        pnl_results = []
        
        for _ in range(num_simulations):
            price = entry_price
            
            for step in range(num_steps):
                # Geometric Brownian motion
                dW = np.random.normal(0, np.sqrt(dt))
                dS = mu * price * dt + volatility * price * dW
                price += dS
                
                # Check for stop loss or take profit
                if price <= stop_price:
                    pnl = stop_price - entry_price
                    pnl_results.append(pnl)
                    break
                elif price >= target_price:
                    pnl = target_price - entry_price
                    pnl_results.append(pnl)
                    break
            else:
                # No stop/target hit - exit at current price
                pnl = price - entry_price
                pnl_results.append(pnl)
        
        pnl_array = np.array(pnl_results)
        
        # Calculate statistics
        win_rate = np.sum(pnl_array > 0) / len(pnl_array)
        avg_pnl = np.mean(pnl_array)
        median_pnl = np.median(pnl_array)
        std_pnl = np.std(pnl_array)
        
        max_profit = np.max(pnl_array)
        max_loss = np.min(pnl_array)
        
        # Sharpe ratio
        if std_pnl > 0:
            sharpe = avg_pnl / std_pnl * np.sqrt(252)  # Annualized
        else:
            sharpe = 0.0
        
        # Profit factor
        gross_profit = np.sum(pnl_array[pnl_array > 0])
        gross_loss = abs(np.sum(pnl_array[pnl_array < 0]))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0.0
        
        # Value at Risk (95%)
        var_95 = np.percentile(pnl_array, 5)
        
        # Conditional VaR (expected loss given loss > VaR)
        cvar_losses = pnl_array[pnl_array <= var_95]
        cvar_95 = np.mean(cvar_losses) if len(cvar_losses) > 0 else var_95
        
        return MonteCarloResult(
            win_rate=float(win_rate),
            avg_pnl=float(avg_pnl),
            median_pnl=float(median_pnl),
            std_pnl=float(std_pnl),
            max_profit=float(max_profit),
            max_loss=float(max_loss),
            sharpe_ratio=float(sharpe),
            profit_factor=float(profit_factor),
            var_95=float(var_95),
            cvar_95=float(cvar_95),
            pnl_distribution=pnl_results,
            num_simulations=num_simulations
        )
    
    # ==================== Validation ====================
    
    def _validate_trade_idea(
        self,
        direction: TradeDirection,
        position_size: float,
        position_value: float,
        account_value: float,
        energy_state: Any,
        liquidity_state: Any,
        sentiment_state: Any,
        expected_impact: float,
        expected_slippage: float
    ) -> Tuple[bool, List[str], List[str]]:
        """
        Validate trade idea against risk parameters.
        
        Returns:
            (is_valid, warnings, errors)
        """
        warnings = []
        errors = []
        
        # Check direction
        if direction == TradeDirection.AVOID:
            errors.append("Trade direction is AVOID - market conditions unfavorable")
        
        if direction == TradeDirection.NEUTRAL:
            warnings.append("Trade direction is NEUTRAL - no clear edge")
        
        # Check position size
        if position_size <= 0:
            errors.append("Position size is zero or negative")
        
        # Check position limits
        if position_value > self.risk_params.max_position_size:
            errors.append(
                f"Position value ${position_value:.2f} exceeds max "
                f"${self.risk_params.max_position_size:.2f}"
            )
        
        position_pct = position_value / account_value
        if position_pct > self.risk_params.max_position_pct:
            errors.append(
                f"Position is {position_pct*100:.1f}% of account, max is "
                f"{self.risk_params.max_position_pct*100:.1f}%"
            )
        
        # Check energy regime
        if energy_state.regime == "plastic":
            errors.append("Energy regime is PLASTIC - high resistance to movement")
        elif energy_state.regime == "chaotic":
            warnings.append("Energy regime is CHAOTIC - unstable conditions")
        
        if energy_state.movement_energy > self.risk_params.max_movement_energy:
            warnings.append(
                f"Movement energy {energy_state.movement_energy:.1f} exceeds threshold "
                f"{self.risk_params.max_movement_energy:.1f}"
            )
        
        if energy_state.elasticity < self.risk_params.min_elasticity:
            warnings.append(
                f"Elasticity {energy_state.elasticity:.3f} below minimum "
                f"{self.risk_params.min_elasticity:.3f}"
            )
        
        # Check liquidity regime
        if liquidity_state.regime == "frozen":
            errors.append("Liquidity regime is FROZEN - no liquidity available")
        elif liquidity_state.regime == "thin":
            warnings.append("Liquidity regime is THIN - limited liquidity")
        
        if expected_impact > self.risk_params.max_impact_bps:
            warnings.append(
                f"Expected impact {expected_impact:.1f} bps exceeds max "
                f"{self.risk_params.max_impact_bps:.1f} bps"
            )
        
        if expected_slippage > self.risk_params.max_slippage_bps:
            warnings.append(
                f"Expected slippage {expected_slippage:.1f} bps exceeds max "
                f"{self.risk_params.max_slippage_bps:.1f} bps"
            )
        
        # Check sentiment
        if abs(sentiment_state.sentiment_score) > 0.8:
            warnings.append(
                f"Extreme sentiment detected: {sentiment_state.sentiment_score:.2f}"
            )
        
        is_valid = len(errors) == 0
        
        return is_valid, warnings, errors
    
    # ==================== Confidence & Logging ====================
    
    def _calculate_confidence(
        self, energy_state: Any, liquidity_state: Any, 
        sentiment_state: Any, regime_consistency: float
    ) -> float:
        """
        Calculate overall confidence score.
        
        Factors:
        - Engine stability scores
        - Regime consistency
        - Data quality
        """
        # Average stability across engines
        avg_stability = (
            energy_state.stability + 
            liquidity_state.stability + 
            sentiment_state.stability
        ) / 3.0
        
        # Average confidence across engines
        avg_confidence = (
            energy_state.confidence + 
            liquidity_state.confidence + 
            sentiment_state.confidence
        ) / 3.0
        
        # Composite confidence
        confidence = (
            0.4 * avg_stability +
            0.3 * avg_confidence +
            0.3 * regime_consistency
        )
        
        return float(np.clip(confidence, 0.0, 1.0))
    
    def _log_trade_idea(self, trade_idea: TradeIdea) -> None:
        """Log trade idea summary."""
        logger.info("=" * 60)
        logger.info(f"🎼 TRADE IDEA: {trade_idea.symbol}")
        logger.info("=" * 60)
        logger.info(f"Direction: {trade_idea.direction.value.upper()}")
        logger.info(f"Position: {trade_idea.position_size:.0f} shares @ ${trade_idea.entry_price:.2f}")
        logger.info(f"Position Value: ${trade_idea.position_value:.2f}")
        logger.info(f"Sizing Method: {trade_idea.sizing_method.value}")
        logger.info(f"Stop Loss: ${trade_idea.stop_loss:.2f}")
        logger.info(f"Take Profit: ${trade_idea.take_profit:.2f}")
        logger.info("-" * 60)
        logger.info(f"Composite Signal: {trade_idea.composite_signal:+.3f}")
        logger.info(f"  ├─ Energy: {trade_idea.energy_signal:+.3f} ({trade_idea.energy_regime})")
        logger.info(f"  ├─ Liquidity: {trade_idea.liquidity_signal:+.3f} ({trade_idea.liquidity_regime})")
        logger.info(f"  └─ Sentiment: {trade_idea.sentiment_signal:+.3f} ({trade_idea.sentiment_regime})")
        logger.info(f"Regime Consistency: {trade_idea.regime_consistency:.2%}")
        logger.info("-" * 60)
        logger.info(f"Expected Return: {trade_idea.expected_return:.2%}")
        logger.info(f"Expected Vol: {trade_idea.expected_volatility:.2%}")
        logger.info(f"Sharpe Ratio: {trade_idea.sharpe_ratio:.2f}")
        logger.info(f"Kelly Fraction: {trade_idea.kelly_fraction:.3f}")
        logger.info("-" * 60)
        logger.info(f"Monte Carlo Win Rate: {trade_idea.mc_win_rate:.1%}")
        logger.info(f"Monte Carlo Avg P&L: ${trade_idea.mc_avg_pnl:.2f}")
        logger.info(f"Monte Carlo Sharpe: {trade_idea.mc_sharpe:.2f}")
        logger.info(f"Monte Carlo VaR (95%): ${trade_idea.mc_var_95:.2f}")
        logger.info("-" * 60)
        logger.info(f"Execution Costs: {trade_idea.total_expected_cost_bps:.1f} bps")
        logger.info(f"  ├─ Slippage: {trade_idea.expected_slippage_bps:.1f} bps")
        logger.info(f"  └─ Impact: {trade_idea.expected_impact_bps:.1f} bps")
        logger.info("-" * 60)
        logger.info(f"Valid: {trade_idea.is_valid}")
        logger.info(f"Confidence: {trade_idea.confidence:.1%}")
        
        if trade_idea.validation_warnings:
            logger.warning(f"⚠️  Warnings: {len(trade_idea.validation_warnings)}")
            for warning in trade_idea.validation_warnings:
                logger.warning(f"  • {warning}")
        
        if trade_idea.validation_errors:
            logger.error(f"❌ Errors: {len(trade_idea.validation_errors)}")
            for error in trade_idea.validation_errors:
                logger.error(f"  • {error}")
        
        logger.info("=" * 60)
