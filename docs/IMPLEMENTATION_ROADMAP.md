# DHPE Implementation Roadmap

## Current Status

### ✅ Completed (M1)
- [x] Project structure and organization
- [x] Basic engine scaffolding (DHPE, Liquidity, Order Flow)
- [x] Configuration system with API credentials
- [x] Git repository with proper .gitignore
- [x] Documentation (README, QUICKSTART, THEORY)
- [x] Example usage script
- [x] Placeholder implementations for all core functions

### 🟡 In Progress (M2 - M3)
Current placeholders that need full implementation:
- [ ] Sticky-delta projector in `dhpe.sources()`
- [ ] Green's kernel computation in `dhpe.greens_kernel()`
- [ ] FFT-based convolution in `dhpe.potential()`
- [ ] Real-time market data integration

---

## Phase 1: Core Math Implementation (M2)

### M2.1: Vol Surface & Greek Computation
**Priority**: HIGH | **Complexity**: Medium | **Time**: 2-3 days

#### Tasks
1. **SSVI Vol Surface Interpolation**
   ```python
   # engines/vol_surface.py
   def fit_ssvi(strikes, expiries, mid_iv, spot):
       """Fit SSVI parametrization for arbitrage-free surface"""
       # Implement SSVI formula
       # Ensure no calendar spread arbitrage
       # Fill gaps in chain
   ```
   
2. **Precise Greek Calculations**
   ```python
   # engines/greeks.py
   def compute_greeks(S, K, tau, r, q, sigma, option_type):
       """Black-Scholes Greeks with proper normalization"""
       d1 = (log(S/K) + (r-q+sigma**2/2)*tau) / (sigma*sqrt(tau))
       d2 = d1 - sigma*sqrt(tau)
       
       gamma = exp(-q*tau) * norm.pdf(d1) / (S * sigma * sqrt(tau))
       vanna = -exp(-q*tau) * (d2/sigma) * norm.pdf(d1)
       charm = -exp(-q*tau) * norm.pdf(d1) * (
           (2*r*tau - d2*sigma*sqrt(tau)) / (2*tau*sigma*sqrt(tau))
       )
       
       return gamma, vanna, charm
   ```

3. **Unit Conversion & Normalization**
   - Convert charm to per-minute (divide annualized by 252*390)
   - Handle contract multipliers (100 for equity options)
   - Proper dollar exposure calculations

**Deliverables**:
- [ ] `engines/vol_surface.py` with SSVI implementation
- [ ] `engines/greeks.py` with precise formulas
- [ ] Unit tests for all Greek calculations
- [ ] Validation against known values

### M2.2: Sticky-Delta Projector
**Priority**: HIGH | **Complexity**: Medium-High | **Time**: 2-3 days

#### Concept
Map option exposures from (K, τ) space to price bins that move with spot.

#### Implementation
```python
# engines/dhpe.py - enhanced sources()

def sources(options_df, projector_config):
    """
    Project option exposures onto sticky-delta moneyness grid.
    
    Parameters
    ----------
    options_df : DataFrame with columns:
        - strike, tau, gamma, vanna, charm
        - open_interest, contract_mult
        - dealer_position_sign (±1)
    projector_config : dict with:
        - mode: 'sticky-delta' or 'sticky-strike'
        - bins: number of moneyness bins
        - price_range: (S_min, S_max) for grid
    
    Returns
    -------
    G, Vn, Ch : np.ndarray
        Projected source densities on price grid
    """
    # Compute log-moneyness for each option
    m = np.log(options_df['strike'] / S_current) / (
        options_df['iv'] * np.sqrt(options_df['tau'])
    )
    
    # Quantize to bins
    bins = projector_config['bins']
    m_bins = np.linspace(-3, 3, bins)  # Cover ±3 sigma
    
    # Project exposures
    G = np.zeros(bins)
    Vn = np.zeros(bins)
    Ch = np.zeros(bins)
    
    for i, option in options_df.iterrows():
        bin_idx = np.digitize(m[i], m_bins)
        
        # Dollar exposure
        G$_i = option['gamma'] * S**2 * option['oi'] * option['mult']
        V$_i = option['vanna'] * S * option['oi'] * option['mult']
        C$_i = option['charm'] * S * option['oi'] * option['mult']
        
        # Accumulate (with dealer position sign)
        sign = option['dealer_sign']  # +1 if long, -1 if short
        G[bin_idx] += sign * G$_i
        Vn[bin_idx] += sign * V$_i
        Ch[bin_idx] += sign * C$_i
    
    return G, Vn, Ch
```

