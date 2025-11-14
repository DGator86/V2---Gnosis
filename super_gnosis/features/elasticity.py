"""Elasticity and price impact feature computation."""

from __future__ import annotations

from core.schemas import OrderFlowFeatures, ElasticityMetrics


def compute_elasticity_features(order_flow: OrderFlowFeatures) -> ElasticityMetrics:
    """Estimate elasticity metrics from order flow."""

    # TODO: implement elasticity estimation
    return ElasticityMetrics(
        dp_dq=0.0,
        dq_dp=0.0,
        dealer_dq_dp=0.0,
        net_elasticity=0.0,
        energy_per_pct_move=0.0,
    )
