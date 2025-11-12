"""
Decay memory engine with time-based forgetting
Implements persistent memory with confidence decay and self-evaluation
Based on Marktechpost Agentic AI Memory patterns
"""
import math
from typing import List, Optional, Dict, Any
from datetime import datetime
from schemas import MemoryItem
from ..orchestration.logger import get_logger

logger = get_logger(__name__)


class DecayMemoryEngine:
    """
    Memory engine with exponential decay
    Items lose relevance over time based on half-life
    """
    
    def __init__(self, 
                 half_life_days: float = 7.0,
                 max_items: int = 5000,
                 min_confidence: float = 0.0):
        """
        Args:
            half_life_days: Days for memory weight to decay to 50%
            max_items: Maximum number of items to retain
            min_confidence: Minimum confidence to keep items
        """
        self.half_life_days = half_life_days
        self.max_items = max_items
        self.min_confidence = min_confidence
        self.items: List[MemoryItem] = []
        
        logger.info(f"Decay memory engine initialized: half_life={half_life_days}d, "
                   f"max_items={max_items}, min_conf={min_confidence}")
    
    def _decay_weight(self, item: MemoryItem, now: Optional[float] = None) -> float:
        """
        Calculate decay weight using exponential decay formula
        weight = confidence * 2^(-age / half_life)
        """
        if now is None:
            now = datetime.now().timestamp()
        
        age_days = item.age_days(now)
        decay_factor = math.pow(2, -age_days / self.half_life_days)
        weight = item.confidence * decay_factor
        
        return weight
    
    def add(self, item: MemoryItem):
        """Add item to memory"""
        # Check if we should add this item
        if item.confidence < self.min_confidence:
            logger.debug(f"Skipping low-confidence item: {item.confidence:.2f}")
            return
        
        self.items.append(item)
        
        # Prune if over capacity
        if len(self.items) > self.max_items:
            self._prune()
    
    def _prune(self):
        """Remove lowest-weighted items to stay under max_items"""
        now = datetime.now().timestamp()
        
        # Calculate weights for all items
        weighted_items = [(self._decay_weight(item, now), item) for item in self.items]
        
        # Sort by weight descending
        weighted_items.sort(key=lambda x: x[0], reverse=True)
        
        # Keep only top max_items
        self.items = [item for _, item in weighted_items[:self.max_items]]
        
        removed = len(weighted_items) - len(self.items)
        if removed > 0:
            logger.debug(f"Pruned {removed} low-weight items")
    
    def topk(self, k: int = 10, now: Optional[float] = None) -> List[MemoryItem]:
        """Get top-k items by current weight"""
        if now is None:
            now = datetime.now().timestamp()
        
        weighted_items = [(self._decay_weight(item, now), item) for item in self.items]
        weighted_items.sort(key=lambda x: x[0], reverse=True)
        
        return [item for _, item in weighted_items[:k]]
    
    def query(self, 
              min_weight: float = 0.0,
              content_filter: Optional[str] = None,
              metadata_filter: Optional[Dict[str, Any]] = None,
              limit: int = 100) -> List[MemoryItem]:
        """
        Query memory with filters
        
        Args:
            min_weight: Minimum weight threshold
            content_filter: String that must appear in content
            metadata_filter: Dict of metadata key-value pairs to match
            limit: Maximum results to return
        """
        now = datetime.now().timestamp()
        results = []
        
        for item in self.items:
            weight = self._decay_weight(item, now)
            
            # Weight filter
            if weight < min_weight:
                continue
            
            # Content filter
            if content_filter and content_filter.lower() not in item.content.lower():
                continue
            
            # Metadata filter
            if metadata_filter:
                match = all(
                    item.metadata.get(k) == v 
                    for k, v in metadata_filter.items()
                )
                if not match:
                    continue
            
            results.append((weight, item))
        
        # Sort by weight and limit
        results.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in results[:limit]]
    
    def self_evaluate(self) -> Dict[str, Any]:
        """
        Self-evaluation of memory quality
        Returns metrics about memory state
        """
        if not self.items:
            return {
                "total_items": 0,
                "avg_weight": 0.0,
                "avg_age_days": 0.0,
                "avg_confidence": 0.0
            }
        
        now = datetime.now().timestamp()
        weights = [self._decay_weight(item, now) for item in self.items]
        ages = [item.age_days(now) for item in self.items]
        confidences = [item.confidence for item in self.items]
        
        return {
            "total_items": len(self.items),
            "avg_weight": sum(weights) / len(weights),
            "avg_age_days": sum(ages) / len(ages),
            "avg_confidence": sum(confidences) / len(confidences),
            "min_weight": min(weights),
            "max_weight": max(weights),
        }
    
    def clear_old(self, max_age_days: float):
        """Remove items older than max_age_days"""
        now = datetime.now().timestamp()
        original_count = len(self.items)
        
        self.items = [
            item for item in self.items 
            if item.age_days(now) <= max_age_days
        ]
        
        removed = original_count - len(self.items)
        if removed > 0:
            logger.info(f"Cleared {removed} items older than {max_age_days} days")
