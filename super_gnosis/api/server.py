from __future__ import annotations

from fastapi import FastAPI, Depends
from pydantic import BaseModel
from typing import List

from core.schemas import (
    MarketTick,
    OptionsSnapshot,
    TechnicalFeatures,
    OrderFlowFeatures,
    ElasticityMetrics,
    MarketScenarioPacket,
    TradeIdea,
)
from engines.hedge_engine import HedgeEngine
from engines.liquidity_engine import LiquidityEngine
from engines.sentiment_engine import SentimentEngine
from engines.standardizer import StandardizerEngine
from agents.hedge_agent import HedgeAgent
from agents.liquidity_agent import LiquidityAgent
from agents.sentiment_agent import SentimentAgent
from composer.composer_agent import ComposerAgent
from trade.trade_agent import TradeAgent
from ml.registry import ModelRegistry
from .dependencies import get_model_registry


app = FastAPI(title="Super Gnosis API")


class RunBarRequest(BaseModel):
    bar: MarketTick
    options: OptionsSnapshot
    technical: TechnicalFeatures
    order_flow: OrderFlowFeatures
    elasticity: ElasticityMetrics
    max_risk_dollars: float = 100.0


class RunBarResponse(BaseModel):
    scenario: MarketScenarioPacket
    trades: List[TradeIdea]


@app.post("/run_bar", response_model=RunBarResponse)
def run_bar(
    payload: RunBarRequest,
    model_registry: ModelRegistry = Depends(get_model_registry),
) -> RunBarResponse:
    """End-to-end run: snapshot → engines → agents → composer → trade agent."""
    # Engines
    hedge_engine = HedgeEngine(model_registry)
    liq_engine = LiquidityEngine(model_registry)
    sent_engine = SentimentEngine(model_registry)
    std_engine = StandardizerEngine()

    hedge_sig = hedge_engine.run(payload.bar, payload.options)
    liq_sig = liq_engine.run(payload.bar, payload.order_flow, payload.elasticity)
    sent_sig = sent_engine.run(payload.bar, payload.technical)
    std_sig = std_engine.run(hedge_sig, liq_sig, sent_sig)
    # TODO: incorporate standardized signals into downstream agents
    _ = std_sig

    # Agents
    hedge_agent = HedgeAgent()
    liq_agent = LiquidityAgent()
    sent_agent = SentimentAgent()

    hedge_pkt = hedge_agent.run(hedge_sig)
    liq_pkt = liq_agent.run(liq_sig)
    sent_pkt = sent_agent.run(sent_sig)

    # Composer
    composer = ComposerAgent(model_registry)
    scenario = composer.run(hedge_pkt, liq_pkt, sent_pkt)

    # Trade Agent
    trade_agent = TradeAgent()
    trades = trade_agent.generate_trades(scenario, payload.max_risk_dollars)

    return RunBarResponse(scenario=scenario, trades=trades)
