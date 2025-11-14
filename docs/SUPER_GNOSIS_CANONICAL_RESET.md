# SUPER GNOSIS — CANONICAL RESET (NOV 2025)

## 1. Core Interpretation Model

Foundational physics-style assumptions for the system:

1. **Price** behaves as a particle traveling within a supply–demand field.
2. **Gamma, vanna, charm** operate as pressure fields that distort the elasticity of the supply–demand curves.
   - Changes in elasticity correspond to changes in the energy required to move price.
3. **Liquidity pools** act as potential wells or barriers that form support/resistance attractors.
4. **Engines** translate raw market inputs into measurable field values.
5. **Agents** interpret the fields and forward actionable suggestions.
6. The **Composer** integrates all interpretations and determines whether the market state is actionable.
7. The **Trade Agent** formulates the actual trade strategy.
8. **Results** and **Quality** agents handle feedback and machine-learning optimization.

All modules are designed to be modular, atomic, and implementation-friendly.

---

## 2. Engine Layer (Raw Inputs → Structured, Quantifiable Data)

Engines never make trading decisions. They purely convert raw market data into structured, standardized metrics.

### A. Hedge Engine

**Role:** Model Greek-derived pressure fields.

**Inputs:**
- Full option chain
- Dealer positioning data (where available)
- Open interest & distribution
- Volatility surface
- Market maker flow (implied)

**Outputs** (standardized numeric arrays or scalars):
1. **Greeks Analysis (base metrics)**
   - Δ, Γ, Θ, Vega, Vanna, Charm (dΔ/dt)
2. **Field Plotters (normalized)**
   - Gamma field: upward/downward pressure, curvature intensity
   - Vanna field: cross-vol-delta sensitivity
   - Charm field: intraday hedge decay pressure
3. **Other Influential Variables**
   - Dealer sign estimate
   - Net gamma exposure
   - Vol compression/expansion forces
   - Whale OI clusters
   - Institutional hedging bias
   - Risk-reversal skew pressure

**Output Container:** `HedgeEnginePayload` (structured model containing all standardized fields).

### B. Liquidity Engine

**Role:** Translate liquidity structure into energy barriers.

**Inputs:**
- Volume profile
- Order flow (delta, CVD)
- Dark-pool prints
- Unusual volume
- Bid-ask depth
- DIX/GEX (if available)
- Liquidity maps from exchanges

**Outputs:**
1. **Liquidity Pools**
   - Price magnet zones
   - High-volume nodes
   - Void regions (low-liquidity acceleration zones)
2. **Order Flow Metrics**
   - Aggressive buyer/seller imbalance
   - CVD trend
   - Tape velocity
   - Volume delta shifts
3. **DIX / Unusual Volume**
   - Dark pool sentiment score
   - Volume anomaly index
   - Whale absorption flags

**Output Container:** `LiquidityEnginePayload`.

### C. Sentiment Engine

**Role:** Translate technicals and human sentiment into directional bias.

**Inputs:**
- Technical indicators
- News sentiment (NLP)
- Public sentiment (social)
- Insider buys/sells
- Macro economic releases
- Corporate events (earnings, guidance, filings)

**Outputs:**
1. **Technical Indicators**
   - RSI, MACD, Bollinger, Keltner, trend state
   - Market structure (Wyckoff phase)
2. **News & Public Sentiment**
   - NLP sentiment score
   - Velocity of sentiment change
   - Emerging risk events
3. **Insider Trading**
   - Aggregated insider buy/sell strength
   - Historical predictive index
4. **Macro & Significant Events**
   - CPI/FOMC proximity risk
   - Earnings volatility estimate
   - Geopolitical tension risks

**Output Container:** `SentimentEnginePayload`.

### D. Standardization Processor

**Role:** Convert all engine outputs into common scaling, time synchronization, and dimensional consistency.

**Processes:**
- Z-score normalization
- Min-max scaling
- Temporal alignment (shared timestamps)
- Dimension reduction (PCA or orthogonal encoding)
- Confidence score standardization

**Output Container:** `UnifiedMetricsBundle` (consumed by all agents).

---

## 3. Agent Layer (Interpret Engines → Produce Suggestions)

Agents never ingest raw market data—only standardized engine outputs. Each agent answers one specific question.

### E. Hedge Agent

**Role:** Interpret Greek pressure fields and provide directional and volatility bias.

**Reads:**
- `HedgeEnginePayload`
- `UnifiedMetricsBundle`

**Outputs:**
- Upward/downward pressure probability
- Field intensity score (0–100)
- Volatility expansion/compression signal
- Hedge-pressure map summary
- Confidence

### F. Liquidity Agent

**Role:** Interpret liquidity barriers, magnets, and acceleration zones.

**Reads:**
- `LiquidityEnginePayload`
- `UnifiedMetricsBundle`

**Outputs:**
- Support/resistance probability
- Liquidity barrier strength
- Liquidity-driven acceleration zones
- Large player absorption flags
- Confidence

### G. Sentiment Agent

**Role:** Interpret human and technical sentiment state.

**Reads:**
- `SentimentEnginePayload`
- `UnifiedMetricsBundle`

**Outputs:**
- Bullish/bearish probability
- Sentiment momentum
- Technical trend validity
- Event-driven risk escalation flags
- Confidence

### H. Composer Agent

**Role:** Combine agent signals and decide whether the information is actionable.

**Reads:**
- Hedge Agent output
- Liquidity Agent output
- Sentiment Agent output

**Process:**
- Weighted fusion
- Conflict-resolution logic
- Actionability testing (thresholds, consensus, volatility checks)

**Outputs:**
- Market actionable? (yes/no)
- Expected direction
- Expected magnitude
- Expected volatility regime
- Confidence

---

## 4. Trade & Feedback Layer

### I. Trade Agent

**Role:** Generate trade strategies when the Composer flags the market state as actionable.

**Reads:**
- Composer output
- Hedge Agent output
- Liquidity Agent output
- Sentiment Agent output

**Produces full trade plans:**
- Stock strategy (buy/sell, levels, invalidation)
- Options strategy (calls, puts, spreads, condors, calendars, diagonals, etc.)
- Contract quantity
- Entry price
- Exit target
- Stop loss
- Estimated profit
- Risk score
- Position size (stateless, recalculated each time)

### J. Results Agent

**Role:** Track realized performance.

**Reads:**
- Executed trades
- Real-time P&L
- Win/loss metrics
- Volatility drag
- Slippage
- Dealer-field prediction accuracy

**Outputs:**
- Strategy effectiveness reports
- Agent accuracy metrics
- Drift analysis

### K. Quality Improvement Agent

**Role:** Machine-learning layer responsible for tuning the system.

**Reads:**
- Results Agent output
- Historical `UnifiedMetricsBundle`
- Engine/agent predictions vs. outcomes

**Techniques Used:**
- Meta-learning
- Reinforcement learning
- Bayesian updates
- Gradient-based optimization
- Feature-importance recalibration

**Outputs:**
- Updated weights for the Composer
- Updated transforms for the Standardization Processor
- Updated model parameters for engines and agents
- Updated trade candidate ranking logic

This agent never trades—its sole purpose is optimization.

---

## 5. Confirmation & Next Steps

This document establishes the clean reset architecture with no deviations from the specified structure.

**Suggested next steps:**
1. Define exact API schemas for each engine output.
2. Build code scaffolding (folders and Python classes).
3. Implement each engine individually.
4. Implement agents.
5. Wire the Composer, Trade Agent, Results Agent, and Quality Improvement Agent together.
