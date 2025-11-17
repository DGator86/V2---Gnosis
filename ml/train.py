"""High-level training orchestrator for ML models."""

from __future__ import annotations

import polars as pl
from typing import Dict, List, Optional

from ml.labels.generator import LabelGenerator, LabelConfig
from ml.features.builder import FeatureBuilder, FeatureConfig
from ml.features.technical import TechnicalIndicators
from ml.features.regime import RegimeClassifier
from ml.dataset.builder import DatasetBuilder, DatasetConfig
from ml.trainer.lightgbm_trainer import LightGBMTrainer, LightGBMConfig
from ml.persistence.manager import ModelManager
from ml.trainer.core import TrainingResult


class MLTrainingOrchestrator:
    """Orchestrate end-to-end ML training pipeline."""
    
    def __init__(
        self,
        label_config: Optional[LabelConfig] = None,
        feature_config: Optional[FeatureConfig] = None,
        dataset_config: Optional[DatasetConfig] = None,
        lgbm_config: Optional[LightGBMConfig] = None,
        models_dir: str = "./ml_models",
    ):
        """Initialize training orchestrator.
        
        Args:
            label_config: Label generation config
            feature_config: Feature building config
            dataset_config: Dataset building config
            lgbm_config: LightGBM training config
            models_dir: Directory for model storage
        """
        self.label_generator = LabelGenerator(label_config)
        self.feature_builder = FeatureBuilder(feature_config)
        self.technical_indicators = TechnicalIndicators()
        self.regime_classifier = RegimeClassifier()
        self.dataset_builder = DatasetBuilder(dataset_config)
        self.trainer = LightGBMTrainer(lgbm_config)
        self.model_manager = ModelManager(base_dir=models_dir)
    
    def train_full_pipeline(
        self,
        df_ohlcv: pl.DataFrame,
        symbol: str,
        horizon: int = 5,
        hedge_outputs: Optional[List] = None,
        liquidity_outputs: Optional[List] = None,
        sentiment_outputs: Optional[List] = None,
        vix_series: Optional[pl.Series] = None,
        spx_series: Optional[pl.Series] = None,
    ) -> Dict[str, TrainingResult]:
        """Run full ML training pipeline.
        
        Args:
            df_ohlcv: OHLCV dataframe
            symbol: Trading symbol
            horizon: Forecast horizon
            hedge_outputs: Optional hedge engine outputs
            liquidity_outputs: Optional liquidity engine outputs
            sentiment_outputs: Optional sentiment engine outputs
            vix_series: Optional VIX data
            spx_series: Optional SPX data
            
        Returns:
            Dictionary of training results by task
        """
        # Step 1: Generate labels
        print(f"[ML Train] Generating labels for {symbol}...")
        df_with_labels = self.label_generator.generate(df_ohlcv)
        
        # Step 2: Build features
        print(f"[ML Train] Building features...")
        df_features = self.feature_builder.build_feature_frame(
            df_ohlcv=df_with_labels,
            hedge_outputs=hedge_outputs,
            liquidity_outputs=liquidity_outputs,
            sentiment_outputs=sentiment_outputs,
        )
        
        # Step 3: Add technical indicators
        print(f"[ML Train] Adding technical indicators...")
        df_features = self.technical_indicators.add_all_indicators(df_features)
        
        # Step 4: Add regime features
        print(f"[ML Train] Adding regime features...")
        df_features = self.regime_classifier.add_all_regimes(
            df_features,
            vix_series=vix_series,
            spx_series=spx_series,
        )
        
        # Step 5: Merge labels back
        df_ml = df_with_labels.join(df_features, on="timestamp", how="inner")
        
        # Step 6: Build dataset
        print(f"[ML Train] Building dataset...")
        dataset = self.dataset_builder.build_dataset(df_ml, horizon=horizon)
        
        # Step 7: Split dataset
        train_dataset, valid_dataset, test_dataset = self.dataset_builder.temporal_split(dataset)
        
        print(f"[ML Train] Train samples: {train_dataset.n_samples}")
        print(f"[ML Train] Valid samples: {valid_dataset.n_samples}")
        print(f"[ML Train] Test samples: {test_dataset.n_samples}")
        print(f"[ML Train] Features: {train_dataset.n_features}")
        
        # Step 8: Train models
        print(f"[ML Train] Training models...")
        results = self.trainer.train_multi_task(
            train_dataset=train_dataset,
            valid_dataset=valid_dataset,
            symbol=symbol,
            horizon=horizon,
        )
        
        # Step 9: Save models
        print(f"[ML Train] Saving models...")
        for task, result in results.items():
            self.model_manager.save_model(
                model=result.model,
                symbol=symbol,
                model_type="lightgbm",
                task=task,
                horizon=horizon,
                feature_names=train_dataset.feature_names,
                metrics=result.metrics,
                hyperparameters=result.hyperparameters,
                n_train_samples=train_dataset.n_samples,
            )
            
            print(f"[ML Train] {task.capitalize()} model saved:")
            for metric_name, metric_value in result.metrics.items():
                print(f"  {metric_name}: {metric_value:.4f}")
        
        # Step 10: Evaluate on test set
        print(f"[ML Train] Evaluating on test set...")
        test_metrics = self._evaluate_on_test(results, test_dataset)
        
        for task, metrics in test_metrics.items():
            print(f"[ML Train] {task.capitalize()} test metrics:")
            for metric_name, metric_value in metrics.items():
                print(f"  {metric_name}: {metric_value:.4f}")
        
        return results
    
    def _evaluate_on_test(
        self,
        results: Dict[str, TrainingResult],
        test_dataset,
    ) -> Dict[str, Dict[str, float]]:
        """Evaluate trained models on test set.
        
        Args:
            results: Training results
            test_dataset: Test dataset
            
        Returns:
            Dictionary of test metrics by task
        """
        test_metrics = {}
        
        # Direction
        if "direction" in results:
            y_pred = self.trainer.predict(results["direction"].model, test_dataset.X)
            y_true = (test_dataset.y_direction > 0).astype(int)
            y_pred_label = (y_pred > 0.5).astype(int)
            
            from sklearn.metrics import accuracy_score
            test_metrics["direction"] = {
                "test_accuracy": accuracy_score(y_true, y_pred_label)
            }
        
        # Magnitude
        if "magnitude" in results:
            import numpy as np
            y_pred = self.trainer.predict(results["magnitude"].model, test_dataset.X)
            y_pred_label = np.argmax(y_pred, axis=1)
            
            from sklearn.metrics import accuracy_score
            test_metrics["magnitude"] = {
                "test_accuracy": accuracy_score(test_dataset.y_magnitude, y_pred_label)
            }
        
        # Volatility
        if "volatility" in results:
            y_pred = self.trainer.predict(results["volatility"].model, test_dataset.X)
            
            from sklearn.metrics import mean_squared_error
            import numpy as np
            test_metrics["volatility"] = {
                "test_rmse": np.sqrt(mean_squared_error(test_dataset.y_volatility, y_pred))
            }
        
        return test_metrics
