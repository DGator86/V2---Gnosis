from __future__ import annotations

from typing import List, Tuple

import numpy as np

from .schemas import (
    ElasticitySummary,
    GreekFieldArrays,
    GreekStructuralSummary,
    HedgeEngineConfig,
    OptionsSurfaceSnapshot,
    OptionTenorExposure,
    StructuralLevels,
    TenorFieldContribution,
    UnderlyingSnapshot,
)


def build_price_grid(spot: float, cfg: HedgeEngineConfig) -> np.ndarray:
    """Construct a symmetric price grid around spot using percentage width."""

    half_width = cfg.price_grid_pct_width
    lo = spot * (1.0 - half_width)
    hi = spot * (1.0 + half_width)
    return np.linspace(lo, hi, cfg.price_grid_points)


def _smooth_profile(values: np.ndarray, lam: float) -> np.ndarray:
    """Simple exponential-kernel smoother."""

    if len(values) <= 2 or lam <= 0:
        return values

    kernel_size = max(3, int(min(len(values) // 5, 21)))
    kernel = np.exp(-lam * np.linspace(-1.0, 1.0, kernel_size) ** 2)
    kernel /= kernel.sum()

    padded = np.pad(values, (kernel_size // 2,), mode="edge")
    smoothed = np.convolve(padded, kernel, mode="same")
    return smoothed[kernel_size // 2 : -kernel_size // 2]


def interpolate_exposures_to_grid(
    tenor: OptionTenorExposure,
    price_grid: np.ndarray,
    cfg: HedgeEngineConfig,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Interpolate gamma, vanna, charm per strike onto dense price grid."""

    strikes = np.array([exposure.strike for exposure in tenor.exposures], dtype=float)
    gamma = np.array([exposure.gamma for exposure in tenor.exposures], dtype=float)
    vanna = np.array([exposure.vanna for exposure in tenor.exposures], dtype=float)
    charm = np.array([exposure.charm for exposure in tenor.exposures], dtype=float)

    if len(strikes) < 2:
        n = len(price_grid)
        return np.zeros(n), np.zeros(n), np.zeros(n)

    order = np.argsort(strikes)
    strikes = strikes[order]
    gamma = gamma[order]
    vanna = vanna[order]
    charm = charm[order]

    gamma_grid = np.interp(price_grid, strikes, gamma, left=0.0, right=0.0)
    vanna_grid = np.interp(price_grid, strikes, vanna, left=0.0, right=0.0)
    charm_grid = np.interp(price_grid, strikes, charm, left=0.0, right=0.0)

    gamma_grid = _smooth_profile(gamma_grid, cfg.gamma_smoothing_lambda)

    return gamma_grid, vanna_grid, charm_grid


def aggregate_across_tenors(
    surface: OptionsSurfaceSnapshot,
    price_grid: np.ndarray,
    cfg: HedgeEngineConfig,
) -> Tuple[
    np.ndarray,
    np.ndarray,
    np.ndarray,
    List[TenorFieldContribution],
    dict,
]:
    """Aggregate gamma/vanna/charm across tenors with liquidity and DTE weights."""

    gamma_total = np.zeros_like(price_grid)
    vanna_total = np.zeros_like(price_grid)
    charm_total = np.zeros_like(price_grid)

    tenor_contrib: List[TenorFieldContribution] = []
    diagnostics: dict = {
        "tenor_count": len(surface.tenors),
        "effective_liquidity": 0.0,
    }

    if not surface.tenors:
        return gamma_total, vanna_total, charm_total, tenor_contrib, diagnostics

    tau = 30.0  # soft time constant (days) for DTE weighting

    raw_profiles: List[Tuple[OptionTenorExposure, np.ndarray, np.ndarray, np.ndarray]] = []
    raw_weights: List[float] = []

    for tenor in surface.tenors:
        gamma_grid, vanna_grid, charm_grid = interpolate_exposures_to_grid(
            tenor=tenor,
            price_grid=price_grid,
            cfg=cfg,
        )

        liq_weight = max(tenor.liquidity_score, 0.0)
        time_weight = np.exp(-max(tenor.dte, 0.0) / tau)
        weight = liq_weight * time_weight

        raw_profiles.append((tenor, gamma_grid, vanna_grid, charm_grid))
        raw_weights.append(weight)

    weights_arr = np.array(raw_weights, dtype=float)
    if weights_arr.sum() <= 0:
        weights_arr = np.ones_like(weights_arr)
    raw_weight_sum = float(weights_arr.sum())
    weights_arr /= raw_weight_sum
    diagnostics["effective_liquidity"] = raw_weight_sum

    for weight, (tenor, gamma_grid, vanna_grid, charm_grid) in zip(weights_arr, raw_profiles):
        gamma_total += weight * gamma_grid
        vanna_total += weight * vanna_grid
        charm_total += weight * charm_grid

        tenor_contrib.append(
            TenorFieldContribution(
                expiry=tenor.expiry,
                dte=tenor.dte,
                weight=float(weight),
                gamma_field=gamma_grid.tolist(),
                vanna_field=vanna_grid.tolist(),
                charm_field=charm_grid.tolist(),
            )
        )

    return gamma_total, vanna_total, charm_total, tenor_contrib, diagnostics


def compute_total_field(
    gamma_field: np.ndarray,
    vanna_field: np.ndarray,
    charm_field: np.ndarray,
    cfg: HedgeEngineConfig,
) -> np.ndarray:
    """Combine gamma, vanna, charm into a single total hedge field."""

    return gamma_field + cfg.vanna_weight * vanna_field + cfg.charm_weight * charm_field


def compute_derivatives(
    price_grid: np.ndarray,
    field: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray]:
    """First and second derivatives of a scalar field w.r.t price."""

    dS = np.gradient(price_grid)
    d_field = np.gradient(field, dS)
    d2_field = np.gradient(d_field, dS)
    return d_field, d2_field


def compute_potential_from_field(
    price_grid: np.ndarray,
    total_field: np.ndarray,
) -> np.ndarray:
    """Integrate the total field along price to get a potential-like function."""

    dS = np.diff(price_grid, prepend=price_grid[0])
    potential = np.cumsum(total_field * dS)
    potential -= potential.mean()
    std = np.std(potential)
    if std > 0:
        potential /= std
    return potential


def compute_elasticity_and_energy(
    price_grid: np.ndarray,
    total_field: np.ndarray,
    underlying: UnderlyingSnapshot,
    cfg: HedgeEngineConfig,
) -> Tuple[np.ndarray, np.ndarray, ElasticitySummary]:
    """Elasticity ~ 1 / |d(field)/dS|. Energy ~ cfg.energy_scale / |field|."""

    if len(price_grid) < 3:
        zeros = np.zeros_like(price_grid)
        summary = ElasticitySummary(
            spot_elasticity=0.0,
            spot_energy_to_move_1pct=0.0,
            spot_energy_to_move_atr=0.0,
            mean_elasticity=0.0,
            max_elasticity=0.0,
            min_elasticity=0.0,
        )
        return zeros, zeros, summary

    d_field, _ = compute_derivatives(price_grid, total_field)

    eps = 1e-9
    elasticity = 1.0 / (np.abs(d_field) + eps)
    energy_1pct = cfg.energy_scale / (np.abs(total_field) + eps)

    spot = underlying.spot_price
    idx_spot = int(np.argmin(np.abs(price_grid - spot)))

    one_pct_up = spot * 1.01
    one_pct_dn = spot * 0.99
    idx_up = int(np.argmin(np.abs(price_grid - one_pct_up)))
    idx_dn = int(np.argmin(np.abs(price_grid - one_pct_dn)))

    atr = max(underlying.atr, 0.0)
    if atr > 0:
        idx_up_atr = int(np.argmin(np.abs(price_grid - (spot + atr))))
        idx_dn_atr = int(np.argmin(np.abs(price_grid - (spot - atr))))
        spot_energy_atr = float(0.5 * (energy_1pct[idx_up_atr] + energy_1pct[idx_dn_atr]))
    else:
        spot_energy_atr = 0.0

    summary = ElasticitySummary(
        spot_elasticity=float(elasticity[idx_spot]),
        spot_energy_to_move_1pct=float(0.5 * (energy_1pct[idx_up] + energy_1pct[idx_dn])),
        spot_energy_to_move_atr=spot_energy_atr,
        mean_elasticity=float(np.mean(elasticity)),
        max_elasticity=float(np.max(elasticity)),
        min_elasticity=float(np.min(elasticity)),
    )

    return elasticity, energy_1pct, summary


def _structural_levels_from_field(
    price_grid: np.ndarray,
    field: np.ndarray,
) -> StructuralLevels:
    """Compute local maxima/minima and low-curvature levels for a scalar field."""

    d1 = np.gradient(field)
    d2 = np.gradient(d1)

    sign = np.sign(d1)
    sign_change = np.diff(sign)

    maxima_idx = np.where(sign_change < 0)[0] + 1
    minima_idx = np.where(sign_change > 0)[0] + 1

    curvature = np.abs(d2)
    low_curv_mask = curvature < np.percentile(curvature, 20)

    return StructuralLevels(
        maxima_levels=price_grid[maxima_idx].tolist(),
        minima_levels=price_grid[minima_idx].tolist(),
        low_curvature_levels=price_grid[low_curv_mask].tolist(),
    )


def build_field_arrays(
    price_grid: np.ndarray,
    gamma_field: np.ndarray,
    vanna_field: np.ndarray,
    charm_field: np.ndarray,
    total_field: np.ndarray,
    potential: np.ndarray,
    elasticity: np.ndarray,
    energy_1pct: np.ndarray,
) -> GreekFieldArrays:
    """Bundle all scalar fields and derivatives into a single arrays object."""

    d_total, d2_total = compute_derivatives(price_grid, total_field)

    return GreekFieldArrays(
        price_grid=price_grid.tolist(),
        gamma_field=gamma_field.tolist(),
        vanna_field=vanna_field.tolist(),
        charm_field=charm_field.tolist(),
        total_field=total_field.tolist(),
        d_field_dS=d_total.tolist(),
        d2_field_dS2=d2_total.tolist(),
        potential=potential.tolist(),
        elasticity=elasticity.tolist(),
        energy_1pct=energy_1pct.tolist(),
    )


def build_structural_summary(
    price_grid: np.ndarray,
    gamma_field: np.ndarray,
    vanna_field: np.ndarray,
    charm_field: np.ndarray,
    total_field: np.ndarray,
) -> GreekStructuralSummary:
    """Structural levels for each Greek field and the total field."""

    gamma_struct = _structural_levels_from_field(price_grid, gamma_field)
    vanna_struct = _structural_levels_from_field(price_grid, vanna_field)
    charm_struct = _structural_levels_from_field(price_grid, charm_field)
    total_struct = _structural_levels_from_field(price_grid, total_field)

    return GreekStructuralSummary(
        gamma_struct=gamma_struct,
        vanna_struct=vanna_struct,
        charm_struct=charm_struct,
        total_struct=total_struct,
    )
