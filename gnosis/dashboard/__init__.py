"""
Dashboard Module

Simple web dashboard for monitoring live trading.
"""

from gnosis.dashboard.dashboard_server import (
    app,
    dashboard_state,
    update_positions,
    add_trade,
    update_agent_votes,
    add_memory_recall,
    update_portfolio_stats,
    update_regime,
    update_bar
)

__all__ = [
    "app",
    "dashboard_state",
    "update_positions",
    "add_trade",
    "update_agent_votes",
    "add_memory_recall",
    "update_portfolio_stats",
    "update_regime",
    "update_bar"
]
