"""Minimal integration checklist for Super Gnosis."""
from __future__ import annotations

from pathlib import Path

from config import load_config


def check_file(path: str) -> bool:
    exists = Path(path).exists()
    status = "✅" if exists else "❌"
    print(f"{status} {path}")
    return exists


def main() -> int:
    print("Super Gnosis Integration Checklist")
    print("=" * 40)

    print("Core Files:")
    core = [
        "config/config.yaml",
        "schemas/core_schemas.py",
        "engines/hedge/hedge_engine_v3.py",
        "engines/liquidity/liquidity_engine_v1.py",
        "engines/sentiment/sentiment_engine_v1.py",
        "engines/elasticity/elasticity_engine_v1.py",
        "trade/trade_agent_v1.py",
        "engines/orchestration/pipeline_runner.py",
        "main.py",
    ]
    ok = all(check_file(path) for path in core)

    print("\nConfig load:")
    try:
        load_config()
        print("✅ config loaded")
    except Exception as exc:  # pragma: no cover - diagnostics only
        print(f"❌ config failed: {exc}")
        ok = False

    print("\nLedger artifact (created after run):")
    check_file("data/ledger.jsonl")

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
