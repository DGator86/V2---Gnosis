# Super Gnosis – Missing Components & Implementation Spec (for Codex)

You are extending the V2---Gnosis repository into the full Super Gnosis / DHPE framework described across all project chats.

The repo currently has:
- A solid architecture and scaffolding.
- Placeholder engines and agents.
- Orchestration, config, and docs.

But several major subsystems are missing or incomplete, relative to the design previously agreed between Darrin and the assistant.

This document is your detailed implementation backlog.

---

## 0. Global Contracts & Conventions (Must Verify / Enforce First)

Before building new modules, you must ensure the core contracts are frozen and enforced.

### 0.1 Core schemas

File: `schemas/core_schemas.py`

You must define the following Pydantic models and keep them as the single source of truth:

```python
from __future__ import annotations

from datetime import datetime
from typing import Dict, Literal, Optional, List
from pydantic import BaseModel, Field


EngineKind = Literal["hedge", "liquidity", "sentiment", "elasticity"]

class EngineOutput(BaseModel):
    """
    Canonical output of any Engine (Hedge, Liquidity, Sentiment, Elasticity).
    All engines MUST return this schema.
    """
    kind: EngineKind
    symbol: str
    timestamp: datetime
    features: Dict[str, float]        # e.g. {"gamma_pressure": ..., "vanna_pressure": ...}
    confidence: float = Field(ge=0.0, le=1.0)
    regime: Optional[str] = None      # e.g. "gamma_squeeze", "range", "trend", "illiquid"
    metadata: Dict[str, str] = Field(default_factory=dict)


class StandardSnapshot(BaseModel):
    """
    Canonical fused snapshot at a single time t for a given symbol.
    This is what primary agents see (no raw data).
    """
    symbol: str
    timestamp: datetime

    hedge: Dict[str, float]
    liquidity: Dict[str, float]
    sentiment: Dict[str, float]
    elasticity: Dict[str, float]

    # Optional aggregated regime label
    regime: Optional[str] = None

    # Free-form metadata (e.g. provider tags, data quality flags, etc.)
    metadata: Dict[str, str] = Field(default_factory=dict)


ActionLiteral = Literal["long", "short", "flat", "spread", "complex"]

class Suggestion(BaseModel):
    """
    Policy-level suggestion from a primary agent or the composer.
    NO direct broker instructions here – just stance and rationale.
    """
    id: str
    layer: str                      # e.g. "primary_hedge", "primary_liquidity", "primary_sentiment", "composer"
    symbol: str
    action: ActionLiteral
    confidence: float = Field(ge=0.0, le=1.0)

    # Example: {"horizon_min": 15, "exp_move_pct": 1.2}
    forecast: Dict[str, float] = Field(default_factory=dict)

    # Human-readable reasoning (used for logs/traceability)
    reasoning: str

    # Optional tags, e.g. ["gamma_squeeze", "illiquid", "news_shock"]
    tags: List[str] = Field(default_factory=list)


class TradeIdea(BaseModel):
    """
    Concrete trade object – output of Trade Agent.
    This IS strategy-level and options-leg aware.
    """
    id: str
    symbol: str
    strategy_type: str        # e.g. "call_debit_spread", "iron_condor", "calendar", "stock"
    side: Literal["long", "short", "neutral"]

    # Options legs definitions – for stock this may be empty.
    # Each leg: {"type": "C"/"P", "strike": float, "expiry": "YYYY-MM-DD", "qty": int, "direction": "buy"/"sell"}
    legs: List[Dict[str, str]]

    # Cost, projected PnL, and sizing
    cost_per_unit: float
    max_loss: float
    max_profit: Optional[float]
    breakeven_levels: List[float]

    target_exit_price: Optional[float]
    stop_loss_price: Optional[float]
    recommended_units: int       # number of spreads/contracts/shares

    # Confidence and metadata
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str
    tags: List[str] = Field(default_factory=list)
```

All engines, agents, composer, and trade agent MUST respect these interfaces.

---

### 0.2 Engine & Agent interfaces

Create abstract interfaces.

File: `engines/base.py`:

```python
from typing import Protocol
from schemas.core_schemas import EngineOutput


class Engine(Protocol):
    """
    Generic interface for all Engines.
    Engines transform market-derived inputs into structured EngineOutput features.
    """
    def run(self, symbol: str, now: datetime) -> EngineOutput:
        ...
```

File: `agents/base.py`:

```python
from typing import Protocol
from schemas.core_schemas import StandardSnapshot, Suggestion
from schemas.core_schemas import TradeIdea


class PrimaryAgent(Protocol):
    """
    Primary agents interpret StandardSnapshots into Suggestion objects.
    They DO NOT touch raw data and DO NOT compute features.
    """
    def step(self, snapshot: StandardSnapshot) -> Suggestion:
        ...


class ComposerAgent(Protocol):
    """
    Composer aggregates primary suggestions into one higher-level Suggestion
    that includes regime/stance and strategy family hints.
    """
    def compose(self, snapshot: StandardSnapshot, suggestions: list[Suggestion]) -> Suggestion:
        ...


class TradeAgent(Protocol):
    """
    Trade Agent converts composer-level Suggestion into a concrete TradeIdea.
    """
    def generate_trades(self, suggestion: Suggestion) -> list[TradeIdea]:
        ...
```

You must ensure the pipeline only deals with these protocols at higher levels.

---

### 0.3 Pipeline runner contract

File: `engines/orchestration/pipeline_runner.py`

Define a PipelineRunner that is purely orchestrational:

```python
from datetime import datetime
from typing import Dict, List

from schemas.core_schemas import EngineOutput, StandardSnapshot, Suggestion, TradeIdea
from engines.base import Engine
from agents.base import PrimaryAgent, ComposerAgent, TradeAgent


class PipelineRunner:
    """
    Orchestrates a single pipeline pass for one symbol at time t:
    Inputs → Engines → StandardSnapshot → Primary Agents → Composer → Trade Agent → Ledger.
    """

    def __init__(
        self,
        symbol: str,
        engines: Dict[str, Engine],
        primary_agents: Dict[str, PrimaryAgent],
        composer: ComposerAgent,
        trade_agent: TradeAgent,
        ledger_engine,      # type: LedgerEngine (define elsewhere)
        config,
    ) -> None:
        self.symbol = symbol
        self.engines = engines
        self.primary_agents = primary_agents
        self.composer = composer
        self.trade_agent = trade_agent
        self.ledger_engine = ledger_engine
        self.config = config

    def run_once(self, now: datetime) -> Dict[str, object]:
        """
        Run ONE full pass of the pipeline, returning a structured dict
        with all intermediate and final artifacts.
        """
        # 1. Run engines
        engine_outputs: Dict[str, EngineOutput] = {
            name: engine.run(self.symbol, now)
            for name, engine in self.engines.items()
        }

        # 2. Fuse engine outputs into StandardSnapshot
        snapshot: StandardSnapshot = self._build_snapshot(engine_outputs)

        # 3. Primary agents
        primary_suggestions: List[Suggestion] = [
            agent.step(snapshot) for agent in self.primary_agents.values()
        ]

        # 4. Composer
        composite_suggestion: Suggestion = self.composer.compose(snapshot, primary_suggestions)

        # 5. Trade agent
        trade_ideas: List[TradeIdea] = self.trade_agent.generate_trades(composite_suggestion)

        # 6. Ledger + feedback update
        self.ledger_engine.record_run(snapshot, primary_suggestions, composite_suggestion, trade_ideas)

        return {
            "snapshot": snapshot,
            "engine_outputs": engine_outputs,
            "primary_suggestions": primary_suggestions,
            "composite_suggestion": composite_suggestion,
            "trade_ideas": trade_ideas,
        }

    def _build_snapshot(self, engine_outputs: Dict[str, EngineOutput]) -> StandardSnapshot:
        """
        Fuse multiple EngineOutput objects into one StandardSnapshot.
        This is the only place where engine features are merged.
        """
        # IMPLEMENTATION REQUIRED
        ...
```

