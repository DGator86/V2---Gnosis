"""Order flow feature engineering."""

from __future__ import annotations

from core.schemas import MarketTick, OrderFlowFeatures


def compute_order_flow_features(bar: MarketTick) -> OrderFlowFeatures:
    """Compute order flow related features."""

    # TODO: implement tape reading features
    return OrderFlowFeatures(
        aggressive_buy_volume=0.0,
        aggressive_sell_volume=0.0,
        delta_volume=0.0,
        order_imbalance=0.0,
        avg_trade_size=0.0,
        sweep_score=0.0,
        absorption_score=0.0,
        dark_pool_volume_estimate=None,
    )
