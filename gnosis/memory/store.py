"""
Episode Memory Store

DuckDB + Parquet for structured episode storage.
Append-only writes with updates on exit.
"""

from __future__ import annotations
import duckdb
from pathlib import Path
from datetime import datetime
from typing import List, Optional
import json

from gnosis.memory.schema import Episode


class EpisodeStore:
    """
    Persistent storage for trade episodes
    
    Schema:
    - episodes table with JSON fields for nested data
    - Parquet backing for durability
    - Efficient queries by symbol, date, outcome
    """
    
    def __init__(self, db_path: str = "memory/episodes.duckdb"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        
        self.conn = duckdb.connect(db_path)
        self._init_schema()
    
    def _init_schema(self):
        """Create episodes table if not exists"""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS episodes (
                episode_id VARCHAR PRIMARY KEY,
                symbol VARCHAR,
                t_open TIMESTAMP,
                t_close TIMESTAMP,
                decision INTEGER,
                decision_confidence DOUBLE,
                pnl DOUBLE,
                return_pct DOUBLE,
                hit_target BOOLEAN,
                exit_reason VARCHAR,
                regime_label VARCHAR,
                data JSON,  -- Full episode as JSON
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Indexes for fast queries
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_symbol_time 
            ON episodes(symbol, t_open DESC)
        """)
        
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_outcome 
            ON episodes(pnl, hit_target) WHERE pnl IS NOT NULL
        """)
    
    def write(self, episode: Episode):
        """
        Write episode to store (insert or update)
        
        If episode_id exists, update it. Otherwise insert.
        """
        data_json = json.dumps(episode.to_dict())
        
        self.conn.execute("""
            INSERT INTO episodes (
                episode_id, symbol, t_open, t_close, decision, decision_confidence,
                pnl, return_pct, hit_target, exit_reason, regime_label, data, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT (episode_id) DO UPDATE SET
                t_close = excluded.t_close,
                pnl = excluded.pnl,
                return_pct = excluded.return_pct,
                hit_target = excluded.hit_target,
                exit_reason = excluded.exit_reason,
                regime_label = excluded.regime_label,
                data = excluded.data,
                updated_at = CURRENT_TIMESTAMP
        """, [
            episode.episode_id,
            episode.symbol,
            episode.t_open,
            episode.t_close,
            episode.decision,
            episode.decision_confidence,
            episode.pnl,
            episode.return_pct,
            episode.hit_target,
            episode.exit_reason,
            episode.regime_label,
            data_json
        ])
    
    def read(self, episode_id: str) -> Optional[Episode]:
        """Read single episode by ID"""
        result = self.conn.execute(
            "SELECT data FROM episodes WHERE episode_id = ?",
            [episode_id]
        ).fetchone()
        
        if result is None:
            return None
        
        data = json.loads(result[0])
        return Episode.from_dict(data)
    
    def read_recent(
        self,
        symbol: Optional[str] = None,
        limit: int = 100,
        closed_only: bool = True
    ) -> List[Episode]:
        """
        Read recent episodes
        
        Args:
            symbol: Filter by symbol (None = all symbols)
            limit: Max episodes to return
            closed_only: Only return closed episodes with outcomes
        
        Returns:
            List of episodes ordered by t_close DESC
        """
        query = "SELECT data FROM episodes WHERE 1=1"
        params = []
        
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)
        
        if closed_only:
            query += " AND t_close IS NOT NULL"
        
        query += " ORDER BY COALESCE(t_close, t_open) DESC LIMIT ?"
        params.append(limit)
        
        results = self.conn.execute(query, params).fetchall()
        
        episodes = []
        for row in results:
            data = json.loads(row[0])
            episodes.append(Episode.from_dict(data))
        
        return episodes
    
    def read_by_outcome(
        self,
        symbol: Optional[str] = None,
        min_pnl: Optional[float] = None,
        hit_target_only: bool = False,
        limit: int = 100
    ) -> List[Episode]:
        """
        Read episodes filtered by outcome
        
        Args:
            symbol: Filter by symbol
            min_pnl: Minimum PnL threshold
            hit_target_only: Only episodes that hit TP
            limit: Max episodes
        
        Returns:
            List of episodes ordered by PnL DESC
        """
        query = "SELECT data FROM episodes WHERE pnl IS NOT NULL"
        params = []
        
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)
        
        if min_pnl is not None:
            query += " AND pnl >= ?"
            params.append(min_pnl)
        
        if hit_target_only:
            query += " AND hit_target = TRUE"
        
        query += " ORDER BY pnl DESC LIMIT ?"
        params.append(limit)
        
        results = self.conn.execute(query, params).fetchall()
        
        episodes = []
        for row in results:
            data = json.loads(row[0])
            episodes.append(Episode.from_dict(data))
        
        return episodes
    
    def get_stats(self, symbol: Optional[str] = None) -> dict:
        """
        Get summary statistics
        
        Returns:
            Dict with total episodes, win rate, avg PnL, etc.
        """
        query = """
            SELECT 
                COUNT(*) as total,
                COUNT(CASE WHEN pnl IS NOT NULL THEN 1 END) as closed,
                COUNT(CASE WHEN pnl > 0 THEN 1 END) as winners,
                COUNT(CASE WHEN pnl < 0 THEN 1 END) as losers,
                AVG(CASE WHEN pnl IS NOT NULL THEN pnl END) as avg_pnl,
                AVG(CASE WHEN pnl IS NOT NULL THEN return_pct END) as avg_return_pct,
                COUNT(CASE WHEN hit_target = TRUE THEN 1 END) as hit_tp
            FROM episodes
        """
        
        if symbol:
            query += " WHERE symbol = ?"
            result = self.conn.execute(query, [symbol]).fetchone()
        else:
            result = self.conn.execute(query).fetchone()
        
        total, closed, winners, losers, avg_pnl, avg_return_pct, hit_tp = result
        
        win_rate = winners / closed if closed > 0 else 0.0
        tp_rate = hit_tp / closed if closed > 0 else 0.0
        
        return {
            "total_episodes": total,
            "closed_episodes": closed,
            "open_episodes": total - closed,
            "winners": winners,
            "losers": losers,
            "win_rate": win_rate,
            "tp_hit_rate": tp_rate,
            "avg_pnl": avg_pnl or 0.0,
            "avg_return_pct": avg_return_pct or 0.0
        }
    
    def export_parquet(self, output_path: str, symbol: Optional[str] = None):
        """Export episodes to Parquet file"""
        query = "COPY (SELECT * FROM episodes"
        
        if symbol:
            query += f" WHERE symbol = '{symbol}'"
        
        query += f") TO '{output_path}' (FORMAT PARQUET)"
        
        self.conn.execute(query)
        print(f"💾 Exported to {output_path}")
    
    def close(self):
        """Close database connection"""
        self.conn.close()