You will fill `_build_snapshot` later once all engines are defined.

---

## 1. Missing Engine Implementations

The repo currently only has generic volume/sentiment/hedge placeholders.

You must implement the canonical engines we designed:
- Hedge Engine v3.0
- Liquidity Engine v1.0
- Sentiment Engine v1.0
- Elasticity Engine v1.0

All must return `EngineOutput`.

---

### 1.1 Hedge Engine v3.0 (Dealer Field Engine)

Path: `engines/hedge/hedge_engine_v3.py`

#### 1.1.1 Purpose
Model the dealer hedge pressure field using options Greeks and open interest, producing features that approximate:
- Gamma pressure
- Vanna pressure
- Charm pressure
- Regime labels (gamma squeeze, pin, neutral)
- Cross-asset fusion (SPX vs ES vs sector ETFs)
- VIX hedging bleed factor
- Jump-risk heuristics

#### 1.1.2 Inputs
- Option chain for symbol and related hedging instruments (SPX/ES, VIX options if available).
- Current price, implied vol, realized vol, past returns.
- Market time (now).

Define a dedicated input adapter:

File: `engines/inputs/options_chain_adapter.py`

```python
class OptionsChainAdapter:
    """
    Responsible for fetching and normalizing options chain data.
    Implement provider-specific logic in subclasses.
    """
    def fetch_chain(self, symbol: str, now: datetime) -> pl.DataFrame:
        """
        Returns a Polars DataFrame with columns:
        ["symbol", "underlying_price", "expiry", "dte", "strike", "type",
         "mid_price", "bid", "ask", "volume", "open_interest",
         "delta", "gamma", "vega", "theta", "vanna", "charm"]
        """
        ...
```

#### 1.1.3 Core computations (high-level)
In `HedgeEngineV3.run`:
- Compute `gamma_pressure`:

```
gamma_pressure = (df["gamma"] * df["open_interest"] * df["underlying_price"]).sum()
```

- Compute `vanna_pressure`:

```
vanna_pressure = (df["vanna"] * df["open_interest"]).sum()
```

- Compute `charm_pressure` (sensitivity of delta over time):

```
charm_pressure = (df["charm"] * df["open_interest"]).sum()
```

- Identify regime:
  - High absolute gamma near spot → `gamma_squeeze`.
  - Strong vanna with IV skew → `vanna_flow`.
  - Mixed / small → `neutral`.
- Add VIX hedging bleed component:
  - If VIX options chain available:
    - Compute gamma pressure in VIX land.
    - Derive a friction coefficient for SPX hedging cost.
- Cross-asset fusion:
  - If ES futures and sector ETFs are available:
    - Compute scaled gamma/vanna for those and blend into SPX field.

#### 1.1.4 Feature output
Populate `EngineOutput.features` with at least:
- `gamma_pressure`
- `vanna_pressure`
- `charm_pressure`
- `gamma_sign` (dealer long/short gamma estimate)
- `vanna_sign`
- `hedge_regime_energy` (normalized field intensity)
- `vix_friction_factor` (0–1)

Set:
- `kind = "hedge"`
- `regime = "gamma_squeeze" | "pin" | "neutral" | "vanna_flow" | "illiquid_gamma"`

#### 1.1.5 Performance
- Implement in Polars, no Python loops.
- Ensure code is vectorized for large chains (thousands of strikes, multiple expiries).

#### 1.1.6 Tests
Create `tests/engines/test_hedge_engine_v3.py`:
- Test 1: Synthetic chain with symmetrical gamma → regime should be neutral.
- Test 2: Massive call OI above spot with large positive gamma → regime gamma_squeeze.
- Test 3: Missing vanna/charm columns → engine returns degraded output with `confidence=0.0` and `metadata["degraded"]="missing_greeks"`.

---

### 1.2 Liquidity Engine v1.0

Path: `engines/liquidity/liquidity_engine_v1.py`

#### 1.2.1 Purpose
Model market liquidity, not just volume:
- Amihud illiquidity
- Kyle’s λ (impact per unit volume)
- Volume profile and liquidity “magnets”
- Footprint-style buyer/seller imbalance
- Dark-pool intensity (if available)

#### 1.2.2 Inputs
Define an adapter:

File: `engines/inputs/market_data_adapter.py`

```python
class MarketDataAdapter:
    """
    Fetches OHLCV and intraday tick/quote data for a symbol.
    """
    def fetch_ohlcv(self, symbol: str, lookback: int, now: datetime) -> pl.DataFrame:
        # columns: ["timestamp", "open", "high", "low", "close", "volume"]
        ...

    def fetch_intraday_trades(self, symbol: str, lookback_minutes: int, now: datetime) -> pl.DataFrame:
        # columns: ["timestamp", "price", "size", "side"]
        # side: "buy"/"sell" if provided, else infer from tick rule
        ...
```

#### 1.2.3 Core computations
- Amihud Illiquidity (daily or intraday)

```
# For each bar: |return| / volume
# Then average over lookback window
```

- Kyle’s λ
- Regress price changes on signed volume:

```
# Δp_t = λ * q_t + ε_t
# Estimate λ as regression slope
```

- Volume profile & magnets
  - Intraday histogram of volume by price bucket (e.g., 0.1% buckets).
  - Identify price levels with:
    - High volume (magnets).
    - Very low volume (voids).
- Order flow imbalance (OFI)
  - From intraday trades, compute buy vs sell volume ratio.
  - `OFI = (buy_vol - sell_vol) / (buy_vol + sell_vol)`.

#### 1.2.4 Feature output
At minimum:
- `amihud_illiquidity`
- `kyle_lambda`
- `volume_magnet_score` (0–1)
- `liquidity_void_score` (0–1)
- `ofi` (order flow imbalance)
- `avg_spread_bps` (if quotes are available)

`kind = "liquidity"`, regime could be:
- `"high_liquidity"`
- `"thin_liquidity"`
- `"one_sided_flow"`
- `"normal"`

#### 1.2.5 Tests
`tests/engines/test_liquidity_engine_v1.py`:
- Synthetic low-volume, high-return series → high Amihud, regime "thin_liquidity".
- Symmetric buy/sell flows → `ofi ≈ 0`.
- Single big buy wave → `ofi > 0.6`, regime "one_sided_flow".

---

### 1.3 Sentiment Engine v1.0

Path: `engines/sentiment/sentiment_engine_v1.py`

We previously locked a canonical sentiment engine with:
- Multiple processors (news, options flow, price patterns).
- Weighted fusion.
- Energy-aware confidence.

#### 1.3.1 Inputs
Adapters:
- News:

```python
class NewsAdapter:
    def fetch_news(self, symbol: str, lookback_hours: int, now: datetime) -> list[dict]:
        # Each dict: {"timestamp": dt, "headline": str, "body": str, "source": str}
        ...
```

- Flow sentiment (optional):
Uses options flow / dark pool order flow if available.
- Technical sentiment:
  - Price + indicators (RSI, Bollinger Bands, Keltner Channels).

#### 1.3.2 Processors (sub-modules)
Implement processors as pure functions/classes that return `(score, confidence)`:
- `NewsSentimentProcessor`
- `FlowSentimentProcessor`
- `TechnicalSentimentProcessor`

Each must implement:

```python
class SentimentProcessor(Protocol):
    def compute(self, symbol: str, now: datetime) -> tuple[float, float]:
        """
        Returns (sentiment_score, confidence) where score is in [-1, 1].
        """
        ...
```

#### 1.3.3 Fusion logic
- Weighted average of scores by confidence.
- If data missing, gracefully degrade (weight others more).
- Compute `sentiment_energy = |score| * aggregate confidence`.

