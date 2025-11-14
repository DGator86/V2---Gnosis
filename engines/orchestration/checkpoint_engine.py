"""
Checkpoint engine for deterministic, resumable agent runs
Implements LangGraph-style checkpointing with time-travel capability
"""
import json
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from schemas import Checkpoint
from .logger import get_logger

logger = get_logger(__name__)


class CheckpointEngine:
    """Engine for managing agent execution checkpoints"""
    
    def __init__(self, checkpoint_dir: str = "logs/checkpoints"):
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Checkpoint engine initialized: {self.checkpoint_dir}")
    
    def save(self, checkpoint: Checkpoint) -> Path:
        """Save a checkpoint to disk"""
        filename = f"{checkpoint.run_id}_{checkpoint.agent_name}_step{checkpoint.step:04d}.json"
        filepath = self.checkpoint_dir / filename
        
        with open(filepath, 'w') as f:
            f.write(checkpoint.to_json())
        
        logger.debug(f"Saved checkpoint: {filepath}")
        return filepath
    
    def load(self, run_id: str, agent_name: str, step: Optional[int] = None) -> Optional[Checkpoint]:
        """
        Load a checkpoint from disk
        If step is None, loads the latest checkpoint
        """
        if step is None:
            # Find latest checkpoint
            checkpoints = self.list_checkpoints(run_id, agent_name)
            if not checkpoints:
                return None
            filepath = checkpoints[-1]
        else:
            filename = f"{run_id}_{agent_name}_step{step:04d}.json"
            filepath = self.checkpoint_dir / filename
            if not filepath.exists():
                return None
        
        with open(filepath, 'r') as f:
            data = f.read()
        
        checkpoint = Checkpoint.from_json(data)
        logger.debug(f"Loaded checkpoint: {filepath}")
        return checkpoint
    
    def list_checkpoints(self, run_id: str, agent_name: str) -> List[Path]:
        """List all checkpoints for a given run and agent"""
        pattern = f"{run_id}_{agent_name}_step*.json"
        checkpoints = sorted(self.checkpoint_dir.glob(pattern))
        return checkpoints
    
    def latest(self, run_id: str, agent_name: str) -> Optional[Checkpoint]:
        """Get the latest checkpoint for a run/agent"""
        return self.load(run_id, agent_name, step=None)
    
    def time_travel(self, run_id: str, agent_name: str, step: int) -> Optional[Checkpoint]:
        """
        Time-travel to a specific step
        Returns the checkpoint at that step
        """
        logger.info(f"Time-traveling to {run_id}/{agent_name}/step{step}")
        return self.load(run_id, agent_name, step)
    
    def replay_from(self, run_id: str, agent_name: str, from_step: int) -> List[Checkpoint]:
        """
        Replay checkpoints from a specific step onwards
        Returns list of checkpoints
        """
        checkpoints = self.list_checkpoints(run_id, agent_name)
        replay_checkpoints = []
        
        for cp_path in checkpoints:
            with open(cp_path, 'r') as f:
                cp = Checkpoint.from_json(f.read())
            
            if cp.step >= from_step:
                replay_checkpoints.append(cp)
        
        logger.info(f"Replaying {len(replay_checkpoints)} checkpoints from step {from_step}")
        return replay_checkpoints
    
    def cleanup_old(self, max_age_hours: int = 24):
        """Remove checkpoints older than max_age_hours"""
        cutoff = datetime.now() - timedelta(hours=max_age_hours)
        removed_count = 0
        
        for cp_path in self.checkpoint_dir.glob("*.json"):
            with open(cp_path, 'r') as f:
                cp = Checkpoint.from_json(f.read())
            
            if cp.timestamp < cutoff:
                cp_path.unlink()
                removed_count += 1
        
        if removed_count > 0:
            logger.info(f"Cleaned up {removed_count} old checkpoints")
    
    def get_run_history(self, run_id: str) -> Dict[str, List[Checkpoint]]:
        """Get complete history of a run across all agents"""
        history = {}
        
        for cp_path in self.checkpoint_dir.glob(f"{run_id}_*.json"):
            with open(cp_path, 'r') as f:
                cp = Checkpoint.from_json(f.read())
            
            if cp.agent_name not in history:
                history[cp.agent_name] = []
            
            history[cp.agent_name].append(cp)
        
        # Sort each agent's checkpoints by step
        for agent_name in history:
            history[agent_name].sort(key=lambda x: x.step)
        
        return history
