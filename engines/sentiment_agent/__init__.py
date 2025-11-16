"""
Sentiment Agent v1.0 - Pure Interpreter

Canonical implementation of the Sentiment Agent as a pure interpreter
of Sentiment Engine outputs.
"""

from .agent import SentimentAgent
from .schemas import SentimentAgentInput, SentimentAgentOutput

__all__ = ["SentimentAgent", "SentimentAgentInput", "SentimentAgentOutput"]
