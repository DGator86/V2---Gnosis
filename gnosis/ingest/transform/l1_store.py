from __future__ import annotations
from pathlib import Path
import pandas as pd
from typing import Iterable
from ...schemas.base import L1Thin

class L1Store:
    def __init__(self, root: str = "data_l1"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def write_many(self, records: Iterable[L1Thin]) -> str:
        df = pd.DataFrame([r.model_dump(mode="json") for r in records])
        if df.empty:
            return ""
        date = pd.to_datetime(df["t_event"]).dt.date.iloc[0].isoformat()
        fn = self.root / f"l1_{date}.parquet"
        if fn.exists():
            old = pd.read_parquet(fn)
            df = pd.concat([old, df], ignore_index=True)
        df.to_parquet(fn, index=False)
        return str(fn)