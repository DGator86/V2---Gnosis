# Super Gnosis ML System

Complete Machine Learning pipeline for Super Gnosis trading system.

## Architecture

```
ml/
├── labels/          # Label generation (forward returns, direction, magnitude, volatility)
├── features/        # Feature engineering (merge engines + technical + regime)
├── dataset/         # Dataset building (purged CV, energy weighting)
├── trainer/         # Model training (LightGBM, XGBoost, LSTM)
├── prediction/      # Prediction pipeline (confidence calibration)
├── persistence/     # Model storage (versioning, drift detection)
├── agents/          # MLAgent for Composer integration
└── train.py         # High-level training orchestrator
```

## Features

### 1. Label Generation
- **Forward returns**: Multiple horizons (5m, 15m, 1h)
- **Direction labels**: Binary ±1 classification
- **Magnitude labels**: Small/medium/large moves (volatility-adjusted)
- **Volatility labels**: Forward realized volatility

### 2. Feature Engineering
- **Engine features**: 114 features from Hedge/Liquidity/Sentiment engines
- **Technical indicators**: MACD, RSI, ATR, ROC, momentum z-scores, Bollinger, Stochastic, ADX
- **Regime classification**: VIX buckets, SPX vol, market structure, session, liquidity time

### 3. Dataset Building
- **Purged K-Fold CV**: Prevents leakage in time series
- **Embargo periods**: Removes overlapping samples
- **Energy-aware weighting**: Weight = 1 / energy_cost
- **Class balancing**: Handle imbalanced data

### 4. Model Training
- **LightGBM**: Fast gradient boosting
- **Multi-task**: Direction + Magnitude + Volatility
- **Early stopping**: Prevent overfitting
- **Feature importance**: Track most predictive features

### 5. Prediction Pipeline
- **Confidence calibration**: Platt/isotonic scaling
- **Energy adjustment**: Lower confidence for high-energy moves
- **Multi-model ensemble**: Combine direction, magnitude, volatility

### 6. Model Persistence
- **Versioning**: Timestamp-based version control
- **Drift detection**: PSI-based monitoring
- **Rollback**: Revert to previous versions
- **Cleanup**: Remove old versions

### 7. Agent Integration
- **MLAgent**: Provides predictions to Composer
- **No trade decisions**: Composer makes final decisions
- **Confidence thresholds**: Only signal when confident

## Quick Start

### Training

```python
import polars as pl
from ml.train import MLTrainingOrchestrator

# Load OHLCV data
df = pl.read_parquet("data/SPY_5min.parquet")

# Initialize orchestrator
orchestrator = MLTrainingOrchestrator()

# Train models
results = orchestrator.train_full_pipeline(
    df_ohlcv=df,
    symbol="SPY",
    horizon=5,  # 5-bar ahead prediction
)

# Results contain trained models and metrics
for task, result in results.items():
    print(f"{task}: {result.metrics}")
```

### Prediction

```python
from ml.agents.ml_agent import MLAgent
import numpy as np

# Initialize agent
agent = MLAgent()

# Make prediction
features = np.random.randn(100)  # Your feature vector
output = agent.process(
    symbol="SPY",
    features=features,
    movement_energy=50.0,
    horizon=5,
)

print(f"Direction: {output.ml_bias}")
print(f"Confidence: {output.ml_confidence}")
print(f"Magnitude: {output.expected_magnitude}")
```

### Composer Integration

```python
from agents.composer_agent import ComposerAgent
from ml.agents.ml_agent import MLAgent

# Add ML agent to composer
ml_agent = MLAgent()
composer = ComposerAgent(ml_agent=ml_agent)

# Composer now uses ML predictions in fusion
context = composer.fuse_agents(
    hedge_output=hedge_output,
    liquidity_output=liquidity_output,
    sentiment_output=sentiment_output,
    # ML predictions automatically included
)
```

## Configuration

### Label Config
```python
from ml.labels.generator import LabelConfig

config = LabelConfig(
    horizons=[5, 15, 60],
    magnitude_small_threshold=0.33,
    magnitude_large_threshold=0.67,
)
```

### Training Config
```python
from ml.trainer.lightgbm_trainer import LightGBMConfig

config = LightGBMConfig(
    num_leaves=31,
    learning_rate=0.05,
    n_estimators=100,
    early_stopping_rounds=50,
)
```

## Performance Metrics

### Direction Model
- **Accuracy**: Overall classification accuracy
- **Precision**: True positives / (TP + FP)
- **Recall**: True positives / (TP + FN)
- **AUC**: Area under ROC curve
- **Directional Accuracy**: Core metric for trading

### Magnitude Model
- **Accuracy**: Overall classification accuracy
- **F1-Macro**: Unweighted mean F1 across classes
- **F1-Weighted**: Class-balanced F1 score

### Volatility Model
- **RMSE**: Root mean squared error
- **MAE**: Mean absolute error
- **R²**: Coefficient of determination

## Drift Detection

Monitor model performance over time:

```python
from ml.persistence.manager import ModelManager

manager = ModelManager()

# Check for drift
drift_detected, psi_score, details = manager.detect_drift(
    symbol="SPY",
    task="direction",
    horizon=5,
    X_recent=recent_features,
    threshold=0.2,
)

if drift_detected:
    print(f"Drift detected! PSI: {psi_score}")
    # Trigger retraining
```

## Development Status

✅ **Phase 1**: Label generation + Feature engineering  
✅ **Phase 2**: Dataset builder with purged CV  
✅ **Phase 3**: LightGBM training  
⏳ **Phase 4**: Optuna hyperparameter optimization (future)  
✅ **Phase 5**: Prediction pipeline  
✅ **Phase 6**: Model persistence  
⏳ **Phase 7**: FastAPI endpoints (future)  
✅ **Phase 8**: MLAgent integration  

## Next Steps

1. Integrate with orchestrator pipeline
2. Add Optuna hyperparameter tuning
3. Add XGBoost and LSTM models
4. Implement ensemble meta-learner
5. Add FastAPI endpoints
6. Set up automated retraining
7. Add comprehensive unit tests
8. Performance benchmarking

## Dependencies

```
lightgbm>=4.0.0
xgboost>=2.0.0
scikit-learn>=1.3.0
optuna>=3.0.0
numpy>=1.24.0
polars>=0.20.0
```

## References

- López de Prado, Marcos. "Advances in Financial Machine Learning" (2018)
- Purged K-Fold cross-validation for time series
- Energy-aware sample weighting
- Multi-objective hyperparameter optimization
