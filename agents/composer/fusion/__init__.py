"""
Composer Agent - Fusion Module

Handles field fusion, confidence aggregation, and directional resolution.
"""

from .confidence_fusion import fuse_confidence
from .direction_fusion import fuse_direction

__all__ = ["fuse_confidence", "fuse_direction"]
