from __future__ import annotations

"""Simple JSONL ledger store."""

import json
from pathlib import Path
from typing import Iterable

from schemas.core_schemas import LedgerRecord


class LedgerStore:
    """Persist ledger records to a JSONL file."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, record: LedgerRecord) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(record.model_dump_json())
            handle.write("\n")

    def stream(self) -> Iterable[LedgerRecord]:
        if not self.path.exists():
            return []
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    yield LedgerRecord.model_validate_json(line)
