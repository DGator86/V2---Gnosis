"""Example usage of the Super Gnosis pipeline."""
from __future__ import annotations

from datetime import datetime, timezone

from config import load_config
from engines.inputs.stub_adapters import StaticMarketDataAdapter, StaticNewsAdapter, StaticOptionsAdapter
from main import build_pipeline


def main() -> None:
    config = load_config()
    adapters = {
        "options": StaticOptionsAdapter(),
        "market": StaticMarketDataAdapter(),
        "news": StaticNewsAdapter(),
    }
    runner = build_pipeline("SPY", config, adapters)
    result = runner.run_once(datetime.now(timezone.utc))
    print("Snapshot", result["snapshot"])
    print("Composite", result["composite_suggestion"])
    for idea in result["trade_ideas"]:
        print("Trade idea", idea)


if __name__ == "__main__":
    main()