**Deliverables**:
- [ ] Complete `sources()` implementation
- [ ] Moneyness binning algorithm
- [ ] Position signing logic
- [ ] Visualization tools for field heatmaps

### M2.3: Green's Kernel & Convolution
**Priority**: HIGH | **Complexity**: High | **Time**: 3-4 days

#### Green's Function Solution
Solve: `(-∂_x λ⁻¹ ∂_x + κ²) K = δ(x)`

```python
# engines/dhpe.py - enhanced greens_kernel()

def greens_kernel(lambda_series, kappa, grid):
    """
    Build Green's kernel for liquidity-weighted operator.
    
    For constant λ, analytical solution:
        K(x) = (λκ/2) * exp(-κ|x|)
    
    For variable λ(x), use numerical methods:
        - Finite differences on grid
        - Solve sparse linear system
    """
    N = len(grid)
    dx = grid[1] - grid[0]
    
    if np.allclose(lambda_series, lambda_series[0]):
        # Constant lambda - analytical
        lam = lambda_series[0]
        x = grid - grid[N//2]  # Center at middle
        K = (lam * kappa / 2) * np.exp(-kappa * np.abs(x))
    else:
        # Variable lambda - numerical
        # Build operator matrix
        A = build_operator_matrix(lambda_series, kappa, dx)
        
        # Solve A * K = e_center (delta at center)
        e_center = np.zeros(N)
        e_center[N//2] = 1.0 / dx  # Normalized delta
        
        K = scipy.sparse.linalg.spsolve(A, e_center)
    
    # Normalize
    K = K / np.sum(K * dx)
    
    return K


def build_operator_matrix(lam, kappa, dx):
    """Build sparse matrix for (-∂_x λ⁻¹ ∂_x + κ²)"""
    N = len(lam)
    
    # Second derivative with variable coefficient
    # (-∂_x λ⁻¹ ∂_x) ≈ -1/dx² * [λ⁻¹_{i-1/2}(u_{i-1}-u_i) + λ⁻¹_{i+1/2}(u_{i+1}-u_i)]
    
    diag = np.zeros(N)
    off_diag_lower = np.zeros(N-1)
    off_diag_upper = np.zeros(N-1)
    
    for i in range(1, N-1):
        lam_inv_left = 2.0 / (lam[i-1] + lam[i])
        lam_inv_right = 2.0 / (lam[i] + lam[i+1])
        
        diag[i] = (lam_inv_left + lam_inv_right) / dx**2 + kappa**2
        off_diag_lower[i-1] = -lam_inv_left / dx**2
        off_diag_upper[i] = -lam_inv_right / dx**2
    
    # Boundary conditions (Neumann or periodic)
    diag[0] = diag[1]
    diag[N-1] = diag[N-2]
    
    A = scipy.sparse.diags(
        [off_diag_lower, diag, off_diag_upper],
        [-1, 0, 1],
        format='csr'
    )
    
    return A
```

#### FFT-Based Convolution
```python
# engines/dhpe.py - enhanced potential()

def potential(G, Vn, Ch, K, weights):
    """
    Convolve weighted sources with kernel via FFT.
    
    Π(x) = (α_G*G + α_V*Vn + α_C*Ch) ⊗ K(x)
    """
    # Weighted source combination
    source = (
        weights['alpha_G'] * G +
        weights['alpha_V'] * Vn +
        weights['alpha_C'] * Ch
    )
    
    # FFT convolution
    Pi = scipy.signal.fftconvolve(source, K, mode='same')
    
    return Pi
```

**Deliverables**:
- [ ] Analytical Green's function for constant λ
- [ ] Numerical solver for variable λ
- [ ] FFT convolution implementation
- [ ] Benchmarks vs naive O(N²) convolution
- [ ] Unit tests for kernel properties (normalization, symmetry)