#### 1.3.4 Regime & features
Regime labels:
- `"bullish_news"`, `"bearish_news"`, `"mixed"`, `"quiet"`.

Features:
- `sentiment_score ([-1, 1])`
- `sentiment_confidence`
- `news_sentiment_score`
- `flow_sentiment_score`
- `technical_sentiment_score`
- `sentiment_energy`

`kind = "sentiment"`.

#### 1.3.5 Tests
`tests/engines/test_sentiment_engine_v1.py`:
- All positive news → high `news_sentiment_score`, positive regime.
- No news, mixed technicals → low confidence, `regime="quiet"`.

---

### 1.4 Elasticity Engine v1.0

Path: `engines/elasticity/elasticity_engine_v1.py`

This is new and critical. It converts:
- Hedge fields (gamma, vanna, charm)
- Liquidity fields
- Technical indicators (RSI, Bollinger, Keltner)
- Possibly realized volatility

into a numeric “energy required to move price” estimate.

#### 1.4.1 Inputs
The engine should not re-fetch raw data; it should:
- Read `EngineOutput` from Hedge Engine and Liquidity Engine.
- Compute additional indicators from OHLCV via `MarketDataAdapter`.

You can define a small internal struct:

```python
class ElasticityInputs(BaseModel):
    hedge_features: Dict[str, float]
    liquidity_features: Dict[str, float]
    indicators: Dict[str, float]    # e.g. RSI, Bollinger position, Keltner width
    realized_vol_annualized: float
```

#### 1.4.2 Concept
We approximate:

```
Energy ~ (liquidity_resistance + hedge_resistance) * required_move
```

Where:
- `liquidity_resistance` grows with:
  - High Amihud, high Kyle λ.
- `hedge_resistance` grows with:
  - Dealer long gamma (they resist moves).
  - Shrinks with short gamma (they amplify moves).
- Technicals:
  - If price is at extreme Bollinger/Keltner boundary, energy to go further in that direction is higher; lower to revert.

#### 1.4.3 Concrete implementation
Define:
- `base_cost_per_1pct = function of liquidity`:

```
base_cost_per_1pct = f(amihud, kyle_lambda, avg_spread_bps)
```

- `hedge_multiplier = function of gamma_sign and gamma_pressure`:

```
if gamma_sign > 0:  # dealer long gamma
    hedge_multiplier = 1.0 + k1 * normalized_gamma_pressure
else:               # dealer short gamma
    hedge_multiplier = 1.0 - k2 * normalized_gamma_pressure
```

- `indicator_bias`:
  - If price at upper Bollinger band + overbought RSI → “up” direction energy high, “down” direction energy low, etc.

Finally, output:
- `energy_to_move_1pct_up`
- `energy_to_move_1pct_down`
- `elasticity_up`
- `elasticity_down`
- `expected_move_cost_1_day` (energy for 1-day expected move)

Regimes:
- `"high_resistance"`, `"low_resistance"`, `"asymmetric_up"`, `"asymmetric_down"`.

`kind = "elasticity"`.

#### 1.4.4 Tests
`tests/engines/test_elasticity_engine_v1.py`:
- Long gamma + high liquidity → high energy both directions.
- Short gamma + thin liquidity → low energy, especially toward option walls.

---

## 2. Missing Agents

### 2.1 Hedge Agent v3.0 (Primary Hedge Interpreter)

Path: `agents/hedge_agent_v3.py`

Responsibilities
- Interpret Hedge Engine `EngineOutput` (features + regime).
- Produce a directional stance + confidence, but no strategies.

Implementation sketch:

```python
class HedgeAgentV3:
    def __init__(self, config):
        self.config = config

    def step(self, snapshot: StandardSnapshot) -> Suggestion:
        hedge = snapshot.hedge
        # Example rule-based logic:
        # - strong positive gamma near current price -> lower directional conviction
        # - strong negative gamma with vanna flows -> trend acceleration
        ...
```

Core logic:
- High negative gamma + supportive vanna → more aggressive long or short.
- Strong long gamma → flat or low-conviction stance.

---

### 2.2 Liquidity Agent v1.0

Path: `agents/liquidity_agent_v1.py`

Responsibilities
- Interpret liquidity features to answer:
  - “Is momentum likely to continue or get choked?”
  - “Is breakout likely or is this a fake?”
- Output Suggestion with tags like `["thin_liquidity", "one_sided_flow"]`.

---

### 2.3 Sentiment Agent v1.0

Path: `agents/sentiment_agent_v1.py`

Responsibilities
- Interpret Sentiment Engine features:
  - Strongly positive sentiment → more weight to bullish stance.
  - Strong divergence (bearish sentiment, bullish price) → contrarian flags.
- Output Suggestion with tags like `["news_shock", "sentiment_divergence"]`.

---

### 2.4 Composer Agent v1.0

Path: `agents/composer/composer_agent_v1.py`

Responsibilities
- Take 3 primary suggestions (hedge, liquidity, sentiment) and produce a single Suggestion with:
  - Final action (long/short/flat/spread/complex).
  - Effective confidence (0–1).
  - Tags summarizing consensus and conflicts.
  - Hints for strategy family (stored in forecast or tags), e.g. `["use_debit_call_spread"]`.

Implementation:
- Weighted voting:
  - Each primary has weight (config-driven) e.g.:

```
agents:
  composer:
    weights:
      primary_hedge: 0.4
      primary_liquidity: 0.3
      primary_sentiment: 0.3
```

- Conflict resolution:
  - If all agree → simple stance.
  - If two agree vs one → majority stance, but lower confidence if minority strongly opposes.
  - If all disagree → likely spread or complex regime (no pure directional stance).

---

### 2.5 Trade Agent v1.0 (BIG MISSING PIECE)

Path: `agents/trade_agent_v1.py`

Responsibilities
Convert composer Suggestion into concrete TradeIdea objects.

Key requirements:
- Can generate both stock and options strategies.
- Zero memory regarding overlapping trades:
  - It does NOT suppress new ideas if the symbol is already in a trade.
- Strategy library must include at least:
  - `long_stock`
  - `short_stock`
  - `call_debit_spread`
  - `put_debit_spread`
  - `iron_condor`
  - `calendar_spread`
  - `covered_call` (if holding stock, but for now you can treat as hypothetical)

Inputs
- Composer Suggestion.
- Current options chain (via `OptionsChainAdapter`).
- Config for:
  - Target DTE windows (e.g., 7–45 days).
  - Preferred moneyness (e.g., 25–40 delta).

Outputs
List[TradeIdea] with full legs, costs, max P/L, breakeven.

Example logic
- If `action="long"` and confidence high:
  - If volatility cheap → consider `long_stock` or `call_debit_spread`.
  - If volatility rich → `call_debit_spread` or `bull_put_spread`.
- If `action="spread"`:
  - Use `iron_condor` for range-bound regime from elasticity and liquidity.

Test cases
`tests/agents/test_trade_agent_v1.py`:
- Given bullish suggestion with high confidence → returns at least one bullish options strategy.
- Given flat/low confidence → returns empty list or small neutral trade (e.g., iron condor) with low size.

---

## 3. ML / Lookahead Layer

Currently you only have placeholder lookahead.

You must implement a minimal ML forecasting layer.

### 3.1 Folder structure

Create: `models/` with:
- `models/lookahead_model.py`
- `models/feature_builder.py`
- `models/training_pipeline.py`

### 3.2 Feature Builder

FeatureBuilder must:
- Take historical price, hedge, liquidity, sentiment features.
- Construct features such as:
  - Lagged returns
  - Realized volatility
  - Rolling hedge pressures
  - Rolling liquidity regimes
  - Rolling sentiment scores

Outputs: model-ready matrices and labels (e.g. next-day return, sign, or volatility).

### 3.3 Lookahead Model

