# Neurotrader888 Repository Integration Plan

## Overview
Complete integration of 14 neurotrader888 repositories into our production sentiment engine system.

## Repository Mapping

### 1. **Market Structure & Price Action**

#### market-structure
- **Purpose**: Multiscale market structure extremes detection
- **Features**: ATR directional changes, local & hierarchical extrema
- **Integration**: Volume Engine → structure analysis
- **Output**: extrema[{timestamp, price, scale, kind}], regime_break_flags
- **Use Case**: Identify key price levels and structural breaks

#### TrendLineAutomation
- **Purpose**: Automatic trendline and S/R level detection
- **Features**: Automated trendline fitting, touch counting, strength scoring
- **Integration**: Volume Engine → context, Agent 2 Liquidity → confluence
- **Output**: trendlines[{id, slope, touch_count, strength}], break_tests
- **Use Case**: Support/resistance scaffolding for trade setups

#### TrendlineBreakoutMetaLabel
- **Purpose**: Meta-labeling for breakout setups
- **Features**: Supervised learning targets for breakout validation
- **Integration**: Agent 4 Composer → edge gating, Backtest validation
- **Output**: meta_label (1/0/−1), confidence, lead_time
- **Use Case**: Filter false breakouts, improve entry quality

### 2. **Volume & Flow Analysis**

#### VSAIndicator
- **Purpose**: Volume Spread Analysis anomaly detection
- **Features**: Range deviation analysis given volume
- **Integration**: Volume Engine → vsa_score, climax_bar_flags
- **Output**: vsa_score, climax_bar, effort_vs_result
- **Use Case**: Detect supply/demand imbalances

#### TimeSeriesVisibilityGraphs
- **Purpose**: Complex network analysis of time series
- **Features**: Visibility graph degree, clustering, path length
- **Integration**: Volume Engine regimes → complexity metrics
- **Output**: vg_degree, vg_clustering, vg_entropy
- **Use Case**: Measure market complexity and regime changes

#### PermutationEntropy
- **Purpose**: Local entropy measurement
- **Features**: Ordinal pattern analysis, complexity quantification
- **Integration**: Volume Engine → turbulence/regularity metrics
- **Output**: perm_entropy(window=w), complexity_score
- **Use Case**: Identify periods of high/low market uncertainty

### 3. **Volatility & Risk**

#### VolatilityHawkes
- **Purpose**: Hawkes process for volatility clustering
- **Features**: Jump intensity estimation, branching ratio
- **Integration**: Hedge Engine → gamma/vanna transmission
- **Output**: lambda_vol, branching_ratio, jump_prob(h)
- **Use Case**: Model volatility contagion and clustering

### 4. **Technical Analysis**

#### TechnicalAnalysisAutomation
- **Purpose**: Bulk technical indicator calculation
- **Features**: Mass TA computation, scanning framework
- **Integration**: Volume & Sentiment Engines → indicator bus
- **Output**: ta_{rsi,atr,kc,ema,...} aligned dataframe
- **Use Case**: Comprehensive technical analysis pipeline

#### RSI-PCA
- **Purpose**: Dimensionality reduction of oscillators
- **Features**: PCA on RSI pack, latent factor extraction
- **Integration**: Sentiment Engine → latent factors
- **Output**: rsi_pca_1..k, explained_variance
- **Use Case**: Reduce oscillator noise, extract main signals

#### TVLIndicator (crypto)
- **Purpose**: DeFi Total Value Locked indicator
- **Features**: TVL-based signals for crypto markets
- **Integration**: Sentiment Engine (crypto mode)
- **Output**: tvl_rate, tvl_divergence
- **Use Case**: Crypto-specific sentiment/fundamentals

### 5. **Research Validation**

#### mcpt (Monte Carlo Permutation Tests)
- **Purpose**: Statistical validation of backtest results
- **Features**: Permutation testing, walk-forward analysis
- **Integration**: Research harness, Agent 4 sign-off
- **Output**: mcpt_p, effect_size, walkforward_stats
- **Use Case**: Ensure edges aren't statistical artifacts

#### TradeDependenceRunsTest
- **Purpose**: Serial dependence testing
- **Features**: Runs test for independence
- **Integration**: Research Validator → feature gating
- **Output**: runs_p_value, independence_score
- **Use Case**: Validate feature independence

#### TimeSeriesReversibility
- **Purpose**: Time-asymmetry and nonlinearity checks
- **Features**: Reversibility statistics
- **Integration**: Research Validator → QA pipeline
- **Output**: reversibility_stat, p_values
- **Use Case**: Detect nonlinear patterns

#### IntramarketDifference
- **Purpose**: Cross-sectional drift/difference tests
- **Features**: Inter-market statistical tests
- **Integration**: Composer QA → cross-validation
- **Output**: difference_stat, significance
- **Use Case**: Validate cross-sectional strategies

## Architecture Integration

### Engine Layer

#### Volume Engine
**Inputs**:
- VSAIndicator
- VisibilityGraphs
- PermutationEntropy
- TechnicalAnalysisAutomation
- market-structure
- TrendLineAutomation

**Outputs**:
- structure_extrema
- vsa_scores
- complexity_metrics
- levels
- trendline_confluence

#### Sentiment Engine (Enhanced)
**Inputs**:
- RSI-PCA
- TechnicalAnalysisAutomation
- TVLIndicator (crypto)
- FinBERT sentiment

**Outputs**:
- sentiment_latents
- momentum_regime
- oscillator_factors
- combined_sentiment_score

#### Hedge Engine
**Inputs**:
- VolatilityHawkes
- market-structure levels
- Volume Engine extrema

