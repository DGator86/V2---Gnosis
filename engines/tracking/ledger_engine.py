"""
Ledger/Tracking engine
Tracks suggestions → positions → results with full lineage
Implements JSONL-based audit trail
"""
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime
from schemas import Suggestion, Position, Result
from ..orchestration.logger import get_logger

logger = get_logger(__name__)


class LedgerEngine:
    """
    Engine for tracking trading lifecycle
    SUGGESTION -> POSITION -> RESULT with full lineage
    """
    
    def __init__(self, ledger_path: str = "data/ledger.jsonl"):
        self.ledger_path = Path(ledger_path)
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        
        # In-memory caches
        self.suggestions: Dict[str, Suggestion] = {}
        self.positions: Dict[str, Position] = {}
        self.results: Dict[str, Result] = {}
        
        logger.info(f"Ledger engine initialized: {self.ledger_path}")
    
    def _write_entry(self, entry_type: str, data: Dict[str, Any]):
        """Write entry to JSONL ledger"""
        import json
        
        with open(self.ledger_path, 'a') as f:
            entry = {
                "type": entry_type,
                "timestamp": datetime.now().timestamp(),
                "data": data
            }
            f.write(json.dumps(entry) + '\n')
    
    def log_suggestion(self, suggestion: Suggestion):
        """Log a suggestion"""
        self.suggestions[suggestion.id] = suggestion
        self._write_entry("SUGGESTION", suggestion.to_dict())
        
        logger.info(f"Logged suggestion: {suggestion.id} | {suggestion.layer} | {suggestion.action}")
    
    def log_position(self, position: Position):
        """Log an opened position"""
        self.positions[position.id] = position
        self._write_entry("POSITION", position.to_dict())
        
        logger.info(f"Logged position: {position.id} | {position.side} | size={position.size}")
    
    def log_result(self, result: Result):
        """Log a closed position result"""
        self.results[result.id] = result
        self._write_entry("RESULT", result.to_dict())
        
        logger.info(f"Logged result: {result.id} | pnl={result.pnl:.2f} | pnl_pct={result.pnl_pct:.2%}")
    
    def get_suggestion(self, suggestion_id: str) -> Optional[Suggestion]:
        """Retrieve suggestion by ID"""
        return self.suggestions.get(suggestion_id)
    
    def get_position(self, position_id: str) -> Optional[Position]:
        """Retrieve position by ID"""
        return self.positions.get(position_id)
    
    def get_result(self, result_id: str) -> Optional[Result]:
        """Retrieve result by ID"""
        return self.results.get(result_id)
    
    def get_lineage(self, id: str) -> Dict[str, Any]:
        """Get full lineage for an ID (suggestion -> position -> result)"""
        return {
            "suggestion": self.get_suggestion(id),
            "position": self.get_position(id),
            "result": self.get_result(id)
        }
    
    def get_metrics(self, 
                   layer: str = None,
                   symbol: str = None,
                   lookback_hours: float = None) -> Dict[str, Any]:
        """
        Calculate performance metrics
        
        Args:
            layer: Filter by agent layer
            symbol: Filter by symbol
            lookback_hours: Only include recent results
        
        Returns:
            Dict with hit_rate, avg_pnl, sharpe, etc.
        """
        filtered_results = list(self.results.values())
        
        # Apply filters
        if lookback_hours:
            cutoff = datetime.now().timestamp() - (lookback_hours * 3600)
            filtered_results = [r for r in filtered_results if r.exit_time >= cutoff]
        
        if symbol:
            # Need to look up suggestions to filter by symbol
            filtered_results = [
                r for r in filtered_results
                if self.suggestions.get(r.id) and self.suggestions[r.id].symbol == symbol
            ]
        
        if layer:
            filtered_results = [
                r for r in filtered_results
                if self.suggestions.get(r.id) and self.suggestions[r.id].layer == layer
            ]
        
        if not filtered_results:
            return {
                "count": 0,
                "hit_rate": 0.0,
                "avg_pnl": 0.0,
                "total_pnl": 0.0,
                "sharpe": 0.0
            }
        
        # Calculate metrics
        count = len(filtered_results)
        wins = sum(1 for r in filtered_results if r.pnl > 0)
        hit_rate = wins / count
        
        pnls = [r.pnl for r in filtered_results]
        avg_pnl = sum(pnls) / count
        total_pnl = sum(pnls)
        
        # Sharpe approximation
        if len(pnls) > 1:
            import math
            pnl_std = math.sqrt(sum((p - avg_pnl) ** 2 for p in pnls) / (count - 1))
            sharpe = (avg_pnl / pnl_std) * math.sqrt(252) if pnl_std > 0 else 0.0
        else:
            sharpe = 0.0
        
        return {
            "count": count,
            "hit_rate": hit_rate,
            "avg_pnl": avg_pnl,
            "total_pnl": total_pnl,
            "sharpe": sharpe,
            "best_pnl": max(pnls),
            "worst_pnl": min(pnls)
        }