---

## Phase 2: Data Integration (M3)

### M3.1: Alpaca Market Data
**Priority**: HIGH | **Complexity**: Low-Medium | **Time**: 1-2 days

```python
# data/alpaca_client.py

import alpaca_trade_api as tradeapi
from config import get_alpaca_config

class AlpacaDataClient:
    def __init__(self):
        config = get_alpaca_config()
        self.api = tradeapi.REST(
            key_id=config['key_id'],
            secret_key=config['secret_key'],
            base_url=config['base_url']
        )
    
    def get_bars(self, symbol, timeframe, limit=1000):
        """Fetch historical bars"""
        bars = self.api.get_bars(
            symbol, timeframe, limit=limit
        ).df
        return bars
    
    def get_options_chain(self, symbol, expiry_date=None):
        """Fetch options chain data"""
        # Note: Alpaca may have limited options data
        # Consider alternative: CBOE DataShop, IVolatility, etc.
        pass
```

**Deliverables**:
- [ ] Alpaca client wrapper
- [ ] Historical bar fetching
- [ ] Options data integration (or alternative source)
- [ ] Data caching layer

### M3.2: Trade Classification Engine
**Priority**: MEDIUM | **Complexity**: Medium | **Time**: 2-3 days

```python
# engines/trade_classification.py

def classify_trade_lee_ready(trade_price, bid, ask, prev_price):
    """
    Lee-Ready algorithm for trade initiator classification.
    
    Returns
    -------
    +1 if buyer-initiated (dealer sold)
    -1 if seller-initiated (dealer bought)
    """
    midpoint = (bid + ask) / 2
    
    if trade_price > midpoint:
        return +1  # Buyer-initiated
    elif trade_price < midpoint:
        return -1  # Seller-initiated
    else:
        # Use tick rule
        if trade_price > prev_price:
            return +1
        elif trade_price < prev_price:
            return -1
        else:
            return 0  # Unknown

def aggregate_dealer_position(options_chain, trades_df):
    """
    Infer dealer net position from trade flow.
    
    Assumptions:
    - Market makers are counterparty to most trades
    - Buyer-initiated = customer bought = dealer sold (short)
    - Seller-initiated = customer sold = dealer bought (long)
    """
    dealer_positions = {}
    
    for contract_id in options_chain['contract_id'].unique():
        trades = trades_df[trades_df['contract_id'] == contract_id]
        
        net_dealer_qty = 0
        for _, trade in trades.iterrows():
            side = classify_trade_lee_ready(
                trade['price'],
                trade['bid'],
                trade['ask'],
                trade['prev_price']
            )
            # Dealer takes opposite side
            net_dealer_qty -= side * trade['quantity']
        
        dealer_positions[contract_id] = net_dealer_qty
    
    return dealer_positions
```

**Deliverables**:
- [ ] Lee-Ready algorithm implementation
- [ ] Dealer position aggregation
- [ ] Historical position reconstruction
- [ ] Validation against known events

---

## Phase 3: Signal Generation (M4)

### M4.1: Regime Detection
**Priority**: HIGH | **Complexity**: Medium | **Time**: 2-3 days

```python
# signals/regime.py

def detect_regime(Pi, grad_Pi, dPi_dt, lam, kappa):
    """
    Classify market regime based on DHPE fields.
    
    Returns
    -------
    regime : str
        'stable_long_gamma' | 'stable_short_gamma' |
        'unstable' | 'critical'
    metrics : dict
        Diagnostic values
    """
    # Aggregate gamma exposure (from grad_Pi)
    gamma_net = np.sum(grad_Pi)
    
    # Amplification factor
    Psi = gamma_net  # Simplified (full version includes vanna)
    A = 1.0 / (1.0 - kappa * Psi)
    
    # Classification
    if gamma_net > 0:
        if A < 1.2:
            regime = 'stable_long_gamma'
        else:
            regime = 'unstable'
    else:
        if A > 0 and A < 1.5:
            regime = 'stable_short_gamma'
        elif A >= 1.5:
            regime = 'critical'
        else:
            regime = 'unstable'
    
    metrics = {
        'gamma_net': gamma_net,
        'amplification': A,
        'kappa_psi': kappa * Psi,
        'liquidity': lam,
    }
    
    return regime, metrics
```

