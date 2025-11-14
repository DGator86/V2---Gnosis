from __future__ import annotations

from typing import Dict, List

import numpy as np

from .processors import (
    aggregate_across_tenors,
    build_field_arrays,
    build_price_grid,
    build_structural_summary,
    compute_elasticity_and_energy,
    compute_potential_from_field,
    compute_total_field,
)
from .schemas import (
    GreekFieldArrays,
    GreekStructuralSummary,
    HedgeEngineConfig,
    HedgeEngineInputs,
    HedgeEngineOutput,
)


class HedgeEngine:
    """Dealer Hedge Pressure Field Engine (pure data version)."""

    def __init__(self, default_config: HedgeEngineConfig | None = None) -> None:
        self._default_config = default_config or HedgeEngineConfig()

    @property
    def config(self) -> HedgeEngineConfig:
        return self._default_config

    def run_bar(self, inputs: HedgeEngineInputs) -> HedgeEngineOutput:
        """Compute hedge fields for a single bar of inputs."""

        cfg = inputs.config or self._default_config
        underlying = inputs.underlying
        surface = inputs.options_surface

        spot = underlying.spot_price
        price_grid = build_price_grid(spot=spot, cfg=cfg)

        (
            gamma_field,
            vanna_field,
            charm_field,
            tenor_contrib,
            agg_diag,
        ) = aggregate_across_tenors(
            surface=surface,
            price_grid=price_grid,
            cfg=cfg,
        )

        total_field = compute_total_field(
            gamma_field=gamma_field,
            vanna_field=vanna_field,
            charm_field=charm_field,
            cfg=cfg,
        )

        potential = compute_potential_from_field(
            price_grid=price_grid,
            total_field=total_field,
        )

        elasticity, energy_1pct, elasticity_summary = compute_elasticity_and_energy(
            price_grid=price_grid,
            total_field=total_field,
            underlying=underlying,
            cfg=cfg,
        )

        fields: GreekFieldArrays = build_field_arrays(
            price_grid=price_grid,
            gamma_field=gamma_field,
            vanna_field=vanna_field,
            charm_field=charm_field,
            total_field=total_field,
            potential=potential,
            elasticity=elasticity,
            energy_1pct=energy_1pct,
        )

        structural: GreekStructuralSummary = build_structural_summary(
            price_grid=price_grid,
            gamma_field=gamma_field,
            vanna_field=vanna_field,
            charm_field=charm_field,
            total_field=total_field,
        )

        options_meta: Dict[str, float] = {
            "tenor_count": float(agg_diag.get("tenor_count", 0)),
            "effective_liquidity": float(agg_diag.get("effective_liquidity", 0.0)),
            "total_gamma_abs": float(np.sum(np.abs(gamma_field))),
            "total_vanna_abs": float(np.sum(np.abs(vanna_field))),
            "total_charm_abs": float(np.sum(np.abs(charm_field))),
        }

        diagnostics: Dict[str, float] = {
            "spot_price": float(spot),
            "realized_vol_20d": float(underlying.realized_vol_20d),
            "vix_level": float(underlying.vix_level or 0.0),
            "intraday_return": float(underlying.intraday_return),
        }

        return HedgeEngineOutput(
            underlying=underlying,
            config_used=cfg,
            fields=fields,
            structural=structural,
            elasticity_summary=elasticity_summary,
            tenor_contributions=tenor_contrib,
            options_surface_meta=options_meta,
            diagnostics=diagnostics,
        )