# Convenience functions
_default_store: Optional[EpisodeStore] = None


def get_store() -> EpisodeStore:
    """Get global episode store instance"""
    global _default_store
    if _default_store is None:
        _default_store = EpisodeStore()
    return _default_store


def write_episode(episode: Episode):
    """Write episode to default store"""
    get_store().write(episode)


def read_episode(episode_id: str) -> Optional[Episode]:
    """Read episode from default store"""
    return get_store().read(episode_id)


def get_recent_episodes(
    symbol: Optional[str] = None,
    limit: int = 100,
    closed_only: bool = True
) -> List[Episode]:
    """Get recent episodes from default store"""
    return get_store().read_recent(symbol, limit, closed_only)


def get_memory_stats(symbol: Optional[str] = None) -> dict:
    """Get stats from default store"""
    return get_store().get_stats(symbol)


if __name__ == "__main__":
    # Test store
    import uuid
    from gnosis.memory.schema import AgentView
    
    store = EpisodeStore("memory/test_episodes.duckdb")
    
    # Create test episode
    ep = Episode(
        episode_id=str(uuid.uuid4()),
        symbol="SPY",
        t_open=datetime.now(),
        price_open=580.0,
        features_digest={"hedge_gamma": 0.5, "liq_amihud": 0.02},
        agent_views=[
            AgentView("hedge", 1, 0.7, "Gamma wall detected", {"gamma": 0.5}),
            AgentView("liquidity", 1, 0.6, "High volume", {"amihud": 0.02}),
        ],
        decision=1,
        decision_confidence=0.65,
        position_size=0.1,
        consensus_logic="2-of-3 agree"
    )
    
    store.write(ep)
    print(f"✅ Wrote episode {ep.episode_id}")
    
    # Read back
    ep2 = store.read(ep.episode_id)
    assert ep2 is not None
    print(f"✅ Read episode back: {ep2.symbol} at {ep2.t_open}")
    
    # Get stats
    stats = store.get_stats()
    print(f"📊 Stats: {stats}")
    
    print("\n✅ Store tests passed!")
