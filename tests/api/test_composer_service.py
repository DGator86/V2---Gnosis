"""
Tests for Composer API service.

Tests HTTP endpoints for directive composition and snapshot generation.
"""

import pytest
from fastapi.testclient import TestClient
from datetime import datetime

from api.app import app
from api.schemas_composer import (
    ComposerDirectiveResponse,
    ComposerSnapshotResponse,
    HealthCheckResponse,
)

client = TestClient(app)


# ============================================================================
# Health Check Tests
# ============================================================================

def test_system_health():
    """Test system-level health check."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data


def test_composer_health():
    """Test composer-specific health check."""
    response = client.get("/composer/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["ok", "error"]
    assert data["version"] == "1.0.0"
    assert "engines_loaded" in data


# ============================================================================
# Utility Endpoint Tests
# ============================================================================

def test_supported_symbols():
    """Test supported symbols endpoint."""
    response = client.get("/composer/supported-symbols")
    assert response.status_code == 200
    data = response.json()
    assert "symbols" in data
    assert isinstance(data["symbols"], list)
    assert len(data["symbols"]) > 0
    assert "SPY" in data["symbols"]


def test_root_redirects_to_docs():
    """Test root endpoint redirects to API docs."""
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 307  # Redirect
    assert response.headers["location"] == "/docs"


# ============================================================================
# Directive Endpoint Tests
# ============================================================================

@pytest.mark.skip(reason="Requires full engine wiring - placeholder for future")
@pytest.mark.regime_slow
def test_get_directive_success():
    """Test successful directive retrieval for SPY."""
    response = client.get("/composer/directive?symbol=SPY")
    assert response.status_code == 200
    
    # Validate response structure
    data = response.json()
    assert "symbol" in data
    assert data["symbol"] == "SPY"
    assert "timestamp" in data
    assert "composite" in data
    
    # Validate composite directive
    composite = data["composite"]
    assert composite["direction"] in [-1, 0, 1]
    assert 0 <= composite["strength"] <= 100
    assert 0 <= composite["confidence"] <= 1.0
    assert composite["trade_style"] in ["momentum", "breakout", "mean_revert", "no_trade"]
    assert "expected_move_cone" in composite
    assert "rationale" in composite


@pytest.mark.skip(reason="Requires full engine wiring - placeholder for future")
@pytest.mark.regime_slow
def test_get_directive_invalid_symbol():
    """Test directive endpoint with invalid symbol."""
    response = client.get("/composer/directive?symbol=INVALID")
    # Should either return 404 or valid response with degraded confidence
    assert response.status_code in [200, 404, 422]


def test_get_directive_missing_symbol():
    """Test directive endpoint without symbol parameter."""
    response = client.get("/composer/directive")
    assert response.status_code == 422  # Validation error


# ============================================================================
# Snapshot Endpoint Tests
# ============================================================================

@pytest.mark.skip(reason="Requires full engine wiring - placeholder for future")
@pytest.mark.regime_slow
def test_get_snapshot_success():
    """Test successful snapshot retrieval."""
    response = client.get("/composer/snapshot?symbol=SPY")
    assert response.status_code == 200
    
    data = response.json()
    assert "symbol" in data
    assert "timestamp" in data
    assert "composite" in data
    assert "engines" in data
    
    # Validate engines breakdown
    engines = data["engines"]
    assert "hedge" in engines
    assert "liquidity" in engines
    assert "sentiment" in engines
    
    # Validate engine directive structure
    for engine_name, engine_data in engines.items():
        assert "engine_name" in engine_data
        assert "direction" in engine_data
        assert "strength" in engine_data
        assert "confidence" in engine_data
        assert "regime" in engine_data
        assert "energy" in engine_data


@pytest.mark.skip(reason="Requires full engine wiring - placeholder for future")
@pytest.mark.regime_slow
def test_snapshot_includes_regime_weights():
    """Test that snapshot includes regime weight breakdown."""
    response = client.get("/composer/snapshot?symbol=SPY")
    assert response.status_code == 200
    
    data = response.json()
    if "regime_weights" in data and data["regime_weights"]:
        weights = data["regime_weights"]
        assert "hedge" in weights
        assert "liquidity" in weights
        assert "sentiment" in weights
        assert "global_regime" in weights
        
        # Weights should sum to approximately 1.0
        total_weight = weights["hedge"] + weights["liquidity"] + weights["sentiment"]
        assert 0.99 <= total_weight <= 1.01


# ============================================================================
# Schema Validation Tests
# ============================================================================

def test_health_check_schema():
    """Test health check response conforms to schema."""
    response = client.get("/composer/health")
    assert response.status_code == 200
    
    # Validate with Pydantic
    health_data = HealthCheckResponse(**response.json())
    assert health_data.status in ["ok", "error"]
    assert health_data.version is not None


@pytest.mark.skip(reason="Requires full engine wiring")
@pytest.mark.regime_slow
def test_directive_response_schema():
    """Test directive response conforms to schema."""
    response = client.get("/composer/directive?symbol=SPY")
    if response.status_code == 200:
        # Validate with Pydantic
        directive_data = ComposerDirectiveResponse(**response.json())
        assert directive_data.symbol == "SPY"
        assert directive_data.composite.direction in [-1, 0, 1]


@pytest.mark.skip(reason="Requires full engine wiring")
@pytest.mark.regime_slow
def test_snapshot_response_schema():
    """Test snapshot response conforms to schema."""
    response = client.get("/composer/snapshot?symbol=SPY")
    if response.status_code == 200:
        # Validate with Pydantic
        snapshot_data = ComposerSnapshotResponse(**response.json())
        assert snapshot_data.symbol == "SPY"
        assert len(snapshot_data.engines) == 3


# ============================================================================
# Error Handling Tests
# ============================================================================

def test_directive_handles_engine_failure_gracefully():
    """Test that directive endpoint handles engine failures gracefully."""
    # For now, endpoint returns 501 (Not Implemented) until engines are wired
    response = client.get("/composer/directive?symbol=SPY")
    assert response.status_code in [500, 501]
    assert "detail" in response.json()


def test_snapshot_handles_engine_failure_gracefully():
    """Test that snapshot endpoint handles engine failures gracefully."""
    # For now, endpoint returns 501 (Not Implemented) until engines are wired
    response = client.get("/composer/snapshot?symbol=SPY")
    assert response.status_code in [500, 501]
    assert "detail" in response.json()


# ============================================================================
# Performance Tests (Optional)
# ============================================================================

@pytest.mark.skip(reason="Performance test - run manually")
@pytest.mark.regime_slow
def test_directive_response_time():
    """Test that directive endpoint responds within acceptable time."""
    import time
    
    start = time.time()
    response = client.get("/composer/directive?symbol=SPY")
    elapsed = time.time() - start
    
    assert elapsed < 2.0  # Should respond within 2 seconds
    assert response.status_code in [200, 501]


@pytest.mark.skip(reason="Performance test - run manually")
@pytest.mark.regime_slow
def test_snapshot_response_time():
    """Test that snapshot endpoint responds within acceptable time."""
    import time
    
    start = time.time()
    response = client.get("/composer/snapshot?symbol=SPY")
    elapsed = time.time() - start
    
    assert elapsed < 2.0  # Should respond within 2 seconds
    assert response.status_code in [200, 501]
