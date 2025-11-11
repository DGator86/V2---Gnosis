"""
Risk Management Module
Kelly sizing, position limits, VaR, and portfolio risk controls.
"""


def compute_position_size(
    equity: float,
    risk_per_trade: float,
    stop_loss: float,
    entry_cost: float
) -> int:
    """
    Compute position size based on risk budget and stop loss.
    
    Parameters
    ----------
    equity : float
        Total account equity
    risk_per_trade : float
        Maximum risk per trade as fraction (e.g., 0.01 for 1%)
    stop_loss : float
        Stop loss price/value
    entry_cost : float
        Entry price/cost per unit
        
    Returns
    -------
    int
        Position size (number of units/shares/contracts)
    """
    if entry_cost <= 0 or stop_loss <= 0:
        return 0
    
    # Maximum dollar amount to risk
    max_risk_dollars = equity * risk_per_trade
    
    # Risk per unit
    risk_per_unit = abs(entry_cost - stop_loss)
    
    if risk_per_unit <= 0:
        return 0
    
    # Position size
    size = int(max_risk_dollars / risk_per_unit)
    
    return max(0, size)


def apply_kelly_fraction(
    base_size: int,
    win_rate: float,
    avg_win: float,
    avg_loss: float,
    kelly_fraction: float = 0.25
) -> int:
    """
    Apply Kelly criterion to adjust position size.
    
    Parameters
    ----------
    base_size : int
        Base position size
    win_rate : float
        Historical win rate (0..1)
    avg_win : float
        Average win amount
    avg_loss : float
        Average loss amount (positive number)
    kelly_fraction : float
        Fraction of full Kelly to use (default 0.25 = quarter Kelly)
        
    Returns
    -------
    int
        Adjusted position size
    """
    if avg_loss <= 0 or win_rate <= 0 or win_rate >= 1:
        return base_size
    
    # Kelly formula: f = (p*b - q) / b
    # where p = win rate, q = 1-p, b = avg_win / avg_loss
    b = avg_win / avg_loss
    q = 1.0 - win_rate
    
    kelly_f = (win_rate * b - q) / b
    
    # Apply fractional Kelly
    kelly_f = max(0.0, kelly_f * kelly_fraction)
    
    # Adjust size
    adjusted_size = int(base_size * kelly_f)
    
    return max(0, adjusted_size)


def check_portfolio_limits(
    current_positions: int,
    max_positions: int,
    current_portfolio_value: float,
    new_position_value: float,
    max_position_pct: float = 0.2
) -> bool:
    """
    Check if new position would violate portfolio limits.
    
    Parameters
    ----------
    current_positions : int
        Number of current open positions
    max_positions : int
        Maximum allowed positions
    current_portfolio_value : float
        Total portfolio value
    new_position_value : float
        Value of proposed new position
    max_position_pct : float
        Maximum position size as % of portfolio (default 20%)
        
    Returns
    -------
    bool
        True if position is within limits, False otherwise
    """
    # Check position count
    if current_positions >= max_positions:
        return False
    
    # Check position size relative to portfolio
    position_pct = new_position_value / current_portfolio_value
    if position_pct > max_position_pct:
        return False
    
    return True


def calculate_var(
    position_value: float,
    volatility: float,
    confidence: float = 0.95,
    holding_period_days: float = 1.0
) -> float:
    """
    Calculate Value at Risk (VaR) for a position.
    
    Parameters
    ----------
    position_value : float
        Current position value
    volatility : float
        Annualized volatility (std dev)
    confidence : float
        Confidence level (default 0.95 for 95%)
    holding_period_days : float
        Holding period in days
        
    Returns
    -------
    float
        VaR in dollars
    """
    import scipy.stats as stats
    
    # Convert annualized vol to period vol
    period_vol = volatility * (holding_period_days / 252) ** 0.5
    
    # Z-score for confidence level
    z_score = stats.norm.ppf(confidence)
    
    # VaR
    var = position_value * z_score * period_vol
    
    return var
