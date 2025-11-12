"""
Core schemas for DHPE pipeline
Defines all data structures used across engines and agents
"""
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional, Literal
from datetime import datetime
import json
import uuid


@dataclass
class RawInputs:
    """Raw market data inputs"""
    symbol: str
    timestamp: float
    options: List[Dict[str, Any]]
    trades: List[Dict[str, Any]]
    news: List[Dict[str, Any]]
    orderbook: Optional[Dict[str, Any]] = None
    fundamentals: Optional[Dict[str, Any]] = None


@dataclass
class EngineOutput:
    """Standardized output from any engine"""
    kind: Literal["hedge", "volume", "sentiment"]
    features: Dict[str, float]
    metadata: Dict[str, Any]
    timestamp: float
    confidence: float = 1.0


@dataclass
class StandardSnapshot:
    """Unified snapshot consumed by all primary agents"""
    timestamp: float
    symbol: str
    hedge: Dict[str, float]
    volume: Dict[str, float]
    sentiment: Dict[str, float]
    regime: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Forecast:
    """Look-ahead forecast from any horizon"""
    horizon: int  # bars/minutes
    exp_return: float
    risk: float
    prob_win: float
    scenarios: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Suggestion:
    """Suggestion emitted by primary agents or composer"""
    id: str
    layer: Literal["primary_hedge", "primary_volume", "primary_sentiment", "composer"]
    symbol: str
    action: str  # 'long', 'short', 'hold', 'spread:call_debit', etc.
    params: Dict[str, Any]
    confidence: float
    forecast: Forecast
    timestamp: float
    reasoning: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d['forecast'] = asdict(self.forecast)
        return d
    
    @staticmethod
    def create(layer: str, symbol: str, action: str, params: Dict[str, Any],
               confidence: float, forecast: Forecast, reasoning: str = None) -> 'Suggestion':
        return Suggestion(
            id=str(uuid.uuid4())[:8],
            layer=layer,
            symbol=symbol,
            action=action,
            params=params,
            confidence=confidence,
            forecast=forecast,
            timestamp=datetime.now().timestamp(),
            reasoning=reasoning
        )


@dataclass
class Position:
    """Opened position (linked to suggestion)"""
    id: str  # matches suggestion id
    symbol: str
    side: Literal["long", "short", "flat"]
    size: float
    entry_price: float
    entry_time: float
    strategy_type: str  # 'directional', 'spread', 'hedge'
    legs: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Result:
    """Result of a closed position (linked to suggestion)"""
    id: str  # matches suggestion id
    exit_price: float
    exit_time: float
    pnl: float
    pnl_pct: float
    realized_horizon: int
    metrics: Dict[str, float] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ToolEvent:
    """Event from a tool call (for A2A comms)"""
    tool: str
    success: bool
    latency_ms: int
    output: Dict[str, Any]
    error: Optional[str] = None


@dataclass
class A2AMessage:
    """Agent-to-Agent communication message"""
    source_agent: str
    intent: str
    version: str
    payload: Dict[str, Any]
    tools: List[ToolEvent] = field(default_factory=list)
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())
    
    def to_json(self) -> str:
        return json.dumps(asdict(self))
    
    @staticmethod
    def from_json(data: str) -> 'A2AMessage':
        d = json.loads(data)
        d['tools'] = [ToolEvent(**t) for t in d.get('tools', [])]
        return A2AMessage(**d)


@dataclass
class MemoryItem:
    """Single memory item with decay"""
    content: str
    embedding: Optional[List[float]]
    timestamp: float
    confidence: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def age_days(self, now: float = None) -> float:
        if now is None:
            now = datetime.now().timestamp()
        return (now - self.timestamp) / 86400.0


@dataclass
class Checkpoint:
    """Orchestration checkpoint for resumable runs"""
    run_id: str
    agent_name: str
    step: int
    state: Dict[str, Any]
    timestamp: float
    
    def to_json(self) -> str:
        return json.dumps(asdict(self))
    
    @staticmethod
    def from_json(data: str) -> 'Checkpoint':
        return Checkpoint(**json.loads(data))
