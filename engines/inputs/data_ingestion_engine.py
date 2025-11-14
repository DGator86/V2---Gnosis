"""Data ingestion engine for live market data providers.

This module introduces an abstraction for connecting the DHPE pipeline to
external market data providers.  It performs structured validation and normalises
responses into the ``RawInputs`` schema that the downstream engines expect.

The goal is to bridge the gap between the previous demo inputs engine and a
production-grade ingestion stack, providing:

* Provider interface with clearly defined fetch methods
* Robust error handling with actionable messages
* Data quality checks (required fields, timestamps, ordering)
* Hooks for latency instrumentation and audit logs via the shared logger
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence

from schemas import RawInputs
from ..orchestration.logger import get_logger

logger = get_logger(__name__)


class DataIngestionError(RuntimeError):
    """Raised when the ingestion engine cannot produce a valid ``RawInputs``."""


@dataclass
class ProviderResponse:
    """Container for provider payloads and simple metadata."""

    data: Sequence[Dict[str, Any]]
    latency_ms: Optional[float] = None


class MarketDataProvider(ABC):
    """Abstract base class for live market data providers."""

    name: str = "unknown"

    @abstractmethod
    def fetch_options_chain(self, symbol: str) -> ProviderResponse:
        """Return the latest options chain for ``symbol``."""

    @abstractmethod
    def fetch_trades(self, symbol: str) -> ProviderResponse:
        """Return recent trade prints for ``symbol``."""

    @abstractmethod
    def fetch_news(self, symbol: str) -> ProviderResponse:
        """Return recent news stories for ``symbol``."""

    def fetch_orderbook(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Return current order book snapshot if available."""

        return None

    def fetch_fundamentals(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Return latest fundamental data if available."""

        return None


class DataIngestionEngine:
    """Ingests data from a :class:`MarketDataProvider` and validates integrity."""

    REQUIRED_OPTION_FIELDS = {"type", "strike", "expiry"}
    REQUIRED_TRADE_FIELDS = {"timestamp", "price", "size"}
    REQUIRED_NEWS_FIELDS = {"timestamp", "title", "sentiment_score"}

    def __init__(self, provider: MarketDataProvider):
        self._provider = provider
        logger.info("Data ingestion engine initialised | provider=%s", provider.name)

    def fetch(self, symbol: str) -> RawInputs:
        """Fetch and validate inputs for ``symbol`` from the configured provider."""

        try:
            options = self._provider.fetch_options_chain(symbol)
            trades = self._provider.fetch_trades(symbol)
            news = self._provider.fetch_news(symbol)
            orderbook = self._provider.fetch_orderbook(symbol)
            fundamentals = self._provider.fetch_fundamentals(symbol)
        except Exception as exc:  # pragma: no cover - defensive logging path
            logger.exception("Provider %s failed while fetching data", self._provider.name)
            raise DataIngestionError(f"Provider {self._provider.name} error: {exc}") from exc

        raw_inputs = RawInputs(
            symbol=symbol,
            timestamp=datetime.now().timestamp(),
            options=list(options.data),
            trades=self._sort_by_timestamp(list(trades.data)),
            news=self._sort_by_timestamp(list(news.data)),
            orderbook=orderbook,
            fundamentals=fundamentals,
        )

        issues = self._validate(raw_inputs)
        if issues:
            issue_text = "; ".join(issues)
            logger.error("Data validation failed for %s | %s", symbol, issue_text)
            raise DataIngestionError(issue_text)

        logger.info(
            "Ingestion successful | symbol=%s provider=%s options=%d trades=%d news=%d",
            symbol,
            self._provider.name,
            len(raw_inputs.options),
            len(raw_inputs.trades),
            len(raw_inputs.news),
        )
        return raw_inputs

    def _validate(self, raw: RawInputs) -> List[str]:
        """Return a list of validation issues for ``raw`` (empty if valid)."""

        issues: List[str] = []

        if not raw.options:
            issues.append("options_chain:empty")
        else:
            for idx, option in enumerate(raw.options):
                missing = self.REQUIRED_OPTION_FIELDS - option.keys()
                if missing:
                    issues.append(f"options_chain[{idx}]:missing={sorted(missing)}")

        if not raw.trades:
            issues.append("trades:empty")
        else:
            for idx, trade in enumerate(raw.trades):
                missing = self.REQUIRED_TRADE_FIELDS - trade.keys()
                if missing:
                    issues.append(f"trades[{idx}]:missing={sorted(missing)}")
                elif trade["timestamp"] is None:
                    issues.append(f"trades[{idx}]:timestamp_none")

        if not raw.news:
            issues.append("news:empty")
        else:
            for idx, item in enumerate(raw.news):
                missing = self.REQUIRED_NEWS_FIELDS - item.keys()
                if missing:
                    issues.append(f"news[{idx}]:missing={sorted(missing)}")

        return issues

    @staticmethod
    def _sort_by_timestamp(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Return ``records`` sorted by ``timestamp`` if the key exists."""

        if not records or "timestamp" not in records[0]:
            return records

        try:
            return sorted(records, key=lambda record: record["timestamp"])
        except Exception:  # pragma: no cover - defensive
            return records


__all__ = [
    "DataIngestionEngine",
    "DataIngestionError",
    "MarketDataProvider",
    "ProviderResponse",
]
