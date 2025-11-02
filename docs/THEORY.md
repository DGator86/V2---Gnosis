# DHPE Theoretical Framework

Based on: "Dynamic Gamma, Vanna, and Charm Fields in a Time–Price Landscape"

## Overview

The Dealer Hedge Pressure Engine (DHPE) models option dealers' market impact through three Greek-derived fields that overlay the time-price landscape:

- **Gamma Field (Φ_Γ)**: Measures rate of change of delta with respect to price
- **Vanna Field (Φ_Vanna)**: Measures delta sensitivity to volatility changes  
- **Charm Field (Φ_Charm)**: Measures delta decay over time

## Mathematical Foundations

### 1. Greek Formulas (Black-Scholes)

#### Gamma
```
Γ = (e^(-qτ) * n(d₁)) / (S * σ * √τ)
```
Where:
- n(d₁) = standard normal density
- q = dividend yield
- σ = implied volatility
- τ = time to expiration
- S = spot price

**Key Property**: Always positive for long options (convexity)

#### Vanna
```
Vanna = -e^(-qτ) * (d₂/σ) * n(d₁)
```
Where d₂ = d₁ - σ√τ

**Key Property**: Captures how delta changes with volatility shifts

#### Charm (Delta Decay)
```
Charm = -e^(-qτ) * [n(d₁) * ((2rτ - d₂σ√τ)/(2τσ√τ))] 
```

**Key Property**: Negative for calls and puts (delta decreases over time)

### 2. Field Aggregation

To compute pressure fields, aggregate across all option positions:

```python
# Dollar Gamma for option i
G$_i = Γ_i * S² * OI_i * M

# Dollar Vanna for option i  
V$_i = Vanna_i * S * OI_i * M

# Dollar Charm for option i (per minute)
C$_i = Charm_i * S * OI_i * M

# Aggregate fields
Φ_Γ(t,S) = Σ G$_i      # $ per 1-point S move
Φ_Vanna(t,S) = Σ V$_i  # $ per ΔS per Δσ  
Φ_Charm(t,S) = Σ C$_i  # $ per minute
```

Where:
- OI_i = open interest (number of contracts)
- M = contract multiplier (e.g., 100 for equity options)
- Sign depends on dealer position (long/short)

### 3. Market Dynamics Equation

The enhanced hedge pressure model incorporates these fields:

```
(1 - κΨ_t) dS_t = κw_CH * Φ_Charm(t)dt + μdt + σdW_t
```

