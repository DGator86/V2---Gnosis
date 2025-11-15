from __future__ import annotations

"""Compute metrics from ledger records."""

from math import sqrt
from typing import Dict, Iterable, List

from schemas.core_schemas import LedgerRecord


class LedgerMetrics:
    """Derive portfolio metrics from ledger records."""

    @staticmethod
    def compute(records: Iterable[LedgerRecord]) -> Dict[str, float]:
        pnls: List[float] = [record.realized_pnl or 0.0 for record in records]
        if not pnls:
            return {"sharpe": 0.0, "hit_rate": 0.0, "max_drawdown": 0.0, "avg_trade_pnl": 0.0}

        avg = sum(pnls) / len(pnls)
        variance = sum((p - avg) ** 2 for p in pnls) / len(pnls)
        sharpe = avg / sqrt(variance) if variance else 0.0
        hits = sum(1 for p in pnls if p > 0)
        drawdown = min(0.0, min(sum(pnls[:i]) for i in range(1, len(pnls) + 1)))

        return {
            "sharpe": float(sharpe),
            "hit_rate": float(hits / len(pnls)),
            "max_drawdown": float(drawdown),
            "avg_trade_pnl": float(avg),
        }
