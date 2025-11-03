from fastapi import FastAPI, Body
from datetime import datetime
from typing import List, Dict, Any
import threading

# In-memory idea log (use Redis/DB in production)
IDEA_LOG: List[Dict[str, Any]] = []
IDEA_LOG_LOCK = threading.Lock()
from gnosis.schemas.base import L3Canonical
from gnosis.feature_store.store import FeatureStore
from gnosis.engines.hedge_v0 import compute_hedge_v0
from gnosis.engines.liquidity_v0 import compute_liquidity_v0
from gnosis.engines.sentiment_v0 import compute_sentiment_v0
from gnosis.agents.agents_v1 import agent1_hedge, agent2_liquidity, agent3_sentiment, compose
import numpy as np
import pandas as pd
from gnosis.ingest.transform.l0_to_l1thin import transform_record
from gnosis.ingest.transform.l1_store import L1Store

app = FastAPI(title="Agentic Trading Orchestrator", version="0.1.0")
fs = FeatureStore(root="data")
l1_store = L1Store(root="data_l1")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/run_bar/{symbol}")
def run_bar(symbol: str, price: float, bar: str, volume: float = None):
    t = datetime.fromisoformat(bar)
    
    # Build pseudo window for liquidity engine (in production pull recent L1)
    # Generate realistic market data around the current price
    np.random.seed(int(t.timestamp()) % 1000)  # reproducible randomness
    df = pd.DataFrame({
        "t_event": pd.date_range(end=t, periods=60, freq="1min"),
        "price": price + np.cumsum(np.random.randn(60) * 0.05),  # random walk
        "volume": np.random.randint(1000, 5000, 60) if volume is None else 
                  np.random.normal(volume, volume * 0.2, 60)
    })
    df["price"] = df["price"].clip(lower=price * 0.99, upper=price * 1.01)  # constrain range
    
    # Generate fake options chain (in production, pull from vendor)
    chain = pd.DataFrame({
        "strike": np.linspace(price*0.9, price*1.1, 40),
        "expiry": pd.Timestamp(t + pd.Timedelta(days=7)),
        "iv": np.random.uniform(0.15, 0.25, 40),
        "delta": np.linspace(-0.9, 0.9, 40),  # More realistic delta profile
        "gamma": np.abs(np.random.normal(1e-5, 2e-6, 40)),
        "vega": np.random.uniform(0.01, 0.05, 40),
        "theta": -np.abs(np.random.uniform(0.01, 0.03, 40)),  # Theta always negative
        "open_interest": np.random.randint(50, 500, 40)
    })
    # Add concentration around ATM strikes (more realistic)
    atm_mask = (chain["strike"] > price * 0.98) & (chain["strike"] < price * 1.02)
    chain.loc[atm_mask, "open_interest"] *= 3
    chain.loc[atm_mask, "gamma"] *= 2
    
    # Create sentiment DataFrame with realistic price action
    df_sent = pd.DataFrame({
        "t_event": pd.date_range(end=t, periods=60, freq="1min"),
        "price": price + np.cumsum(np.random.randn(60) * 0.1),  # Random walk for momentum
        "volume": np.random.randint(1000, 5000, 60) if volume is None else
                  np.random.normal(volume or 3000, 500, 60)
    })
    
    hedge = compute_hedge_v0(symbol, t, price, chain)
    liq = compute_liquidity_v0(symbol, t, df)
    sent = compute_sentiment_v0(symbol, t, df_sent, news_bias=0.0)

    row = L3Canonical(symbol=symbol, bar=t, hedge=hedge, liquidity=liq, sentiment=sent)
    fs.write(row)

    # Build agent views
    v1 = agent1_hedge(symbol, t, hedge.present.model_dump(), hedge.future.model_dump())
    v2 = agent2_liquidity(symbol, t, liq.present.model_dump(), liq.future.model_dump(), price)
    v3 = agent3_sentiment(symbol, t, sent.present.model_dump(), sent.future.model_dump())

    # Compose final trade idea
    idea = compose(
        symbol, t, [v1, v2, v3],
        amihud=float(liq.present.amihud),
        reliability={"hedge": 1.0, "liquidity": 1.0, "sentiment": 1.0}  # Will be learned from backtests later
    )
    
    return {"l3": row.model_dump(), "idea": idea}

@app.get("/features/{symbol}")
def features(symbol: str, bar: str, feature_set_id: str = "v0.1.0"):
    try:
        t = datetime.fromisoformat(bar)
        return fs.read_pit(symbol, t, feature_set_id)
    except FileNotFoundError as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/ideas/log")
def log_idea(idea: Dict[str, Any] = Body(...)):
    """Log an idea for later review/analysis"""
    with IDEA_LOG_LOCK:
        IDEA_LOG.append(idea)
        return {"logged": True, "count": len(IDEA_LOG)}

@app.get("/ideas/log")
def list_ideas(limit: int = 100):
    """Retrieve logged ideas (most recent first)"""
    with IDEA_LOG_LOCK:
        return {
            "count": len(IDEA_LOG), 
            "ideas": list(reversed(IDEA_LOG[-limit:]))
        }

@app.post("/ingest/l1thin")
def ingest_l1(raw_rows: List[Dict[str, Any]] = Body(...)):
    """
    Accepts a list of vendor rows (L0-ish) and returns L1Thin rows (time/symbol/units normalized).
    """
    out = []
    for i, raw in enumerate(raw_rows):
        raw_ref = raw.get("_raw_ref", f"memory://post/{i}")  # in real use: s3://... or file://...
        l1 = transform_record(raw, raw_ref=raw_ref, source=raw.get("_source", "api.post"))
        out.append(l1.model_dump())
    # optional persistence
    l1_objs = []
    for i, raw in enumerate(raw_rows):
        raw_ref = raw.get("_raw_ref", f"memory://post/{i}")
        l1_objs.append(transform_record(raw, raw_ref=raw_ref, source=raw.get("_source", "api.post")))
    if l1_objs:
        l1_store.write_many(l1_objs)
    return {"count": len(out), "rows": out}