Where:
- **Ψ_t** = combined gamma/vanna pressure = w_Γ*Φ_Γ(t) + w_Vanna*Φ_Vanna(t)
- **κ** = market impact intensity (Kyle's lambda × S)
- **w_Γ, w_Vanna, w_CH** = calibrated weights

**Feedback Factor**: (1 - κΨ_t) represents market amplification/dampening
- If Ψ_t > 0 (long gamma): stabilizing, coefficient < 1
- If Ψ_t < 0 (short gamma): destabilizing, risk of κΨ_t → 1

### 4. Green's Function for Liquidity Operator

The pressure potential Π solves:

```
(-∂_x λ⁻¹ ∂_x + κ²) K = δ(x)
```

Where:
- λ(x) = Amihud illiquidity at price x
- κ = screening parameter
- K = Green's kernel

This formulation accounts for liquidity's spatial variation and screening effects.

## Market Impact Mechanisms

### Gamma Regime Effects

**Long Gamma (Φ_Γ > 0)**:
- Dealers sell into rallies, buy into dips
- **Stabilizing**: Dampens volatility
- Market exhibits mean reversion
- Realized vol < Implied vol

**Short Gamma (Φ_Γ < 0)**:
- Dealers buy into rallies, sell into dips  
- **Destabilizing**: Amplifies volatility
- Market exhibits momentum
- Realized vol > Implied vol
- Risk of cascading moves

**Empirical Evidence**:
- All large S&P 500 moves (>1.5%) occurred when aggregate gamma was negative
- Positive gamma correlates with intraday mean reversion
- "Gamma pinning" near large strikes at expiry

### Vanna Feedback Loops

**Vanna = "Volatility Feedback Engine"**

Spot-Vol Correlation Effects:
```
Market Down → Vol Up → Vanna triggers dealer selling → Further down → Vol higher → ...
```

**Critical Observations**:
- Moneyness matters: OTM vs ITM have opposite vanna signs
- Typical positioning: customers long OTM puts, short OTM calls
- This creates inherently unstable feedback in sell-offs
- "Vanna is gamma's evil twin"

**Historical Impact**:
- 2008 Crisis: VEX ~ -$400M per 1% S&P move
- March 2020: Extreme negative vanna during COVID crash
- These were among most volatile periods in history

### Charm Time Decay

**Charm = "Delta Drift"**

Creates persistent bid/offer throughout day:
- Short puts: Charm → persistent bid (dealers buy)
- Short calls: Charm → persistent offer (dealers sell)
- Long options: Opposite flows

**"Decay Wind" Metric**:
```python
D_H = κ * w_CH * Φ_Charm(t) × H
```
Estimates cumulative price impact over horizon H

**Expiration Effects**:
- "OpEx hour" (last hour before expiry)
- Rapid delta unwinding
- Can cause sharp moves as positions resolve

## Liquidity Integration

### Kyle's Lambda (λ)

Measures price impact per unit of flow:
```
λ(t) = coefficient from: ΔP_t = λ(t) × SignedFlow_t
```

Typical values for S&P 500:
- Normal conditions: 1e-6 to 1e-5 per dollar
- Stressed conditions: 10x to 100x higher
- $1B flow → 1-10% index move (if unabsorbed)

### Dimensionless Impact Intensity
```
κ = S · λ(t)
```

Typical range: 0.1% to few % for indices

**Risk Management**: Keep |κΨ| < 0.8 with 99% probability to avoid feedback instability

## Implementation Requirements

### Data Inputs

1. **Options Chain**:
   - Strike, expiry, type (call/put)
   - Bid/ask prices, volume, open interest
   - Implied volatility (or compute from prices)

2. **Underlying Data**:
   - Spot price, historical prices
   - Volume, order flow
   - Dividend yield, risk-free rate

3. **Position Data**:
   - Dealer long/short classification
   - Trade classification (Lee-Ready algorithm)
   - Open interest changes

### Processing Pipeline

1. **Vol Surface Construction**:
   - Use SSVI or similar parametrization
   - Fill gaps, ensure smoothness and arbitrage-free

2. **Greek Computation**:
   - Calculate Γ, Vanna, Charm for each option
   - Convert to dollar exposures (G$, V$, C$)
   - Handle units properly (charm → per-minute)

3. **Field Aggregation**:
   - Sum across all positions
   - Weight by dealer positioning
   - Project onto price grid (sticky-delta)

4. **Liquidity Estimation**:
   - Measure Kyle's λ from microstructure
   - Compute Amihud illiquidity from bars
   - Time-varying calibration

5. **Potential Computation**:
   - Build Green's kernel
   - Convolve sources with kernel
   - Compute gradients (spatial, temporal)

### Key Algorithms

#### Sticky-Delta Projector
Maps strikes → moneyness bins that move with spot:
```python
moneyness = log(K/S) / (σ√τ)  # delta-neutral log-moneyness
bin_idx = quantize(moneyness, bins)
```

#### Trade Classification (Lee-Ready)
Determines trade initiator → dealer position:
```python
if trade_price > midpoint:
    initiator = "buyer"  # dealer sold (short)
elif trade_price < midpoint:
    initiator = "seller"  # dealer bought (long)
else:
    use_tick_rule()
```

#### FFT Convolution for Potential
```python
Π(x) = FFT⁻¹[FFT(sources) * FFT(kernel)]
```
Fast O(N log N) convolution for large grids

## Market Regime Classification

### Low-Vol Regime (Stable)
- Φ_Γ > 0 (dealers long gamma)
- Low κ (high liquidity)
- Vanna benign
- RV << IV (vol risk premium)
- Mean-reverting price action

### High-Vol Regime (Crisis)
- Φ_Γ < 0 (dealers short gamma)
- High κ (low liquidity)
- Large negative vanna
- RV >> IV
- Trending/momentum price action
- Risk of feedback loops

### Transition Indicators
- Gamma flip level (where Φ_Γ changes sign)
- Amplification factor A_t = 1/(1-κΨ_t) approaching 1
- VEX (vanna exposure) turning deeply negative
- Charm creating unusual drift patterns

## References

This framework synthesizes:
- Black-Scholes partial derivatives theory
- Market microstructure (Kyle's lambda)
- Empirical dealer positioning studies
- SqueezeMetrics Implied Order Book methodology
- 0DTE options research (2023-2025)
- Historical crisis analysis (1987, 2008, 2020)

## Next Steps for Implementation

1. Implement proper sticky-delta projector
2. Build vol surface interpolation (SSVI)
3. Add trade classification engine
4. Implement FFT-based convolution
5. Real-time λ estimation from order flow
6. Regime detection and alerts
7. Backtesting framework with historical positioning
