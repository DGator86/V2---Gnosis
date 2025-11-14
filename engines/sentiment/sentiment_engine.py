"""
Sentiment engine
Analyzes news, social media, and filings for market sentiment
Uses decay memory for time-weighted relevance
"""
from typing import Dict, Any, List
from datetime import datetime
from schemas import EngineOutput, MemoryItem
from ..memory.decay_memory_engine import DecayMemoryEngine
from ..orchestration.logger import get_logger

logger = get_logger(__name__)


class SentimentEngine:
    """
    Engine for sentiment analysis
    Processes news, social, filings with decay memory
    """
    
    def __init__(self, 
                 decay_half_life_days: float = 7.0,
                 max_memory_items: int = 5000,
                 min_confidence: float = 0.3):
        self.memory = DecayMemoryEngine(
            half_life_days=decay_half_life_days,
            max_items=max_memory_items,
            min_confidence=min_confidence
        )
        logger.info(f"Sentiment engine initialized (decay_half_life={decay_half_life_days}d)")
    
    def _process_news_item(self, item: Dict[str, Any]) -> MemoryItem:
        """Convert news item to memory item"""
        return MemoryItem(
            content=item.get("title", ""),
            embedding=None,  # TODO: Add embedding generation
            timestamp=item.get("timestamp", datetime.now()),
            confidence=item.get("confidence", 0.5),
            metadata={
                "source": item.get("source", "unknown"),
                "sentiment_score": item.get("sentiment_score", 0.0),
                "url": item.get("url", "")
            }
        )
    
    def _aggregate_sentiment(self, items: List[MemoryItem]) -> Dict[str, float]:
        """Aggregate sentiment from weighted items"""
        if not items:
            return {
                "sentiment_score": 0.0,
                "sentiment_magnitude": 0.0,
                "sentiment_consistency": 0.0
            }
        
        # Compute weighted average sentiment
        total_weight = 0.0
        weighted_sentiment = 0.0
        
        now = datetime.now()

        for item in items:
            weight = self.memory._decay_weight(item, now)
            sentiment = item.metadata.get("sentiment_score", 0.0)
            
            weighted_sentiment += sentiment * weight
            total_weight += weight
        
        avg_sentiment = weighted_sentiment / total_weight if total_weight > 0 else 0.0
        
        # Compute magnitude (how strong the signals are)
        sentiments = [item.metadata.get("sentiment_score", 0.0) for item in items]
        magnitude = sum(abs(s) for s in sentiments) / len(sentiments) if sentiments else 0.0
        
        # Compute consistency (how aligned the signals are)
        if len(sentiments) > 1:
            positive_count = sum(1 for s in sentiments if s > 0)
            negative_count = sum(1 for s in sentiments if s < 0)
            total_count = len(sentiments)
            
            consistency = max(positive_count, negative_count) / total_count
        else:
            consistency = 1.0 if sentiments else 0.0
        
        return {
            "sentiment_score": avg_sentiment,
            "sentiment_magnitude": magnitude,
            "sentiment_consistency": consistency
        }
    
    def _detect_catalysts(self, items: List[MemoryItem]) -> List[Dict[str, Any]]:
        """Detect high-impact news catalysts"""
        catalysts = []
        
        for item in items:
            sentiment = item.metadata.get("sentiment_score", 0.0)
            
            # High-magnitude sentiment = potential catalyst
            if abs(sentiment) > 0.5 and item.confidence > 0.7:
                catalysts.append({
                    "content": item.content,
                    "sentiment": sentiment,
                    "confidence": item.confidence,
                    "age_hours": item.age_days() * 24,
                    "source": item.metadata.get("source", "unknown")
                })
        
        # Sort by recency and magnitude
        catalysts.sort(key=lambda x: (x["age_hours"], -abs(x["sentiment"])))
        
        return catalysts[:5]  # Top 5
    
    def run(self, news: List[Dict[str, Any]]) -> EngineOutput:
        """
        Main entry point: compute sentiment features from news
        
        Args:
            news: List of news dicts with titles, scores, timestamps
        
        Returns:
            EngineOutput with sentiment features
        """
        start_time = datetime.now()
        
        # Add news to memory
        for item in news:
            memory_item = self._process_news_item(item)
            self.memory.add(memory_item)
        
        # Get recent weighted items
        recent_items = self.memory.topk(k=50)
        
        # Aggregate sentiment
        sentiment_features = self._aggregate_sentiment(recent_items)
        
        # Detect catalysts
        catalysts = self._detect_catalysts(recent_items)
        
        # Memory health
        memory_stats = self.memory.self_evaluate()
        
        features = {
            **sentiment_features,
            "num_recent_items": len(recent_items),
            "num_catalysts": len(catalysts),
            "memory_avg_weight": memory_stats.get("avg_weight", 0.0),
            "memory_total_items": memory_stats.get("total_items", 0)
        }
        
        latency_ms = (datetime.now() - start_time).total_seconds() * 1000
        
        logger.debug(f"Sentiment engine computed {len(features)} features in {latency_ms:.2f}ms")
        
        return EngineOutput(
            kind="sentiment",
            features=features,
            metadata={
                "n_news_items": len(news),
                "catalysts": catalysts,
                "memory_stats": memory_stats,
                "latency_ms": latency_ms
            },
            timestamp=datetime.now(),
            confidence=sentiment_features["sentiment_consistency"]
        )
