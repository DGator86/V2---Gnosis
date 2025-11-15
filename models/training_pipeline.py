from __future__ import annotations

"""Training pipeline placeholder."""

from typing import Any, Dict

import polars as pl

from models.feature_builder import FeatureBuilder


def run_training(data: pl.DataFrame, config: Dict[str, Any]) -> Dict[str, Any]:
    builder = FeatureBuilder(config)
    features = builder.build_training_features(data)
    return {"features": features}
