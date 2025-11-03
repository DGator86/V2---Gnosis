from __future__ import annotations
from datetime import datetime, timezone
from dateutil import tz
from typing import Dict, Any, Optional
from pydantic import ValidationError
from ..config import SYMBOL_MAP, VENDOR_TIMEZONE, DEFAULT_SOURCE
from ...schemas.base import L1Thin

_TZ_VENDOR = tz.gettz(VENDOR_TIMEZONE)

def _canon_symbol(sym: str) -> str:
    s = sym.strip().upper()
    return SYMBOL_MAP.get(s, s)

def _to_utc(dt_like: str | datetime) -> datetime:
    if isinstance(dt_like, str):
        # accept "2025-11-03T09:31:00" (vendor local) or with tz
        try:
            t = datetime.fromisoformat(dt_like)
        except ValueError:
            raise ValueError(f"Bad datetime string: {dt_like}")
    else:
        t = dt_like
    # if naive, assume vendor local; else trust tz
    if t.tzinfo is None:
        t = t.replace(tzinfo=_TZ_VENDOR)
    return t.astimezone(timezone.utc).replace(tzinfo=None)  # store naive UTC

def _iv_to_decimal(iv_any: Optional[float]) -> Optional[float]:
    if iv_any is None:
        return None
    # if a vendor sends "18.5" meaning 18.5%, convert to 0.185
    return iv_any / 100.0 if iv_any > 1.0 else float(iv_any)

def transform_record(raw: Dict[str, Any], raw_ref: str, source: str = DEFAULT_SOURCE) -> L1Thin:
    """
    raw: vendor dict like {"symbol": "SPY.P", "t": "2025-11-03T09:31:00", "price": 451.62, "iv": 18.7, "oi": 12345}
    raw_ref: pointer to L0 storage (path/hash). Keep it immutable.
    """
    symbol = _canon_symbol(raw.get("symbol", ""))
    if not symbol:
        raise ValueError("Missing symbol")

    t_event = _to_utc(raw.get("t") or raw.get("timestamp") or raw.get("time"))
    price = float(raw["price"]) if raw.get("price") is not None else None
    volume = float(raw["volume"]) if raw.get("volume") is not None else None
    dollar_volume = float(raw["dollar_volume"]) if raw.get("dollar_volume") is not None else None
    # If we have dollar_volume but not volume, compute it
    if dollar_volume and not volume and price:
        volume = dollar_volume / price
    # If we have volume but not dollar_volume, compute it
    if volume and not dollar_volume and price:
        dollar_volume = volume * price
    iv_dec = _iv_to_decimal(raw.get("iv"))
    oi = int(raw["oi"]) if raw.get("oi") is not None else None

    try:
        l1 = L1Thin(
            symbol=symbol,
            t_event=t_event,
            source=source,
            units_normalized=True,
            price=price,
            volume=volume,
            dollar_volume=dollar_volume,
            iv_dec=iv_dec,
            oi=oi,
            raw_ref=raw_ref
        )
    except ValidationError as e:
        raise ValueError(f"L1Thin validation error: {e}") from e
    return l1