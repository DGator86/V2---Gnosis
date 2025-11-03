"""
Episodic Memory System for Trading Agents

Stores trade episodes with outcomes, embeds them for semantic search,
and recalls similar past contexts to inform future decisions.

Key Components:
- Episode: Trade episode schema with context, decision, and outcome
- EpisodeStore: DuckDB storage for structured data
- VectorMemory: FAISS-based semantic search
- ReflectionEngine: Auto-generate critiques and lessons
- MemoryAugmentedComposer: Decision hook that uses memory

Usage:
    from gnosis.memory import Episode, write_episode, recall_similar
    from gnosis.memory import augment_with_memory
    
    # Store episode
    ep = Episode(...)
    write_episode(ep)
    
    # Recall similar
    recall = recall_similar("SPY bullish setup", k=10)
    
    # Augment decision
    decision, conf, size, ctx = augment_with_memory(
        symbol, features, agent_views, base_decision, base_conf, base_size
    )
"""

from gnosis.memory.schema import Episode, AgentView, MemoryRecall
from gnosis.memory.store import (
    EpisodeStore,
    write_episode,
    read_episode,
    get_recent_episodes,
    get_memory_stats
)
from gnosis.memory.reflect import reflect_on_episode, ReflectionEngine
from gnosis.memory.composer_hook import (
    MemoryAugmentedComposer,
    augment_with_memory
)

# Vector memory (optional, requires faiss + sentence-transformers)
try:
    from gnosis.memory.vec import (
        VectorMemory,
        recall_similar,
        index_episode,
        rebuild_memory_index
    )
    VECTOR_MEMORY_AVAILABLE = True
except ImportError:
    VECTOR_MEMORY_AVAILABLE = False
    
    # Provide stub functions
    def recall_similar(*args, **kwargs):
        raise RuntimeError("Vector memory not available. Install: pip install faiss-cpu sentence-transformers")
    
    def index_episode(*args, **kwargs):
        raise RuntimeError("Vector memory not available. Install: pip install faiss-cpu sentence-transformers")
    
    def rebuild_memory_index(*args, **kwargs):
        raise RuntimeError("Vector memory not available. Install: pip install faiss-cpu sentence-transformers")


__all__ = [
    # Schema
    "Episode",
    "AgentView",
    "MemoryRecall",
    
    # Store
    "EpisodeStore",
    "write_episode",
    "read_episode",
    "get_recent_episodes",
    "get_memory_stats",
    
    # Reflection
    "reflect_on_episode",
    "ReflectionEngine",
    
    # Composer integration
    "MemoryAugmentedComposer",
    "augment_with_memory",
    
    # Vector memory (if available)
    "VectorMemory",
    "recall_similar",
    "index_episode",
    "rebuild_memory_index",
    "VECTOR_MEMORY_AVAILABLE",
]
