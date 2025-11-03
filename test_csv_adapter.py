#!/usr/bin/env python3
from gnosis.ingest.adapters.csv_prices import stream_csv
from gnosis.ingest.transform.l0_to_l1thin import transform_record

# Test the CSV adapter
for i, raw in enumerate(stream_csv("sample_vendor_data.csv")):
    l1 = transform_record(raw, raw_ref=f"file://sample_vendor_data.csv:row_{i}")
    print(f"Row {i}: {l1.symbol} @ {l1.t_event} - Price: ${l1.price}, IV: {l1.iv_dec:.3f}")