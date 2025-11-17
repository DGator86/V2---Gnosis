"""Machine Learning system for Super Gnosis.

This package implements the complete ML pipeline:
- Label generation (forward returns, direction, magnitude, volatility)
- Feature engineering (merging engine outputs + technical indicators)
- Dataset building (purged CV, energy-aware weighting)
- Model training (LightGBM, XGBoost, LSTM, ensembles)
- Hyperparameter optimization (Optuna multi-objective)
- Prediction pipeline (confidence calibration)
- Model persistence (versioning, drift detection)
- Agent integration (MLAgent → Composer)
"""

__version__ = "1.0.0"