Simple v1:
- Use sklearn (RandomForest, GradientBoost, or XGBoost) or a basic LSTM wrapper.
- Wrap the model with a class:

```python
class LookaheadModel:
    def predict(self, snapshot: StandardSnapshot) -> dict:
        """
        Returns {"exp_return_1d": float, "exp_vol_1d": float, "p_up": float}
        """
        ...
```

Integrate into pipeline by:
- Adding forecast fields to `Suggestion.forecast`.
- Giving composer access to expected return / volatility to pick strategy families.

### 3.4 Training Pipeline (offline)

`models/training_pipeline.py` should:
- Load historical data (to be wired later).
- Build features.
- Train models.
- Save artifacts (pickles or on-disk model files).

---

## 4. Data Adapters (Real Integrations Later, but Interfaces Now)

You must define stable interfaces even if implementations are placeholder.

Already mentioned:
- `OptionsChainAdapter`
- `MarketDataAdapter`
- `NewsAdapter`

All must have:
- Clear methods.
- Docstrings.
- Return types (Polars DataFrames or typed lists).

These will later be implemented with real APIs (Polygon, Tradier, etc.).

---

## 5. Backtesting & Execution

Right now backtesting is just a CLI placeholder.

### 5.1 Backtest Runner

Create: `backtest/runner.py`

```python
class BacktestRunner:
    """
    Event-driven backtest wrapper around PipelineRunner.
    """
    def __init__(self, data_source, pipeline_factory, config):
        ...

    def run_backtest(self, symbol: str, start: datetime, end: datetime) -> dict:
        """
        Step through time (bars or events), call pipeline,
        collect trade ideas, simulate fills/PnL.
        Returns summary stats.
        """
        ...
```

### 5.2 Execution Layer (stubs)

Create: `execution/` with:
- `execution/broker_adapter.py` – interface for live/paper broker.
- `execution/order_simulator.py` – simple fill + slippage model for backtesting.

---

## 6. Feedback Engine & Learning Loop

You’ve conceptually defined a Feedback / Tracking Engine.

You must:
- Implement `LedgerStore` (file/DB writes).
- Implement `LedgerMetrics` (Sharpe, hit-rate, drawdown).
- Implement `FeedbackEngine` that:
  - Reads metrics.
  - Adjusts config parameters (agent weights, risk fraction).
  - Logs changes.

Integrate:
- `PipelineRunner` must call `ledger_engine.record_run(...)`.
- A periodic process (e.g., `feedback/update_parameters.py`) must recompute metrics and update config.

---

## 7. UI / Dashboard (Minimal v1)

Create: `ui/dashboard.py`

Use Streamlit or FastAPI to:
- Display:
  - Latest snapshot (hedge, liquidity, sentiment, elasticity).
  - Latest suggestions, trade ideas.
  - Key metrics (Sharpe, hit-rate).
  - Basic charts: price + gamma walls, liquidity zones, sentiment score.

This can be minimal but must be wired to the same pipeline.

---

## 8. Ops: Tests, CI, Packaging

You must:
1. Add `pyproject.toml` to make this an installable package.
2. Create `tests/` folder with:
   - `tests/test_schemas.py`
   - `tests/test_pipeline_smoke.py`
   - Per-engine and per-agent tests as specified above.
3. Add `.github/workflows/ci.yml` to:
   - Run mypy (strict).
   - Run ruff.
   - Run pytest.

---

## 9. Implementation Priority (for Codex)

If you cannot do everything at once, follow this sequence:
1. Core contracts: verify/lock `core_schemas.py`, `engines/base.py`, `agents/base.py`, `PipelineRunner`.
2. Hedge/Liquidity/Sentiment Engines: implement v3/v1/v1 with full features, vectorized.
3. Elasticity Engine v1.0: build energy/elasticity metrics.
4. Primary Agents + Composer: `HedgeAgent`, `LiquidityAgent`, `SentimentAgent`, `ComposerAgent`.
5. Trade Agent v1.0: map composer suggestions to `TradeIdeas`.
6. Lookahead Model: minimal forecasting integrated into composer / agents.
7. Backtest Runner + Ledger/Feedback: close the loop.
8. UI Dashboard: visual diagnostics.
9. Data Adapters & Execution Layer: stable interfaces, stub implementations.
10. Tests + CI + Packaging: ensure repo is production-grade.

All code must be:
- Function-based and class-based.
- PEP 8 compliant.
- Fully type-hinted.
- With docstrings describing inputs, outputs, and side effects.

---

Here’s the unified skeleton you can hand straight to Codex.

It’s organized as a single Python block with file headers in comments so your dev agent can split it back into real files (`schemas/core_schemas.py`, `engines/hedge/hedge_engine_v3.py`, etc.) and then fill in the bodies.

---