### M4.2: Trading Signals
**Priority**: MEDIUM | **Complexity**: Medium-High | **Time**: 3-4 days

```python
# signals/trading.py

def generate_signals(regime, Pi, grad_Pi, dPi_dt, cvd):
    """
    Generate trading signals from DHPE analysis.
    
    Signal types:
    - Mean reversion in long gamma regime
    - Momentum in short gamma regime  
    - Gamma flip breakouts
    - Vanna rally/crash anticipation
    """
    signals = []
    
    if regime == 'stable_long_gamma':
        # Mean reversion strategy
        if grad_Pi[-1] > 2*np.std(grad_Pi):
            signals.append({
                'type': 'mean_reversion',
                'direction': 'short',
                'confidence': 0.7,
                'reason': 'Extreme positive gradient in long gamma'
            })
    
    elif regime == 'stable_short_gamma':
        # Momentum strategy
        if dPi_dt > 0 and cvd[-1] > cvd[-10]:
            signals.append({
                'type': 'momentum',
                'direction': 'long',
                'confidence': 0.6,
                'reason': 'Positive dPi/dt with rising CVD'
            })
    
    # Add more signal types...
    
    return signals
```

**Deliverables**:
- [ ] Regime classification engine
- [ ] Signal generation framework
- [ ] Signal backtesting infrastructure
- [ ] Performance metrics

---

## Phase 4: Production System (M5)

### M5.1: Real-Time Engine
**Priority**: MEDIUM | **Complexity**: High | **Time**: 1-2 weeks

- [ ] WebSocket data ingestion
- [ ] Streaming Greek computation
- [ ] Incremental field updates
- [ ] Low-latency API (<100ms)

### M5.2: Risk Management
**Priority**: HIGH | **Complexity**: Medium | **Time**: 1 week

- [ ] Position sizing
- [ ] Stop losses
- [ ] Exposure limits
- [ ] VaR monitoring

### M5.3: Monitoring & Alerts
**Priority**: MEDIUM | **Complexity**: Low-Medium | **Time**: 3-5 days

- [ ] Dashboard (Streamlit/Dash)
- [ ] Field visualization (heatmaps)
- [ ] Alert system (Discord/Telegram)
- [ ] Performance tracking

---

## Testing Strategy

### Unit Tests
- [ ] Greek calculation accuracy (vs QuantLib)
- [ ] Kernel normalization
- [ ] Convolution correctness
- [ ] Liquidity estimation

### Integration Tests
- [ ] End-to-end pipeline
- [ ] Data flow validation
- [ ] API response times

### Historical Backtests
- [ ] 2018 Volmageddon
- [ ] March 2020 COVID crash
- [ ] 2023 0DTE explosion
- [ ] Compare regime detection vs realized outcomes

---

## Timeline Estimate

**Phase 1 (M2)**: 1-2 weeks  
**Phase 2 (M3)**: 1 week  
**Phase 3 (M4)**: 1-2 weeks  
**Phase 4 (M5)**: 2-3 weeks  

**Total**: ~6-8 weeks for full production system

---

## Success Metrics

1. **Accuracy**: Greek calculations within 0.1% of QuantLib
2. **Performance**: < 100ms for full field computation
3. **Robustness**: Handle 10,000+ options without memory issues
4. **Predictive Power**: Regime detection AUC > 0.7
5. **Backtesting**: Sharpe > 1.5 on historical data

---

## Resources Needed

### Data Sources
- [ ] Options market data (consider CBOE DataShop, IVolatility)
- [ ] Historical trade & quote data
- [ ] VIX futures (for vanna validation)

### Compute
- [ ] Development machine (local)
- [ ] Production server (cloud) for real-time
- [ ] Database (PostgreSQL/TimescaleDB)

### Libraries
- [x] NumPy, SciPy, pandas
- [ ] QuantLib (for validation)
- [ ] statsmodels (for regression)
- [ ] plotly/matplotlib (visualization)
