from __future__ import annotations
from pathlib import Path
from datetime import datetime
from typing import Dict, Any
import duckdb, pandas as pd
import json
from ..schemas.base import L3Canonical

class FeatureStore:
    def __init__(self, root: str = "data", read_only: bool = False):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.read_only = read_only
        # Only create DB connection if not read-only (backtests use parquet directly)
        if not read_only:
            self.db = duckdb.connect(str(self.root / "feature_store.duckdb"))
        else:
            self.db = None

    def _path(self, symbol: str, bar: datetime, feature_set_id: str) -> Path:
        d = bar.strftime("%Y-%m-%d")
        p = self.root / f"date={d}" / f"symbol={symbol}" / f"feature_set_id={feature_set_id}"
        p.mkdir(parents=True, exist_ok=True)
        return p / "features.parquet"

    def write(self, row: L3Canonical) -> None:
        fn = self._path(row.symbol, row.bar, row.feature_set_id)
        df = pd.DataFrame([row.model_dump(mode="json")])
        if fn.exists():
            old = pd.read_parquet(fn)
            df = pd.concat([old, df], ignore_index=True)
        df.to_parquet(fn, index=False)

    def read_pit(self, symbol: str, t_event: datetime, feature_set_id: str) -> Dict[str, Any]:
        d = t_event.strftime("%Y-%m-%d")
        fn = self.root / f"date={d}" / f"symbol={symbol}" / f"feature_set_id={feature_set_id}" / "features.parquet"
        if not fn.exists():
            raise FileNotFoundError(f"No features for {symbol} on {d} (set={feature_set_id})")
        
        # Read parquet directly (no DuckDB needed for reading)
        df = pd.read_parquet(fn, engine='pyarrow')
        df["bar"] = pd.to_datetime(df["bar"])
        df = df[df["bar"] <= pd.Timestamp(t_event)]
        if df.empty:
            raise ValueError("No bar <= t_event")
        row_dict = df.sort_values("bar").iloc[-1].to_dict()
        # Convert Timestamp to ISO string for JSON serialization
        if isinstance(row_dict.get("bar"), pd.Timestamp):
            row_dict["bar"] = row_dict["bar"].isoformat()
        # The data is already stored as JSON-compatible format from model_dump(mode="json")
        # Just ensure we return clean dict for FastAPI
        return json.loads(json.dumps(row_dict, default=str))