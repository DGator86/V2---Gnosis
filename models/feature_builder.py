from __future__ import annotations

"""Feature engineering utilities for the lookahead model."""

from typing import Dict, Any

import polars as pl


class FeatureBuilder:
    """Construct model-ready features from historical data."""

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config

    def build_training_features(self, df: pl.DataFrame) -> Dict[str, pl.DataFrame]:
        if df.is_empty():
            return {"X": pl.DataFrame(), "y_return_1d": pl.Series(name="y_return_1d", values=[])}

        returns = df["close"].pct_change().rename("return")
        df = df.with_columns(returns)

        features = df.select(["return"]).fill_null(0.0)
        labels = df["return"].shift(-1).fill_null(0.0)

        return {"X": features, "y_return_1d": labels}
