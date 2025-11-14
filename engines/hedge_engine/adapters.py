from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd

from schemas import EngineOutput, RawInputs

from .engine import HedgeEngine
from .schemas import (
    HedgeEngineConfig,
    HedgeEngineInputs,
    HedgeEngineOutput,
    OptionStrikeExposure,
    OptionTenorExposure,
    OptionsSurfaceSnapshot,
    UnderlyingSnapshot,
)


def _infer_spot_from_inputs(raw: RawInputs) -> float:
    if raw.orderbook and raw.orderbook.get("mid"):
        return float(raw.orderbook["mid"])

    trades = raw.trades
    if trades:
        return float(trades[-1]["price"])

    strikes = [opt.get("strike") for opt in raw.options if opt.get("strike")]
    if strikes:
        return float(np.median(strikes))

    return 1.0


def _group_option_exposures(
    options: Iterable[Dict],
    spot: float,
    timestamp: pd.Timestamp,
) -> List[OptionTenorExposure]:
    grouped: Dict[Tuple[pd.Timestamp, float], Dict[str, float]] = defaultdict(
        lambda: {"gamma": 0.0, "vanna": 0.0, "charm": 0.0, "open_interest": 0.0, "notional": 0.0}
    )
    totals_by_expiry: Dict[pd.Timestamp, Dict[str, float]] = defaultdict(
        lambda: {"gamma": 0.0, "vanna": 0.0, "charm": 0.0, "notional": 0.0, "open_interest": 0.0}
    )

    for option in options:
        strike_val = option.get("strike")
        expiry_val = option.get("expiry")
        if strike_val is None or expiry_val is None:
            continue

        strike = float(strike_val)
        expiry = pd.to_datetime(expiry_val, unit="s", utc=True).tz_convert(None)

        gamma = float(option.get("gamma", 0.0))
        vanna = float(option.get("vanna", option.get("vega", 0.0) * 0.1))
        charm = float(option.get("charm", 0.0))
        open_interest = float(option.get("open_interest", 0.0))
        notional = float(option.get("notional", open_interest * spot))

        key = (expiry, strike)
        grouped[key]["gamma"] += gamma
        grouped[key]["vanna"] += vanna
        grouped[key]["charm"] += charm
        grouped[key]["open_interest"] += open_interest
        grouped[key]["notional"] += notional

        totals = totals_by_expiry[expiry]
        totals["gamma"] += gamma
        totals["vanna"] += vanna
        totals["charm"] += charm
        totals["open_interest"] += open_interest
        totals["notional"] += notional

    strikes_by_expiry: Dict[pd.Timestamp, List[OptionStrikeExposure]] = defaultdict(list)
    for (expiry, strike), values in grouped.items():
        strikes_by_expiry[expiry].append(
            OptionStrikeExposure(
                strike=float(strike),
                gamma=float(values["gamma"]),
                vanna=float(values["vanna"]),
                charm=float(values["charm"]),
                open_interest=int(values["open_interest"]),
                notional=float(values["notional"]),
            )
        )

    tenors: List[OptionTenorExposure] = []
    for expiry, exposures in strikes_by_expiry.items():
        exposures.sort(key=lambda e: e.strike)
        totals = totals_by_expiry[expiry]
        dte = max((expiry - timestamp).total_seconds() / 86400.0, 0.0)
        total_notional = max(totals["notional"], 0.0)
        liquidity_score = float(np.tanh(total_notional / 1e7)) if total_notional > 0 else 0.0

        tenors.append(
            OptionTenorExposure(
                expiry=expiry,
                dte=dte,
                exposures=exposures,
                total_gamma=float(totals["gamma"]),
                total_vanna=float(totals["vanna"]),
                total_charm=float(totals["charm"]),
                total_notional=total_notional,
                liquidity_score=liquidity_score,
            )
        )

    tenors.sort(key=lambda tenor: tenor.expiry)
    return tenors


def build_inputs_from_raw(
    raw: RawInputs,
    config: HedgeEngineConfig | None = None,
) -> HedgeEngineInputs:
    spot = _infer_spot_from_inputs(raw)
    timestamp = pd.to_datetime(raw.timestamp, unit="s", utc=True).tz_convert(None)

    underlying = UnderlyingSnapshot(
        symbol=raw.symbol,
        timestamp=timestamp,
        spot_price=spot,
        intraday_return=0.0,
        realized_vol_20d=0.0,
        atr=float(raw.orderbook.get("spread", 0.0)) if raw.orderbook else 0.0,
        vix_level=None,
    )

    tenors = _group_option_exposures(raw.options, spot=spot, timestamp=timestamp)

    surface = OptionsSurfaceSnapshot(
        symbol=raw.symbol,
        timestamp=timestamp,
        tenors=tenors,
    )

    return HedgeEngineInputs(
        underlying=underlying,
        options_surface=surface,
        dealer_position=None,
        config=config,
    )


def summarize_output_to_engine_output(
    output: HedgeEngineOutput,
    *,
    timestamp: float,
) -> EngineOutput:
    price_grid = np.array(output.fields.price_grid)
    gamma_field = np.array(output.fields.gamma_field)
    vanna_field = np.array(output.fields.vanna_field)
    charm_field = np.array(output.fields.charm_field)

    gamma_pressure = float(np.trapz(gamma_field, price_grid))
    vanna_pressure = float(np.trapz(vanna_field, price_grid))
    charm_pressure = float(np.trapz(charm_field, price_grid))
    max_strike_gamma = float(np.max(np.abs(gamma_field))) if gamma_field.size else 0.0

    gamma_positive = float(np.sum(gamma_field[gamma_field > 0]))
    gamma_negative = float(np.sum(np.abs(gamma_field[gamma_field < 0])))
    gamma_imbalance = 0.0
    if gamma_positive + gamma_negative > 0:
        gamma_imbalance = (gamma_positive - gamma_negative) / (gamma_positive + gamma_negative)

    features = {
        "gamma_pressure": gamma_pressure,
        "vanna_pressure": vanna_pressure,
        "charm_pressure": charm_pressure,
        "gamma_imbalance": gamma_imbalance,
        "delta_imbalance": 0.0,
        "vega_notional": output.options_surface_meta.get("total_vanna_abs", 0.0),
        "max_strike_gamma": max_strike_gamma,
    }

    metadata = {
        "tenor_count": output.options_surface_meta.get("tenor_count", 0.0),
        "effective_liquidity": output.options_surface_meta.get("effective_liquidity", 0.0),
        "elasticity": output.elasticity_summary.dict(),
        "structural": output.structural.dict(),
        "fields": output.fields.dict(),
    }

    return EngineOutput(
        kind="hedge",
        features=features,
        metadata=metadata,
        timestamp=timestamp,
        confidence=1.0,
    )


def run_hedge_engine_from_raw(
    raw: RawInputs,
    engine: HedgeEngine,
    config: HedgeEngineConfig | None = None,
) -> Tuple[HedgeEngineOutput, EngineOutput]:
    inputs = build_inputs_from_raw(raw, config=config)
    output = engine.run_bar(inputs)
    engine_output = summarize_output_to_engine_output(output, timestamp=raw.timestamp)
    return output, engine_output