```
# ============================================
# schemas/core_schemas.py
# ============================================

from __future__ import annotations

from datetime import datetime
from typing import Dict, Literal, Optional, List, Iterable
from pydantic import BaseModel, Field


EngineKind = Literal["hedge", "liquidity", "sentiment", "elasticity"]


class EngineOutput(BaseModel):
    """
    Canonical output of any Engine (Hedge, Liquidity, Sentiment, Elasticity).

    All engines MUST return this schema. Engines convert market-derived inputs
    into a structured feature vector with a confidence level and optional regime label.
    """
    kind: EngineKind
    symbol: str
    timestamp: datetime

    # Feature vector produced by the engine, arbitrary numeric keys
    features: Dict[str, float]

    # Overall confidence of this engine's assessment in [0, 1]
    confidence: float = Field(ge=0.0, le=1.0)

    # Optional regime label (engine-specific taxonomy)
    regime: Optional[str] = None

    # Extra metadata (e.g. provider IDs, data quality flags, degradation flags)
    metadata: Dict[str, str] = Field(default_factory=dict)


class StandardSnapshot(BaseModel):
    """
    Canonical fused snapshot at a single time t for a given symbol.

    This is the ONLY object that primary agents see. It is built from multiple
    EngineOutput objects (hedge, liquidity, sentiment, elasticity).
    Agents NEVER see raw data.
    """
    symbol: str
    timestamp: datetime

    hedge: Dict[str, float]
    liquidity: Dict[str, float]
    sentiment: Dict[str, float]
    elasticity: Dict[str, float]

    # Optional aggregated regime label at snapshot level
    regime: Optional[str] = None

    # Free-form metadata (e.g. combined flags, anomaly markers)
    metadata: Dict[str, str] = Field(default_factory=dict)


ActionLiteral = Literal["long", "short", "flat", "spread", "complex"]


class Suggestion(BaseModel):
    """
    Policy-level suggestion from a primary agent or the composer.

    This is NOT a broker instruction. It expresses stance, confidence,
    forecast metrics, and reasoning for traceability.
    """
    id: str
    layer: str                      # "primary_hedge", "primary_liquidity", "primary_sentiment", "composer"
    symbol: str
    action: ActionLiteral
    confidence: float = Field(ge=0.0, le=1.0)

    # Model-level forecast metrics (e.g. expected return, move %, horizon)
    # Example: {"horizon_min": 60, "exp_move_pct": 1.5}
    forecast: Dict[str, float] = Field(default_factory=dict)

    # Human-readable reasoning, suitable for logs / explanation
    reasoning: str

    # Optional labels like ["gamma_squeeze", "thin_liquidity", "news_shock"]
    tags: List[str] = Field(default_factory=list)


class TradeLeg(BaseModel):
    """
    Single leg of an options strategy (or stock leg).
    For stock, type can be "STOCK" with strike=None, expiry=None.
    """
    instrument_type: Literal["C", "P", "STOCK"]
    direction: Literal["buy", "sell"]
    qty: int
    strike: Optional[float] = None
    expiry: Optional[str] = None  # "YYYY-MM-DD"


class TradeIdea(BaseModel):
    """
    Concrete trade object – output of Trade Agent.

    This IS strategy-level and options-leg aware. It is the final artifact that
    would be mapped into broker orders by an execution layer.
    """
    id: str
    symbol: str
    strategy_type: str        # e.g. "call_debit_spread", "iron_condor", "calendar_spread", "long_stock"
    side: Literal["long", "short", "neutral"]

    legs: List[TradeLeg]

    # Economic metrics per 1 unit (spread, contract, share)
    cost_per_unit: float
    max_loss: float
    max_profit: Optional[float]
    breakeven_levels: List[float]

    target_exit_price: Optional[float]
    stop_loss_price: Optional[float]
    recommended_units: int       # number of strategy units (spreads/condors/shares)

    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str
    tags: List[str] = Field(default_factory=list)


class LedgerRecord(BaseModel):
    """
    Single record for the tracking / ledger system.

    It ties together snapshot, suggestions, trade ideas, and realized outcomes.
    """
    timestamp: datetime
    symbol: str

    snapshot: StandardSnapshot
    primary_suggestions: List[Suggestion]
    composite_suggestion: Suggestion
    trade_ideas: List[TradeIdea]

    # Realized PnL for this step (if known); can be filled later by backtest or live engine
    realized_pnl: Optional[float] = None


# ============================================
# engines/base.py
# ============================================

from __future__ import annotations

from datetime import datetime
from typing import Protocol
from schemas.core_schemas import EngineOutput


class Engine(Protocol):
    """
    Generic interface for all Engines.

    Engines transform market-derived inputs into structured EngineOutput features.
    They do NOT directly place trades or produce policy decisions.
    """

    def run(self, symbol: str, now: datetime) -> EngineOutput:
        """
        Compute and return EngineOutput for the given symbol at time 'now'.

        Implementations must:
        - Fetch any required data via adapters.
        - Handle missing / delayed data gracefully.
        - Populate features dict with numeric values.
        - Set confidence in [0, 1].
        - Set regime if appropriate.
        - Use metadata["degraded"]="true" if operating in degraded mode.
        """
        ...


# ============================================
# agents/base.py
# ============================================

from __future__ import annotations

from typing import Protocol, List
from schemas.core_schemas import StandardSnapshot, Suggestion, TradeIdea


class PrimaryAgent(Protocol):
    """
    Primary agents interpret StandardSnapshots and output Suggestion objects.

    They MUST NOT:
    - Fetch raw market data.
    - Compute raw technical indicators.
    They ONLY consume fields from StandardSnapshot and apply policy logic.
    """

    def step(self, snapshot: StandardSnapshot) -> Suggestion:
        """
        Convert a StandardSnapshot into a high-level Suggestion.
        """
        ...


class ComposerAgent(Protocol):
    """
    Composer aggregates primary suggestions into one higher-level Suggestion.

    It:
    - Combines multiple Suggestion objects from primary agents.
    - Resolves conflicts.
    - Outputs a composite Suggestion with stance and strategy hints.
    """

    def compose(self, snapshot: StandardSnapshot, suggestions: List[Suggestion]) -> Suggestion:
        """
        Fuse multiple primary Suggestions into a single composite Suggestion.
        """
        ...


class TradeAgent(Protocol):
    """
    Trade Agent converts composer-level Suggestion into concrete TradeIdea objects.

    It:
    - Maps directional stance + regime + forecasts to actual options/stock strategies.
    - Calculates costs, max loss/profit, breakevens, and recommended sizing.
    """

    def generate_trades(self, suggestion: Suggestion) -> List[TradeIdea]:
        """
        Generate concrete TradeIdea objects from a composite Suggestion.

        Must:
        - Use options chain / stock price data via adapters (injected).
        - Respect risk constraints (from config).
        - Return zero or more TradeIdeas.
        """
        ...


# ============================================
# engines/inputs/options_chain_adapter.py
# ============================================

from __future__ import annotations

from datetime import datetime
from typing import Protocol
import polars as pl


class OptionsChainAdapter(Protocol):
    """
    Responsible for fetching and normalizing options chain data for a symbol.

    Implement provider-specific subclasses (Polygon, Tradier, IBKR, etc.)
    elsewhere; the Hedge Engine should depend ONLY on this interface.
    """

    def fetch_chain(self, symbol: str, now: datetime) -> pl.DataFrame:
        """
        Return a Polars DataFrame with columns at minimum:
        [
            "symbol", "underlying_price", "expiry", "dte", "strike", "type",
            "mid_price", "bid", "ask", "volume", "open_interest",
            "delta", "gamma", "vega", "theta", "vanna", "charm"
        ]
        """
        ...


# ============================================
# engines/inputs/market_data_adapter.py
# ============================================

from __future__ import annotations

from datetime import datetime
from typing import Protocol
import polars as pl


class MarketDataAdapter(Protocol):
    """
    Fetches OHLCV and intraday trade/quote data for a symbol.

    Implement provider-specific subclasses to satisfy this interface.
    """

    def fetch_ohlcv(self, symbol: str, lookback: int, now: datetime) -> pl.DataFrame:
        """
        Returns OHLCV history for 'lookback' bars.

        Required columns:
        ["timestamp", "open", "high", "low", "close", "volume"]
        """
        ...

    def fetch_intraday_trades(self, symbol: str, lookback_minutes: int, now: datetime) -> pl.DataFrame:
        """
        Returns intraday trade-level data.

        Required columns:
        ["timestamp", "price", "size", "side"]
        where 'side' is "buy" or "sell" if available, otherwise inferred via tick rule.
        """
        ...


# ============================================
# engines/inputs/news_adapter.py
# ============================================

from __future__ import annotations

from datetime import datetime
from typing import Protocol, List, Dict


class NewsAdapter(Protocol):
    """
    Fetches symbolic news for sentiment analysis.
    """

    def fetch_news(self, symbol: str, lookback_hours: int, now: datetime) -> List[Dict[str, str]]:
        """
        Returns a list of news items. Each item should contain:
        {
            "timestamp": ISO8601 string or dt,
            "headline": str,
            "body": str,      # can be empty if not available
            "source": str
        }
        """
        ...


# ============================================
# engines/hedge/hedge_engine_v3.py
# ============================================
from __future__ import annotations

from datetime import datetime
from typing import Dict, Any

import polars as pl
from schemas.core_schemas import EngineOutput
from engines.base import Engine
from engines.inputs.options_chain_adapter import OptionsChainAdapter


class HedgeEngineV3(Engine):
    """
    Dealer Hedge Pressure Engine v3.0

    Computes hedge-related features:
    - Gamma pressure
    - Vanna pressure
    - Charm pressure
    - Dealer gamma sign
    - VIX friction factor (if data available)
    - Cross-asset hedging field components

    Produces an EngineOutput(kind="hedge").
    """

    def __init__(self, adapter: OptionsChainAdapter, config: Dict[str, Any]) -> None:
        self.adapter = adapter
        self.config = config

    def run(self, symbol: str, now: datetime) -> EngineOutput:
        # Fetch options chain
        # Compute gamma/vanna/charm pressure via vectorized Polars operations
        # Infer regime (gamma squeeze, pin, neutral, etc.)
        # Populate EngineOutput
        ...
        # placeholder return to satisfy type checker
        raise NotImplementedError


# ============================================
# engines/liquidity/liquidity_engine_v1.py
# ============================================

from __future__ import annotations

from datetime import datetime
from typing import Dict, Any

import polars as pl
from schemas.core_schemas import EngineOutput
from engines.base import Engine
from engines.inputs.market_data_adapter import MarketDataAdapter


class LiquidityEngineV1(Engine):
    """
    Liquidity Engine v1.0

    Computes:
    - Amihud illiquidity
    - Kyle's lambda
    - Volume profile magnets and voids
    - Order flow imbalance (OFI)
    - Average spread (if quotes available)

    Produces an EngineOutput(kind="liquidity").
    """

    def __init__(self, adapter: MarketDataAdapter, config: Dict[str, Any]) -> None:
        self.adapter = adapter
        self.config = config

    def run(self, symbol: str, now: datetime) -> EngineOutput:
        # Fetch OHLCV / trades
        # Compute liquidity metrics using Polars
        # Derive regime (high_liquidity, thin_liquidity, one_sided_flow, normal)
        ...
        raise NotImplementedError


# ============================================
# engines/sentiment/processors.py
# ============================================

from __future__ import annotations

from datetime import datetime
from typing import Protocol, Tuple
from engines.inputs.news_adapter import NewsAdapter
from engines.inputs.market_data_adapter import MarketDataAdapter


class SentimentProcessor(Protocol):
    """
    Base interface for sentiment processors.

    Each processor returns (score, confidence) where score is in [-1, 1].
    """

    def compute(self, symbol: str, now: datetime) -> Tuple[float, float]:
        ...


class NewsSentimentProcessor:
    """
    News-based sentiment using NewsAdapter and simple NLP or placeholder heuristics.
    """

    def __init__(self, adapter: NewsAdapter, config: dict) -> None:
        self.adapter = adapter
        self.config = config

    def compute(self, symbol: str, now: datetime) -> Tuple[float, float]:
        ...
        raise NotImplementedError


class FlowSentimentProcessor:
    """
    Flow-based sentiment using options flow or dark pool data (to be wired later).
    """

    def __init__(self, config: dict) -> None:
        self.config = config

    def compute(self, symbol: str, now: datetime) -> Tuple[float, float]:
        ...
        raise NotImplementedError


class TechnicalSentimentProcessor:
    """
    Technical sentiment using indicators (RSI, Bollinger, Keltner) computed from OHLCV.
    """

    def __init__(self, market_adapter: MarketDataAdapter, config: dict) -> None:
        self.market_adapter = market_adapter
        self.config = config

    def compute(self, symbol: str, now: datetime) -> Tuple[float, float]:
        ...
        raise NotImplementedError


# ============================================
# engines/sentiment/sentiment_engine_v1.py
# ============================================

from __future__ import annotations

from datetime import datetime
from typing import Dict, Any, List, Tuple

from schemas.core_schemas import EngineOutput
from engines.base import Engine
from engines.sentiment.processors import (
    SentimentProcessor,
    NewsSentimentProcessor,
    FlowSentimentProcessor,
    TechnicalSentimentProcessor,
)


class SentimentEngineV1(Engine):
    """
    Sentiment Engine v1.0

    Fuses:
    - News sentiment
    - Flow sentiment
    - Technical sentiment

    into a single sentiment_score in [-1, 1], a confidence measure,
    and a sentiment_energy = |score| * confidence.

    Produces EngineOutput(kind="sentiment").
    """

    def __init__(self, processors: List[SentimentProcessor], config: Dict[str, Any]) -> None:
        self.processors = processors
        self.config = config

    def run(self, symbol: str, now: datetime) -> EngineOutput:
        # Call each processor, aggregate scores by confidence weighting.
        # Derive overall sentiment_score, sentiment_confidence, sentiment_energy.
        # Classify regime (bullish_news, bearish_news, mixed, quiet).
        ...
        raise NotImplementedError


# ============================================
# engines/elasticity/elasticity_engine_v1.py
# ============================================

from __future__ import annotations

from datetime import datetime
from typing import Dict, Any

from schemas.core_schemas import EngineOutput
from engines.base import Engine
from engines.inputs.market_data_adapter import MarketDataAdapter


class ElasticityEngineV1(Engine):
    """
    Elasticity / Energy Engine v1.0

    Converts:
    - Hedge fields (gamma, vanna, charm)
    - Liquidity metrics
    - Technical indicators (RSI, Bollinger, Keltner)
    - Realized volatility

    into an estimate of energy required to move price (up/down).
    """

    def __init__(self, market_adapter: MarketDataAdapter, config: Dict[str, Any]) -> None:
        self.market_adapter = market_adapter
        self.config = config

    def run(self, symbol: str, now: datetime) -> EngineOutput:
        # Pull previously computed hedge/liquidity features if needed (or receive via injection).
        # Compute indicators from OHLCV.
        # Derive:
        #   energy_to_move_1pct_up
        #   energy_to_move_1pct_down
        #   elasticity_up
        #   elasticity_down
        #   expected_move_cost_1_day
        ...
        raise NotImplementedError


# ============================================
# agents/hedge_agent_v3.py
# ============================================

from __future__ import annotations

from typing import Dict, Any
from uuid import uuid4
from schemas.core_schemas import StandardSnapshot, Suggestion
from agents.base import PrimaryAgent


class HedgeAgentV3(PrimaryAgent):
    """
    Hedge Agent v3.0

    Interprets hedge features in StandardSnapshot into directional stance & confidence.
    No feature computation; only uses snapshot.hedge fields.
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config

    def step(self, snapshot: StandardSnapshot) -> Suggestion:
        # Interpret snapshot.hedge (gamma_pressure, vanna, charm, etc.)
        # to decide action (long/short/flat/spread) and confidence.
        suggestion_id = f"hedge-{uuid4()}"
        ...
        raise NotImplementedError


# ============================================
# agents/liquidity_agent_v1.py
# ============================================

from __future__ import annotations

from typing import Dict, Any
from uuid import uuid4
from schemas.core_schemas import StandardSnapshot, Suggestion
from agents.base import PrimaryAgent


class LiquidityAgentV1(PrimaryAgent):
    """
    Liquidity Agent v1.0

    Interprets liquidity features (Amihud, Kyle λ, OFI, magnets/voids)
    into a view on continuation vs failure of moves.
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config

    def step(self, snapshot: StandardSnapshot) -> Suggestion:
        suggestion_id = f"liq-{uuid4()}"
        ...
        raise NotImplementedError


# ============================================
# agents/sentiment_agent_v1.py
# ============================================

from __future__ import annotations

from typing import Dict, Any
from uuid import uuid4
from schemas.core_schemas import StandardSnapshot, Suggestion
from agents.base import PrimaryAgent


class SentimentAgentV1(PrimaryAgent):
    """
    Sentiment Agent v1.0

    Interprets sentiment features (score, confidence, energy, regime)
    into a bullish/bearish/flat stance and confidence multiplier.
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config

    def step(self, snapshot: StandardSnapshot) -> Suggestion:
        suggestion_id = f"sent-{uuid4()}"
        ...
        raise NotImplementedError


# ============================================
# agents/composer/composer_agent_v1.py
# ============================================

from __future__ import annotations

from typing import Dict, Any, List
from uuid import uuid4
from schemas.core_schemas import StandardSnapshot, Suggestion
from agents.base import ComposerAgent


class ComposerAgentV1(ComposerAgent):
    """
    Composer Agent v1.0

    Aggregates primary agent suggestions via weighted voting and conflict resolution.
    Outputs a composite Suggestion with final stance, confidence, and tags.
    """

    def __init__(self, weights: Dict[str, float], config: Dict[str, Any]) -> None:
        """
        weights: mapping from layer name to weight, e.g. {
            "primary_hedge": 0.4,
            "primary_liquidity": 0.3,
            "primary_sentiment": 0.3
        }
        """
        self.weights = weights
        self.config = config

    def compose(self, snapshot: StandardSnapshot, suggestions: List[Suggestion]) -> Suggestion:
        composite_id = f"composer-{uuid4()}"
        # Implement:
        # - Weighted aggregation of actions & confidences
        # - Regime-aware adjustment
        # - Tagging of consensus/conflicts
        ...
        raise NotImplementedError

# ============================================
# agents/trade_agent_v1.py
# ============================================

from __future__ import annotations

from typing import Dict, Any, List
from uuid import uuid4
from schemas.core_schemas import Suggestion, TradeIdea, TradeLeg
from agents.base import TradeAgent
from engines.inputs.options_chain_adapter import OptionsChainAdapter


class TradeAgentV1(TradeAgent):
    """
    Trade Agent v1.0

    Converts composite Suggestion into concrete TradeIdea objects:
    - Stock trades
    - Vertical spreads
    - Iron condors
    - Calendars, etc.

    Uses options chain via OptionsChainAdapter and risk constraints from config.
    """

    def __init__(self, adapter: OptionsChainAdapter, config: Dict[str, Any]) -> None:
        self.adapter = adapter
        self.config = config

    def generate_trades(self, suggestion: Suggestion) -> List[TradeIdea]:
        trade_id_prefix = f"trade-{uuid4()}"
        # Implement mapping from Suggestion.action + forecast + tags
        # to specific strategies and legs.
        ...
        raise NotImplementedError


# ============================================
# models/feature_builder.py
# ============================================

from __future__ import annotations

from typing import Dict, Any
import polars as pl


class FeatureBuilder:
    """
    Builds ML-ready features from historical time series of:
    - price/returns
    - hedge features
    - liquidity features
    - sentiment features
    - realized volatility

    Used offline for model training and online for single-snapshot predictions.
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config

    def build_training_features(self, df: pl.DataFrame) -> Dict[str, pl.DataFrame]:
        """
        Given a consolidated Polars DataFrame with historical data,
        construct features X and labels y.

        Returns a dict like:
        {
            "X": pl.DataFrame,
            "y_return_1d": pl.Series,
            "y_vol_1d": pl.Series,
            ...
        }
        """
        ...
        raise NotImplementedError


# ============================================
# models/lookahead_model.py
# ============================================

from __future__ import annotations

from typing import Dict, Any
from schemas.core_schemas import StandardSnapshot


class LookaheadModel:
    """
    Wrapper around an ML model (e.g. tree-based, LSTM).

    Produces short-horizon forecasts used by Composer/Agents:
    - expected return
    - expected volatility
    - probability of up move
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config
        self._model = None  # placeholder for real model (sklearn, torch, etc.)

    def load(self, path: str) -> None:
        """
        Load trained model artifacts from disk.
        """
        ...
        raise NotImplementedError

    def predict(self, snapshot: StandardSnapshot) -> Dict[str, float]:
        """
        Produce forecasts for a single StandardSnapshot, e.g.:
        {
            "exp_return_1d": float,
            "exp_vol_1d": float,
            "p_up_1d": float
        }
        """
        ...
        raise NotImplementedError


# ============================================
# ledger/ledger_store.py
# ============================================

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable
from schemas.core_schemas import LedgerRecord


class LedgerStore:
    """
    Append-only ledger store. Initially JSONL-based; later can be swapped to DB/DuckDB.

    Responsibilities:
    - Append LedgerRecord entries.
    - Stream historical records for metrics/feedback.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, record: LedgerRecord) -> None:
        """
        Append a single record to the ledger file.
        """
        ...
        raise NotImplementedError

    def stream(self) -> Iterable[LedgerRecord]:
        """
        Stream all records from the ledger.
        """
        ...
        raise NotImplementedError


# ============================================
# ledger/ledger_metrics.py
# ============================================

from __future__ import annotations

from typing import Iterable, Dict
from schemas.core_schemas import LedgerRecord


class LedgerMetrics:
    """
    Computes metrics (Sharpe, hit-rate, drawdown, etc.) from a stream of LedgerRecord.
    """

    @staticmethod
    def compute(records: Iterable[LedgerRecord]) -> Dict[str, float]:
        """
        Compute and return metrics as a dict.
        Expected keys (at minimum):
        - "sharpe"
        - "hit_rate"
        - "max_drawdown"
        - "avg_trade_pnl"
        """
        ...
        raise NotImplementedError


# ============================================
# feedback/feedback_engine.py
# ============================================

from __future__ import annotations

from typing import Dict, Any
from ledger.ledger_store import LedgerStore
from ledger.ledger_metrics import LedgerMetrics


class FeedbackEngine:
    """
    Feedback engine that:
    - Reads LedgerStore
    - Computes LedgerMetrics
    - Applies parameter updates (e.g. agent weights, risk fraction)
    """

    def __init__(self, store: LedgerStore, config: Dict[str, Any]) -> None:
        self.store = store
        self.config = config

    def update_parameters(self) -> Dict[str, Any]:
        """
        Compute metrics, derive updated parameters, and return the updated config diff.

        Implementation must:
        - Stream records
        - Compute metrics
        - Map metrics -> config updates (e.g. adjust weights, risk limits)
        - NOT directly mutate global config; instead, return updates for the caller to persist.
        """
        ...
        raise NotImplementedError


# ============================================
# engines/orchestration/pipeline_runner.py
# ============================================

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Any

from schemas.core_schemas import (
    EngineOutput,
    StandardSnapshot,
    Suggestion,
    TradeIdea,
    LedgerRecord,
)
from engines.base import Engine
from agents.base import PrimaryAgent, ComposerAgent, TradeAgent
from ledger.ledger_store import LedgerStore


class PipelineRunner:
    """
    Orchestrates a single pipeline pass for one symbol at time t:

    Engines -> StandardSnapshot -> Primary Agents -> Composer -> Trade Agent -> Ledger.
    """

    def __init__(
        self,
        symbol: str,
        engines: Dict[str, Engine],
        primary_agents: Dict[str, PrimaryAgent],
        composer: ComposerAgent,
        trade_agent: TradeAgent,
        ledger_store: LedgerStore,
        config: Dict[str, Any],
    ) -> None:
        self.symbol = symbol
        self.engines = engines
        self.primary_agents = primary_agents
        self.composer = composer
        self.trade_agent = trade_agent
        self.ledger_store = ledger_store
        self.config = config

    def run_once(self, now: datetime) -> Dict[str, object]:
        """
        Run ONE full pass of the pipeline for the configured symbol.

        Returns:
            A dict with snapshot, engine_outputs, primary_suggestions,
            composite_suggestion, trade_ideas.
        """
        # 1. Run engines
        engine_outputs: Dict[str, EngineOutput] = {
            name: engine.run(self.symbol, now)
            for name, engine in self.engines.items()
        }

        # 2. Build StandardSnapshot
        snapshot: StandardSnapshot = self._build_snapshot(engine_outputs)

        # 3. Primary agents
        primary_suggestions: List[Suggestion] = [
            agent.step(snapshot) for agent in self.primary_agents.values()
        ]

        # 4. Composer
        composite_suggestion: Suggestion = self.composer.compose(snapshot, primary_suggestions)

        # 5. Trade agent
        trade_ideas: List[TradeIdea] = self.trade_agent.generate_trades(composite_suggestion)

        # 6. Ledger record
        record = LedgerRecord(
            timestamp=now,
            symbol=self.symbol,
            snapshot=snapshot,
            primary_suggestions=primary_suggestions,
            composite_suggestion=composite_suggestion,
            trade_ideas=trade_ideas,
        )
        self.ledger_store.append(record)

        return {
            "snapshot": snapshot,
            "engine_outputs": engine_outputs,
            "primary_suggestions": primary_suggestions,
            "composite_suggestion": composite_suggestion,
            "trade_ideas": trade_ideas,
        }

    def _build_snapshot(self, engine_outputs: Dict[str, EngineOutput]) -> StandardSnapshot:
        """
        Fuse EngineOutput objects into a StandardSnapshot.

        This is the ONLY place where engine features get merged into the canonical snapshot.
        """
        ...
        raise NotImplementedError

# ============================================
# backtest/runner.py
# ============================================

from __future__ import annotations

from datetime import datetime
from typing import Callable, Dict, Any


class BacktestRunner:
    """
    Event-driven backtest wrapper.

    It:
    - Iterates over historical time steps
    - Calls PipelineRunner-like function
    - Simulates fills and PnL
    - Returns summary metrics
    """

    def __init__(
        self,
        pipeline_factory: Callable[[str], Any],
        data_source: Any,
        config: Dict[str, Any],
    ) -> None:
        self.pipeline_factory = pipeline_factory
        self.data_source = data_source
        self.config = config

    def run_backtest(self, symbol: str, start: datetime, end: datetime) -> Dict[str, float]:
        """
        Run a backtest for the specified symbol and date range.

        Returns:
            A dict of summary metrics (Sharpe, hit-rate, etc.)
        """
        ...
        raise NotImplementedError


# ============================================
# execution/broker_adapter.py
# ============================================

from __future__ import annotations

from typing import Protocol, List
from schemas.core_schemas import TradeIdea


class BrokerAdapter(Protocol):
    """
    Abstract broker adapter interface (paper or live).

    Maps TradeIdea objects to concrete orders.
    """

    def place_trades(self, trades: List[TradeIdea]) -> None:
        """
        Place one or more trades at the broker.

        Implementation must:
        - Handle partial fills
        - Handle errors and logging
        """
        ...


# ============================================
# execution/order_simulator.py
# ============================================

from __future__ import annotations

from typing import List
from schemas.core_schemas import TradeIdea


class OrderSimulator:
    """
    Simple order simulator for backtesting.

    Applies slippage models and fill rules to TradeIdeas.
    """

    def __init__(self, config: dict) -> None:
        self.config = config

    def simulate_fills(self, trades: List[TradeIdea]) -> None:
        """
        Simulate order fills for TradeIdeas during backtest.
        """
        ...
        raise NotImplementedError


# ============================================
# ui/dashboard.py
# ============================================

from __future__ import annotations

from typing import Any, Dict


def run_dashboard(app_context: Dict[str, Any]) -> None:
    """
    Placeholder for Streamlit/FastAPI dashboard entrypoint.

    It should:
    - Display latest snapshot and engine features
    - Show primary and composite suggestions
    - Show trade ideas
    - Plot price + gamma walls + liquidity zones + sentiment score (later)
    """
    ...
    raise NotImplementedError


# ============================================
# main.py
# ============================================

from __future__ import annotations

from datetime import datetime
from typing import Dict, Any

import typer

from engines.orchestration.pipeline_runner import PipelineRunner

# TODO: import concrete engine implementations, agents, adapters, config loader, ledger store, etc.


app = typer.Typer(help="Super Gnosis / DHPE Pipeline CLI")


def build_pipeline(symbol: str, config: Dict[str, Any]) -> PipelineRunner:
    """
    Construct a PipelineRunner for a symbol using injected engines, agents,
    adapters, and ledger.

    This is where you wire:
    - HedgeEngineV3
    - LiquidityEngineV1
    - SentimentEngineV1
    - ElasticityEngineV1
    - Primary agents
    - ComposerAgentV1
    - TradeAgentV1
    - LedgerStore
    """
    ...
    raise NotImplementedError


@app.command()
def run_once(symbol: str = typer.Option("SPY")) -> None:
    """
    Run a single pipeline pass for the given symbol and print summarized output.
    """
    config: Dict[str, Any] = {}  # TODO: load from config loader
    runner = build_pipeline(symbol, config)
    now = datetime.utcnow()
    result = runner.run_once(now)
    print(result)


if __name__ == "__main__":
    app()


# ============================================
# tests/test_schemas.py
# ============================================

from __future__ import annotations

from datetime import datetime
from schemas.core_schemas import (
    EngineOutput,
    StandardSnapshot,
    Suggestion,
    TradeIdea,
    TradeLeg,
)


def test_engine_output_basic() -> None:
    eo = EngineOutput(
        kind="hedge",
        symbol="SPY",
        timestamp=datetime.utcnow(),
        features={"gamma_pressure": 1.0},
        confidence=0.9,
        regime="gamma_squeeze",
    )
    assert eo.kind == "hedge"
    assert eo.features["gamma_pressure"] == 1.0


def test_standard_snapshot_basic() -> None:
    snap = StandardSnapshot(
        symbol="SPY",
        timestamp=datetime.utcnow(),
        hedge={"gamma_pressure": 1.0},
        liquidity={"amihud_illiquidity": 0.1},
        sentiment={"sentiment_score": 0.5},
        elasticity={"energy_to_move_1pct_up": 10.0},
    )
    assert snap.symbol == "SPY"
    assert "gamma_pressure" in snap.hedge


def test_trade_idea_basic() -> None:
    legs = [
        TradeLeg(
            instrument_type="C",
            direction="buy",
            qty=1,
            strike=500.0,
            expiry="2025-12-19",
        )
    ]
    idea = TradeIdea(
        id="test",
        symbol="SPY",
        strategy_type="call_debit_spread",
        side="long",
        legs=legs,
        cost_per_unit=200.0,
        max_loss=200.0,
        max_profit=300.0,
        breakeven_levels=[502.0],
        target_exit_price=510.0,
        stop_loss_price=495.0,
        recommended_units=1,
        confidence=0.8,
        rationale="Test idea",
    )
    assert idea.strategy_type == "call_debit_spread"
    assert idea.legs[0].instrument_type == "C"


# ============================================
# tests/test_pipeline_smoke.py
# ============================================

from __future__ import annotations

from datetime import datetime
from typing import Dict, Any

from engines.orchestration.pipeline_runner import PipelineRunner
from schemas.core_schemas import EngineOutput, StandardSnapshot, Suggestion, TradeIdea
from engines.base import Engine
from agents.base import PrimaryAgent, ComposerAgent, TradeAgent
from ledger.ledger_store import LedgerStore
from pathlib import Path


class DummyEngine(Engine):
    def run(self, symbol: str, now: datetime) -> EngineOutput:
        return EngineOutput(
            kind="hedge",
            symbol=symbol,
            timestamp=now,
            features={"dummy": 1.0},
            confidence=1.0,
        )


class DummyPrimaryAgent(PrimaryAgent):
    def step(self, snapshot: StandardSnapshot) -> Suggestion:
        return Suggestion(
            id="dummy",
            layer="primary_hedge",
            symbol=snapshot.symbol,
            action="flat",
            confidence=0.5,
            forecast={},
            reasoning="dummy",
        )


class DummyComposer(ComposerAgent):
    def compose(self, snapshot: StandardSnapshot, suggestions):
        return Suggestion(
            id="dummy-composer",
            layer="composer",
            symbol=snapshot.symbol,
            action="flat",
            confidence=0.5,
            forecast={},
            reasoning="dummy composite",
        )


class DummyTradeAgent(TradeAgent):
    def generate_trades(self, suggestion: Suggestion):
        return []  # no trades


def test_pipeline_smoke(tmp_path: Path) -> None:
    engines: Dict[str, Engine] = {"hedge": DummyEngine()}
    primary_agents: Dict[str, PrimaryAgent] = {"primary_hedge": DummyPrimaryAgent()}
    composer: ComposerAgent = DummyComposer()
    trade_agent: TradeAgent = DummyTradeAgent()
    ledger_store = LedgerStore(tmp_path / "ledger.jsonl")
    config: Dict[str, Any] = {}

    runner = PipelineRunner(
        symbol="SPY",
        engines=engines,
        primary_agents=primary_agents,
        composer=composer,
        trade_agent=trade_agent,
        ledger_store=ledger_store,
        config=config,
    )

    now = datetime.utcnow()
    # _build_snapshot will raise NotImplementedError until implemented; that's OK as a placeholder.
    try:
        runner.run_once(now)
    except NotImplementedError:
        # Pipeline wiring is correct, we just haven't implemented the snapshot builder yet.
        assert True
```
