"""
Trading Memory Store

Persistent memory system optimized for trading agents.
Features exponential decay, hybrid search, and outcome tracking.
"""

import time
from typing import List, Dict, Optional
from dataclasses import dataclass, field


@dataclass
class TradingMemoryItem:
    """
    Memory item for trading context
    
    Attributes:
        kind: Memory type ('trade', 'signal', 'regime', 'outcome', 'pattern')
        content: Description of event
        score: Importance weight (1.0 = normal, 2.0 = critical)
        symbol: Ticker symbol
        timestamp: Unix timestamp (auto-set)
        metadata: Additional context dict
    """
    kind: str
    content: str
    score: float
    symbol: str
    timestamp: float = field(default_factory=time.time)
    metadata: Dict = field(default_factory=dict)


class TradingMemoryStore:
    """
    Memory store with exponential decay and hybrid search
    
    Key Features:
    - Exponential decay: Recent memories weighted higher
    - Hybrid search: Combines importance + similarity + recency
    - Category filtering: Search by kind, symbol
    - Auto-cleanup: Remove stale memories
    
    Based on: Marktechpost Agentic AI Memory tutorial
    """
    
    def __init__(self, decay_half_life: float = 3600):
        """
        Initialize memory store
        
        Args:
            decay_half_life: Half-life for exponential decay in seconds
                            Default 3600 = 1 hour
                            30-60 min for intraday
                            4-8 hours for daily strategies
        """
        self.items: List[TradingMemoryItem] = []
        self.decay_half_life = decay_half_life
        
    def _decay_factor(self, item: TradingMemoryItem) -> float:
        """
        Calculate exponential decay factor
        
        Returns value in [0, 1] where:
        - 1.0 = just created
        - 0.5 = one half-life old
        - 0.25 = two half-lives old
        - etc.
        """
        dt = time.time() - item.timestamp
        return 0.5 ** (dt / self.decay_half_life)
    
    def add(self, kind: str, content: str, score: float = 1.0, 
            symbol: str = "SPY", metadata: Optional[Dict] = None) -> TradingMemoryItem:
        """
        Add new memory item
        
        Args:
            kind: Memory category
            content: Description/details
            score: Importance weight
            symbol: Ticker symbol
            metadata: Additional context
            
        Returns:
            Created TradingMemoryItem
        """
        item = TradingMemoryItem(
            kind=kind,
            content=content,
            score=score,
            symbol=symbol,
            metadata=metadata or {}
        )
        self.items.append(item)
        return item
    
    def search(self, query: str = "", kind: Optional[str] = None, 
               symbol: Optional[str] = None, topk: int = 5) -> List[TradingMemoryItem]:
        """
        Search memories with filtering and ranking
        
        Scoring formula:
        final_score = (importance * decay_factor) + text_similarity
        
        Args:
            query: Text to search for (optional)
            kind: Filter by memory type
            symbol: Filter by ticker
            topk: Number of results to return
            
        Returns:
            List of most relevant memories (sorted by score)
        """
        scored = []
        
        for item in self.items:
            # Apply filters
            if kind and item.kind != kind:
                continue
            if symbol and item.symbol != symbol:
                continue
                
            # Calculate relevance score
            decay = self._decay_factor(item)
            
            # Text similarity (simple word overlap)
            if query:
                query_words = set(query.lower().split())
                content_words = set(item.content.lower().split())
                sim = len(query_words & content_words) * 0.5  # Weight similarity lower
            else:
                sim = 0
            
            # Combined score: importance * decay + similarity
            final_score = (item.score * decay) + sim
            scored.append((final_score, item))
        
        # Sort by score descending and return top-k
        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for score, item in scored[:topk] if score > 0]
    
    def get_recent(self, kind: Optional[str] = None, 
                   symbol: Optional[str] = None, n: int = 10) -> List[TradingMemoryItem]:
        """
        Get N most recent memories (ignoring decay/scoring)
        
        Args:
            kind: Filter by memory type
            symbol: Filter by ticker
            n: Number of results
            
        Returns:
            List of recent memories (sorted by timestamp descending)
        """
        filtered = [
            item for item in self.items
            if (kind is None or item.kind == kind) and
               (symbol is None or item.symbol == symbol)
        ]
        return sorted(filtered, key=lambda x: x.timestamp, reverse=True)[:n]
    
    def cleanup(self, min_score: float = 0.1) -> int:
        """
        Remove stale memories below threshold
        
        Effective score = base_score * decay_factor
        
        Args:
            min_score: Minimum effective score to keep
            
        Returns:
            Number of memories removed
        """
        new_items = []
        for item in self.items:
            effective_score = item.score * self._decay_factor(item)
            if effective_score > min_score:
                new_items.append(item)
        
        removed = len(self.items) - len(new_items)
        self.items = new_items
        return removed
    
    def summarize(self, symbol: str = "SPY", lookback_hours: int = 24) -> Dict:
        """
        Generate summary statistics
        
        Args:
            symbol: Ticker to summarize
            lookback_hours: Time window for recent stats
            
        Returns:
            Dict with counts, averages, and breakdowns
        """
        cutoff = time.time() - (lookback_hours * 3600)
        recent = [
            item for item in self.items 
            if item.timestamp > cutoff and item.symbol == symbol
        ]
        
        summary = {
            "total_memories": len(self.items),
            "recent_count": len(recent),
            "lookback_hours": lookback_hours,
            "by_kind": {},
            "avg_score": 0.0,
            "oldest": None,
            "newest": None
        }
        
        if self.items:
            summary["oldest"] = min(item.timestamp for item in self.items)
            summary["newest"] = max(item.timestamp for item in self.items)
        
        if recent:
            summary["avg_score"] = sum(item.score for item in recent) / len(recent)
            
            # Count by kind
            for item in recent:
                summary["by_kind"][item.kind] = summary["by_kind"].get(item.kind, 0) + 1
        
        return summary
    
    def clear(self, symbol: Optional[str] = None) -> int:
        """
        Clear all memories (optionally for specific symbol)
        
        Args:
            symbol: If provided, only clear this symbol's memories
            
        Returns:
            Number of memories removed
        """
        if symbol:
            before = len(self.items)
            self.items = [item for item in self.items if item.symbol != symbol]
            return before - len(self.items)
        else:
            count = len(self.items)
            self.items = []
            return count
    
    def __len__(self) -> int:
        """Return number of stored memories"""
        return len(self.items)
    
    def __repr__(self) -> str:
        return f"TradingMemoryStore(items={len(self.items)}, half_life={self.decay_half_life}s)"