**Outputs**:
- jump_prob
- lambda_vol
- transmission_factor
- pin_break_probabilities

### Agent Layer

#### Agent 1: Hedge/Fields Specialist
**Inputs**: Hedge Engine + Volume levels
**Processing**: 
- Pin/break probability projection
- Transmission strength modeling
- Gamma/vanna field interactions

**Outputs**: 
- pin_prob
- break_prob
- transmission_factor
- hedge_recommendations

#### Agent 2: Liquidity Cartographer
**Inputs**: 
- TrendLineAutomation
- market-structure
- VSA extremes

**Processing**:
- Confluence map building
- Level strength scoring
- Liquidity event detection

**Outputs**:
- confluence_score
- key_levels
- liquidity_events
- support_resistance_matrix

#### Agent 3: Sentiment Interpreter
**Inputs**:
- RSI-PCA factors
- TA bus
- FinBERT output
- TVL (crypto)

**Processing**:
- Regime classification
- Tilt score computation
- Multi-source sentiment fusion

**Outputs**:
- sentiment_regime
- sentiment_tilt
- confidence_score
- signal_quality

#### Agent 4: Composer/Strategy
**Inputs**:
- All agent outputs
- Meta-labels (TrendlineBreakoutMetaLabel)
- Validation results (mcpt)

**Processing**:
- Strategy selection
- Position sizing
- Risk management
- Edge validation

**Outputs**:
- strategy_signal (long/short/neutral)
- position_size
- stop_loss/take_profit
- confidence_level

### Research/Validation Layer

#### Feature Validation Pipeline
1. **Independence Testing**: TradeDependenceRunsTest
2. **Reversibility Check**: TimeSeriesReversibility
3. **Cross-sectional Validation**: IntramarketDifference
4. **Backtest Validation**: mcpt

#### Quality Gates
- Features must pass independence test (p > 0.05)
- Reversibility stat within acceptable range
- MCPT shows p < 0.05 on rolling windows
- Meta-label confidence > threshold

## Implementation Strategy

### Phase 1: Core Features (Priority 1)
1. ✅ VSA + Extrema integration
2. ✅ Hawkes jump risk
3. ✅ Meta-label breakout filter
4. ✅ Research guardrails

### Phase 2: Volume & Structure (Priority 2)
5. TrendLineAutomation
6. market-structure hierarchical extrema
7. VisibilityGraphs complexity
8. PermutationEntropy

### Phase 3: Technical & Sentiment (Priority 3)
9. TechnicalAnalysisAutomation bus
10. RSI-PCA latent factors
11. Enhanced sentiment fusion

### Phase 4: Validation & Polish (Priority 4)
12. Complete validation pipeline
13. Walk-forward testing framework
14. Production monitoring

## Data Flow

```
OHLCV Data
    ↓
┌─────────────────────────────────────┐
│     Feature Extraction Layer        │
│  (All neurotrader888 repos)        │
└──────────────┬──────────────────────┘
               ↓
    ┌──────────┴─────────────┐
    │                        │
┌───▼────┐  ┌────▼────┐  ┌──▼────┐
│ Volume │  │Sentiment│  │ Hedge │
│ Engine │  │ Engine  │  │Engine │
└───┬────┘  └────┬────┘  └──┬────┘
    │            │           │
    └────────┬───┴───────┬───┘
             ↓           ↓
      ┌──────▼─────┬────▼─────┐
      │  Agent 1   │ Agent 2  │
      │  (Hedge)   │(Liquidity)│
      └──────┬─────┴────┬─────┘
             │          │
      ┌──────▼─────┬────▼─────┐
      │  Agent 3   │ Agent 4  │
      │(Sentiment) │(Composer)│
      └──────┬─────┴────┬─────┘
             │          │
             └────┬─────┘
                  ↓
          Trading Signals
               +
      Validation Pipeline
               ↓
        Execution Layer
```

## Configuration

### Feature Toggles (features.yaml)
```yaml
volume_engine:
  vsa:
    enabled: true
    window: 50
  extrema:
    enabled: true
    orders: [3, 10, 25]
  trendlines:
    enabled: true
    lookback: 200
  visibility_graphs:
    enabled: true
    window: 200
  perm_entropy:
    enabled: true
    window: 100

hedge_engine:
  hawkes:
    enabled: true
    event_threshold: 1.5
  transmission:
    enabled: true

sentiment_engine:
  rsi_pca:
    enabled: true
    n_components: 2
  tvl_indicator:
    enabled: false  # Only for crypto

research:
  validation:
    mcpt:
      enabled: true
      n_permutations: 300
    runs_test:
      enabled: true
    reversibility:
      enabled: true
```

## Testing Strategy

1. **Unit Tests**: Each feature adapter
2. **Integration Tests**: Engine-level
3. **End-to-End Tests**: Full pipeline
4. **Backtests**: Historical validation
5. **Walk-Forward**: Out-of-sample validation

## Performance Targets

- **Throughput**: 100+ tickers/minute
- **Latency**: <100ms per feature
- **Memory**: <2GB for full feature set
- **Accuracy**: 80%+ on validation set

## Monitoring

- Feature computation times
- Validation test pass rates
- Agent signal quality metrics
- Strategy performance attribution

## Next Steps

1. Review and approve integration plan
2. Implement Phase 1 features
3. Build validation pipeline
4. Create comprehensive tests
5. Deploy to staging
6. Monitor and iterate

---

**Status**: Ready for Implementation
**Est. Time**: 40-60 hours for complete integration
**Priority**: High - Significant alpha potential