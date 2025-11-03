from __future__ import annotations
import csv
from pathlib import Path
from typing import Iterator, Dict, Any

def stream_csv(path: str) -> Iterator[Dict[str, Any]]:
    p = Path(path)
    with p.open() as f:
        rdr = csv.DictReader(f)
        for row in rdr:
            # map/rename as needed to match transform_record expectations
            yield {
                "symbol": row.get("symbol"),
                "t": row.get("timestamp"),   # vendor local time string
                "price": float(row["price"]) if row.get("price") else None,
                "iv": float(row["iv"]) if row.get("iv") else None,
                "oi": int(row["oi"]) if row.get("oi") else None
            }