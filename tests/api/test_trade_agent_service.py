# tests/api/test_trade_agent_service.py

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.app import app

client = TestClient(app)


class TestTradeAgentHealth:
    """Test health check endpoint."""

    def test_trade_agent_health(self):
        resp = client.get("/trade-agent/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["component"] == "trade_agent_v2"


class TestStrategiesEndpoint:
    """Test strategies listing endpoint."""

    def test_list_strategies_returns_list(self):
        resp = client.get("/trade-agent/strategies")
        assert resp.status_code == 200
        strategies = resp.json()
        assert isinstance(strategies, list)
        assert len(strategies) > 0

    def test_list_strategies_includes_expected_types(self):
        resp = client.get("/trade-agent/strategies")
        strategies = resp.json()

        expected = ["stock", "long_call", "long_put", "iron_condor"]
        for exp in expected:
            assert exp in strategies


class TestGenerateTradesEndpoint:
    """Test trade generation endpoint."""

    def _get_sample_directive(self) -> dict:
        """Helper to create a valid directive payload."""
        return {
            "direction": 1,  # bullish
            "strength": 65.0,
            "confidence": 0.75,
            "volatility": 45.0,
            "energy_cost": 1.2,
            "trade_style": "momentum",
            "expected_move_cone": {
                "reference_price": 500.0,
                "bands": {
                    "15m": {
                        "horizon_minutes": 15,
                        "lower": 498.0,
                        "upper": 502.0,
                        "confidence": 0.7,
                    }
                }
            },
            "rationale": "Bullish momentum with moderate volatility",
        }

    def test_generate_trades_basic_success(self):
        payload = self._get_sample_directive()

        resp = client.post(
            "/trade-agent/generate?asset=SPY&underlying_price=500.0&capital=10000",
            json=payload,
        )

        assert resp.status_code == 200
        ideas = resp.json()
        assert isinstance(ideas, list)
        assert len(ideas) > 0

    def test_generate_trades_returns_valid_trade_ideas(self):
        payload = self._get_sample_directive()

        resp = client.post(
            "/trade-agent/generate?asset=SPY&underlying_price=500.0",
            json=payload,
        )

        ideas = resp.json()
        first_idea = ideas[0]

        # Validate structure
        assert "asset" in first_idea
        assert "strategy_type" in first_idea
        assert "description" in first_idea
        assert "confidence" in first_idea
        assert first_idea["asset"] == "SPY"

    def test_generate_trades_missing_asset_fails(self):
        payload = self._get_sample_directive()

        resp = client.post(
            "/trade-agent/generate?underlying_price=500.0",
            json=payload,
        )

        assert resp.status_code == 422  # Validation error

    def test_generate_trades_missing_underlying_price_fails(self):
        payload = self._get_sample_directive()

        resp = client.post(
            "/trade-agent/generate?asset=SPY",
            json=payload,
        )

        assert resp.status_code == 422

    def test_generate_trades_with_custom_capital(self):
        payload = self._get_sample_directive()

        resp = client.post(
            "/trade-agent/generate?asset=SPY&underlying_price=500.0&capital=50000",
            json=payload,
        )

        assert resp.status_code == 200
        ideas = resp.json()
        assert len(ideas) > 0

    def test_generate_trades_bullish_includes_calls(self):
        payload = self._get_sample_directive()
        payload["direction"] = 1  # bullish

        resp = client.post(
            "/trade-agent/generate?asset=SPY&underlying_price=500.0",
            json=payload,
        )

        ideas = resp.json()
        strategy_types = {idea["strategy_type"] for idea in ideas}

        # Should include call-based strategies
        call_strategies = {"long_call", "call_debit_spread"}
        assert len(call_strategies & strategy_types) > 0

    def test_generate_trades_bearish_includes_puts(self):
        payload = self._get_sample_directive()
        payload["direction"] = -1  # bearish

        resp = client.post(
            "/trade-agent/generate?asset=SPY&underlying_price=500.0",
            json=payload,
        )

        ideas = resp.json()
        strategy_types = {idea["strategy_type"] for idea in ideas}

        # Should include put-based strategies
        put_strategies = {"long_put", "put_debit_spread"}
        assert len(put_strategies & strategy_types) > 0

    def test_generate_trades_neutral_includes_iron_condor(self):
        payload = self._get_sample_directive()
        payload["direction"] = 0  # neutral

        resp = client.post(
            "/trade-agent/generate?asset=SPY&underlying_price=500.0",
            json=payload,
        )

        ideas = resp.json()
        strategy_types = {idea["strategy_type"] for idea in ideas}

        assert "iron_condor" in strategy_types

    def test_generate_trades_ideas_are_ranked(self):
        payload = self._get_sample_directive()

        resp = client.post(
            "/trade-agent/generate?asset=SPY&underlying_price=500.0",
            json=payload,
        )

        ideas = resp.json()

        # Check that ranking_score exists and is sorted descending
        scores = [idea["ranking_score"] for idea in ideas if idea.get("ranking_score")]
        assert scores == sorted(scores, reverse=True)

    def test_generate_trades_with_timeframe_override(self):
        payload = self._get_sample_directive()

        resp = client.post(
            "/trade-agent/generate?asset=SPY&underlying_price=500.0&timeframe=intraday",
            json=payload,
        )

        assert resp.status_code == 200
        ideas = resp.json()
        assert len(ideas) > 0

    def test_generate_trades_invalid_directive_fails(self):
        # Missing required fields
        payload = {"direction": 1}

        resp = client.post(
            "/trade-agent/generate?asset=SPY&underlying_price=500.0",
            json=payload,
        )

        assert resp.status_code == 422


class TestEndToEndIntegration:
    """Test complete flow from directive to trade ideas."""

    def test_full_workflow_bullish_momentum(self):
        """Test full workflow for bullish momentum scenario."""
        directive = {
            "direction": 1,
            "strength": 70.0,
            "confidence": 0.8,
            "volatility": 50.0,
            "energy_cost": 1.5,
            "trade_style": "momentum",
            "expected_move_cone": {
                "reference_price": 450.0,
                "bands": {
                    "1h": {
                        "horizon_minutes": 60,
                        "lower": 448.0,
                        "upper": 452.0,
                        "confidence": 0.75,
                    }
                }
            },
            "rationale": "Strong bullish momentum with high confidence",
        }

        resp = client.post(
            "/trade-agent/generate?asset=AAPL&underlying_price=450.0&capital=25000",
            json=directive,
        )

        assert resp.status_code == 200
        ideas = resp.json()

        # Verify we got multiple ideas
        assert len(ideas) >= 3

        # Verify all ideas have required fields
        for idea in ideas:
            assert idea["asset"] == "AAPL"
            assert idea["confidence"] > 0
            assert idea["ranking_score"] is not None

        # Top-ranked idea should be highly ranked
        assert ideas[0]["ranking_score"] >= ideas[-1]["ranking_score"]
