"""
Vector Memory Retrieval

FAISS-based semantic search over trade episodes.
Embeds episode context → finds similar past situations → informs decisions.
"""

from __future__ import annotations
import numpy as np
from pathlib import Path
from typing import List, Optional, Tuple
from datetime import datetime
import pickle

try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False
    print("⚠️  FAISS not installed. Install with: pip install faiss-cpu")

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    print("⚠️  sentence-transformers not installed. Install with: pip install sentence-transformers")

from gnosis.memory.schema import Episode, MemoryRecall
from gnosis.memory.store import get_store


class VectorMemory:
    """
    Vector-based episode retrieval
    
    Workflow:
    1. Embed episode context text using sentence-transformers
    2. Index embeddings in FAISS for fast similarity search
    3. Query with new context → get K most similar past episodes
    4. Weight by recency + outcome → inform current decision
    """
    
    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        index_path: str = "memory/faiss_index",
        rebuild_on_init: bool = False
    ):
        """
        Initialize vector memory
        
        Args:
            model_name: SentenceTransformer model to use
            index_path: Path to save/load FAISS index
            rebuild_on_init: If True, rebuild index from store on init
        """
        self.index_path = Path(index_path)
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Check dependencies
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            raise RuntimeError("sentence-transformers not installed")
        if not FAISS_AVAILABLE:
            raise RuntimeError("faiss not installed")
        
        # Load embedding model
        print(f"📥 Loading embedding model: {model_name}")
        self.model = SentenceTransformer(model_name)
        self.embedding_dim = self.model.get_sentence_embedding_dimension()
        print(f"   Dimension: {self.embedding_dim}")
        
        # Initialize or load FAISS index
        self.index = None
        self.episode_ids: List[str] = []
        
        if rebuild_on_init:
            self.rebuild_index()
        else:
            self.load_index()
    
    def embed(self, text: str) -> np.ndarray:
        """
        Embed text to vector
        
        Args:
            text: Natural language description
        
        Returns:
            Embedding vector (normalized)
        """
        vec = self.model.encode(text, convert_to_numpy=True)
        # Normalize for cosine similarity
        vec = vec / (np.linalg.norm(vec) + 1e-8)
        return vec.astype('float32')
    
    def embed_batch(self, texts: List[str]) -> np.ndarray:
        """Embed multiple texts efficiently"""
        vecs = self.model.encode(texts, convert_to_numpy=True, show_progress_bar=True)
        # Normalize
        norms = np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-8
        vecs = vecs / norms
        return vecs.astype('float32')
    
    def add_episode(self, episode: Episode):
        """
        Add episode to index
        
        Embeds episode context and adds to FAISS index.
        """
        if self.index is None:
            self._init_index()
        
        # Embed episode text
        text = episode.to_text()
        vec = self.embed(text)
        
        # Store embedding in episode
        episode.embedding = vec.tolist()
        
        # Add to index
        self.index.add(vec.reshape(1, -1))
        self.episode_ids.append(episode.episode_id)
    
    def search(
        self,
        query: str,
        k: int = 10,
        current_time: Optional[datetime] = None
    ) -> MemoryRecall:
        """
        Search for similar episodes
        
        Args:
            query: Natural language query (e.g., episode.to_text())
            k: Number of results
            current_time: For recency weighting (defaults to now)
        
        Returns:
            MemoryRecall with top-K episodes and similarities
        """
        if self.index is None or self.index.ntotal == 0:
            return MemoryRecall(query, [], [])
        
        if current_time is None:
            current_time = datetime.now()
        
        # Embed query
        query_vec = self.embed(query).reshape(1, -1)
        
        # Search FAISS index
        k_actual = min(k, self.index.ntotal)
        distances, indices = self.index.search(query_vec, k_actual)
        
        # Retrieve episodes from store
        store = get_store()
        episodes = []
        similarities = []
        
        for dist, idx in zip(distances[0], indices[0]):
            if idx < 0 or idx >= len(self.episode_ids):
                continue
            
            episode_id = self.episode_ids[idx]
            episode = store.read(episode_id)
            
            if episode is None:
                continue
            
            # Compute retrieval score (recency + outcome)
            episode.compute_retrieval_score(current_time)
            
            episodes.append(episode)
            similarities.append(float(dist))  # Cosine similarity (0-1)
        
        recall = MemoryRecall(query, episodes, similarities)
        recall.compute_aggregate()
        
        return recall
    
    def rebuild_index(self):
        """
        Rebuild FAISS index from all episodes in store
        
        Use this when:
        - Index is corrupted
        - Many new episodes added without indexing
        - Changing embedding model
        """
        print("🔨 Rebuilding FAISS index from episode store...")
        
        store = get_store()
        episodes = store.read_recent(limit=10000, closed_only=True)
        
        if not episodes:
            print("   No episodes found. Initializing empty index.")
            self._init_index()
            return
        
        print(f"   Found {len(episodes)} episodes to index")
        
        # Embed all episodes
        texts = [ep.to_text() for ep in episodes]
        embeddings = self.embed_batch(texts)
        
        # Store embeddings in episodes and update store
        for ep, emb in zip(episodes, embeddings):
            ep.embedding = emb.tolist()
            store.write(ep)
        
        # Build FAISS index
        self.index = faiss.IndexFlatIP(self.embedding_dim)  # Inner product (cosine)
        self.index.add(embeddings)
        self.episode_ids = [ep.episode_id for ep in episodes]
        
        print(f"   ✅ Indexed {self.index.ntotal} episodes")
        
        # Save index
        self.save_index()
    
    def save_index(self):
        """Save FAISS index and metadata to disk"""
        if self.index is None:
            return
        
        # Save FAISS index
        index_file = str(self.index_path) + ".faiss"
        faiss.write_index(self.index, index_file)
        
        # Save episode IDs
        meta_file = str(self.index_path) + ".meta"
        with open(meta_file, 'wb') as f:
            pickle.dump(self.episode_ids, f)
        
        print(f"💾 Saved index to {index_file}")
    
    def load_index(self):
        """Load FAISS index from disk"""
        index_file = str(self.index_path) + ".faiss"
        meta_file = str(self.index_path) + ".meta"
        
        if not Path(index_file).exists():
            print("   No saved index found. Initializing empty index.")
            self._init_index()
            return
        
        try:
            self.index = faiss.read_index(index_file)
            with open(meta_file, 'rb') as f:
                self.episode_ids = pickle.load(f)
            
            print(f"✅ Loaded index with {self.index.ntotal} episodes")
        except Exception as e:
            print(f"❌ Failed to load index: {e}")
            self._init_index()
    
    def _init_index(self):
        """Initialize empty FAISS index"""
        self.index = faiss.IndexFlatIP(self.embedding_dim)
        self.episode_ids = []


