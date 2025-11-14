"""
Agent-to-Agent (A2A) communication engine
Standardized messaging protocol for inter-agent communication
Based on Marktechpost Agent Communication Protocol patterns
"""
from typing import Dict, Any, List
from datetime import datetime
from schemas import A2AMessage, ToolEvent
from ..orchestration.logger import get_logger

logger = get_logger(__name__)


class A2AEngine:
    """Engine for agent-to-agent communication"""
    
    PROTOCOL_VERSION = "1.0"
    
    def __init__(self):
        self.message_history: List[A2AMessage] = []
        logger.info("A2A communication engine initialized")
    
    def create_message(self,
                      source_agent: str,
                      intent: str,
                      payload: Dict[str, Any],
                      tools: List[ToolEvent] = None) -> A2AMessage:
        """
        Create standardized A2A message
        
        Args:
            source_agent: Name of sending agent
            intent: Intent/purpose of message (e.g., 'hedge_snapshot', 'request_data')
            payload: Message data
            tools: List of tool events that generated this data
        """
        message = A2AMessage(
            source_agent=source_agent,
            intent=intent,
            version=self.PROTOCOL_VERSION,
            payload=payload,
            tools=tools or [],
            timestamp=datetime.now()
        )
        
        self.message_history.append(message)
        logger.debug(f"Created A2A message: {source_agent} -> {intent}")
        
        return message
    
    def hedge_snapshot(self, 
                      source_agent: str,
                      features: Dict[str, float],
                      tools: List[ToolEvent] = None) -> A2AMessage:
        """Create standardized hedge snapshot message"""
        return self.create_message(
            source_agent=source_agent,
            intent="hedge_snapshot",
            payload={
                "type": "hedge",
                "features": features,
                "timestamp": datetime.now().isoformat()
            },
            tools=tools
        )
    
    def volume_snapshot(self,
                       source_agent: str,
                       features: Dict[str, float],
                       tools: List[ToolEvent] = None) -> A2AMessage:
        """Create standardized volume snapshot message"""
        return self.create_message(
            source_agent=source_agent,
            intent="volume_snapshot",
            payload={
                "type": "volume",
                "features": features,
                "timestamp": datetime.now().isoformat()
            },
            tools=tools
        )
    
    def sentiment_snapshot(self,
                          source_agent: str,
                          features: Dict[str, float],
                          tools: List[ToolEvent] = None) -> A2AMessage:
        """Create standardized sentiment snapshot message"""
        return self.create_message(
            source_agent=source_agent,
            intent="sentiment_snapshot",
            payload={
                "type": "sentiment",
                "features": features,
                "timestamp": datetime.now().isoformat()
            },
            tools=tools
        )
    
    def request_data(self,
                    source_agent: str,
                    request_type: str,
                    params: Dict[str, Any]) -> A2AMessage:
        """Create data request message"""
        return self.create_message(
            source_agent=source_agent,
            intent="request_data",
            payload={
                "request_type": request_type,
                "params": params
            }
        )
    
    def response_data(self,
                     source_agent: str,
                     request_id: str,
                     data: Dict[str, Any]) -> A2AMessage:
        """Create data response message"""
        return self.create_message(
            source_agent=source_agent,
            intent="response_data",
            payload={
                "request_id": request_id,
                "data": data
            }
        )
    
    def error_message(self,
                     source_agent: str,
                     error_type: str,
                     error_msg: str,
                     context: Dict[str, Any] = None) -> A2AMessage:
        """Create error message"""
        return self.create_message(
            source_agent=source_agent,
            intent="error",
            payload={
                "error_type": error_type,
                "error_msg": error_msg,
                "context": context or {}
            }
        )
    
    def get_history(self,
                   source_agent: str = None,
                   intent: str = None,
                   limit: int = 100) -> List[A2AMessage]:
        """
        Get message history with optional filters
        
        Args:
            source_agent: Filter by source agent
            intent: Filter by intent
            limit: Maximum messages to return
        """
        filtered = self.message_history
        
        if source_agent:
            filtered = [m for m in filtered if m.source_agent == source_agent]
        
        if intent:
            filtered = [m for m in filtered if m.intent == intent]
        
        # Return most recent first
        return list(reversed(filtered[-limit:]))
    
    def clear_history(self, before_timestamp: float = None):
        """Clear message history, optionally before a timestamp"""
        if before_timestamp is None:
            self.message_history.clear()
            logger.info("Cleared all A2A message history")
        else:
            original_len = len(self.message_history)
            self.message_history = [
                m for m in self.message_history 
                if m.timestamp >= before_timestamp
            ]
            removed = original_len - len(self.message_history)
            logger.info(f"Cleared {removed} A2A messages before timestamp {before_timestamp}")
