from gnosis.ingest.transform.l0_to_l1thin import transform_record
from datetime import datetime

def test_iv_normalization_and_tz():
    raw = {"symbol":"SPY.P","t":"2025-11-03T09:31:00","price":451.62,"iv":18.7,"oi":12345}
    out = transform_record(raw, raw_ref="mem://1")
    assert out.symbol == "SPY"
    assert 0.186 < out.iv_dec < 0.188
    # 09:31 ET → 14:31 UTC stored as naive (UTC)
    assert out.t_event == datetime(2025,11,3,14,31,0)

def test_already_normalized_iv():
    raw = {"symbol":"SPY","t":"2025-11-03T09:31:00","price":451.62,"iv":0.187,"oi":12345}
    out = transform_record(raw, raw_ref="mem://2")
    assert out.iv_dec == 0.187  # already in decimal form

def test_timezone_aware_input():
    raw = {"symbol":"SPY","timestamp":"2025-11-03T09:32:00-04:00","price":451.70,"iv":0.187,"oi":12360}
    out = transform_record(raw, raw_ref="mem://3")
    # 09:32 ET (with explicit -04:00) → 13:32 UTC
    assert out.t_event == datetime(2025,11,3,13,32,0)

def test_symbol_mapping():
    raw = {"symbol":"SPDR-S&P500","t":"2025-11-03T09:31:00","price":451.62}
    out = transform_record(raw, raw_ref="mem://4")
    assert out.symbol == "SPY"  # mapped via SYMBOL_MAP