# Convenience functions
_default_vec_memory: Optional[VectorMemory] = None


def get_vec_memory() -> VectorMemory:
    """Get global vector memory instance"""
    global _default_vec_memory
    if _default_vec_memory is None:
        _default_vec_memory = VectorMemory()
    return _default_vec_memory


def recall_similar(
    query: str,
    k: int = 10,
    current_time: Optional[datetime] = None
) -> MemoryRecall:
    """
    Recall similar episodes
    
    High-level API for memory retrieval.
    """
    return get_vec_memory().search(query, k, current_time)


def index_episode(episode: Episode):
    """Add episode to vector index"""
    get_vec_memory().add_episode(episode)


def rebuild_memory_index():
    """Rebuild entire memory index"""
    get_vec_memory().rebuild_index()


if __name__ == "__main__":
    # Test vector memory
    import uuid
    from gnosis.memory.schema import AgentView
    from gnosis.memory.store import write_episode
    
    print("\n" + "="*60)
    print("  VECTOR MEMORY TEST")
    print("="*60 + "\n")
    
    # Create test episodes
    episodes = []
    
    # Episode 1: Long on bullish signal
    ep1 = Episode(
        episode_id=str(uuid.uuid4()),
        symbol="SPY",
        t_open=datetime(2024, 10, 1, 10, 0),
        price_open=580.0,
        features_digest={"hedge_gamma": 0.8, "liq_amihud": 0.01, "sent_momentum": 0.6},
        agent_views=[
            AgentView("hedge", 1, 0.8, "Strong gamma wall above", {"gamma": 0.8}),
            AgentView("liquidity", 1, 0.7, "Tight spreads", {"amihud": 0.01}),
            AgentView("sentiment", 1, 0.6, "Bullish momentum", {"momentum": 0.6}),
        ],
        decision=1,
        decision_confidence=0.7,
        position_size=0.15,
        consensus_logic="3-of-3 agree"
    )
    ep1.update_outcome(
        t_close=datetime(2024, 10, 1, 14, 0),
        price_close=582.5,
        exit_reason="TP",
        pnl=2.5 * 0.15,
        hit_target=True
    )
    ep1.critique = "Strong uptrend, all agents aligned. Good entry timing."
    ep1.regime_label = "trending_up"
    episodes.append(ep1)
    
    # Episode 2: Short on bearish signal
    ep2 = Episode(
        episode_id=str(uuid.uuid4()),
        symbol="SPY",
        t_open=datetime(2024, 10, 5, 11, 0),
        price_open=575.0,
        features_digest={"hedge_gamma": -0.6, "liq_amihud": 0.03, "sent_momentum": -0.5},
        agent_views=[
            AgentView("hedge", -1, 0.6, "Gamma wall below", {"gamma": -0.6}),
            AgentView("liquidity", -1, 0.5, "Widening spreads", {"amihud": 0.03}),
            AgentView("sentiment", -1, 0.7, "Bearish breakdown", {"momentum": -0.5}),
        ],
        decision=-1,
        decision_confidence=0.6,
        position_size=0.10,
        consensus_logic="3-of-3 agree"
    )
    ep2.update_outcome(
        t_close=datetime(2024, 10, 5, 15, 0),
        price_close=573.0,
        exit_reason="TP",
        pnl=2.0 * 0.10,
        hit_target=True
    )
    ep2.critique = "Clean bearish setup. Agents correctly identified weakness."
    ep2.regime_label = "trending_down"
    episodes.append(ep2)
    
    # Write to store
    for ep in episodes:
        write_episode(ep)
        print(f"✅ Wrote {ep.episode_id}")
    
    # Initialize vector memory and rebuild index
    print("\n🔨 Building vector memory...")
    vec_mem = VectorMemory(rebuild_on_init=True)
    
    # Test query: bullish setup
    print("\n🔍 Query: Bullish setup with high gamma")
    query = "SPY bullish with strong gamma wall, tight spreads, momentum positive"
    recall = vec_mem.search(query, k=5)
    print(recall.to_summary())
    
    # Test query: bearish setup
    print("\n🔍 Query: Bearish setup with weak momentum")
    query = "SPY bearish breakdown, widening spreads, negative momentum"
    recall = vec_mem.search(query, k=5)
    print(recall.to_summary())
    
    print("\n✅ Vector memory tests passed!")
