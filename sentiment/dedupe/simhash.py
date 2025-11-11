"""SimHash implementation for near-duplicate detection."""

from __future__ import annotations
from typing import Iterable, List, Optional
import hashlib
import logging
from collections import deque

logger = logging.getLogger(__name__)


def _tokenize(text: str) -> Iterable[str]:
    """Tokenize text into normalized words."""
    for word in text.lower().split():
        # Remove non-alphanumeric characters
        clean = ''.join(ch for ch in word if ch.isalnum())
        if clean:
            yield clean


def simhash_64(text: str) -> int:
    """Compute 64-bit SimHash of text.
    
    Args:
        text: Input text
        
    Returns:
        64-bit hash value
    """
    if not text:
        return 0
    
    # Initialize bit vector
    v = [0] * 64
    
    for token in _tokenize(text):
        # Get hash of token
        h = int(hashlib.blake2b(token.encode(), digest_size=8).hexdigest(), 16)
        
        # Update bit vector
        for i in range(64):
            bit = (h >> i) & 1
            if bit:
                v[i] += 1
            else:
                v[i] -= 1
    
    # Generate final hash
    result = 0
    for i in range(64):
        if v[i] > 0:
            result |= (1 << i)
    
    return result


def hamming(a: int, b: int) -> int:
    """Calculate Hamming distance between two hashes.
    
    Args:
        a: First hash
        b: Second hash
        
    Returns:
        Number of differing bits
    """
    return (a ^ b).bit_count()


class NoveltyIndex:
    """Index for tracking novel (non-duplicate) content."""
    
    def __init__(
        self,
        threshold_bits: int = 6,
        max_size: int = 10000,
        use_sliding_window: bool = True
    ):
        """Initialize novelty index.
        
        Args:
            threshold_bits: Maximum Hamming distance for duplicates
            max_size: Maximum number of hashes to store
            use_sliding_window: Whether to use sliding window (FIFO)
        """
        self.threshold = threshold_bits
        self.max_size = max_size
        self.use_sliding_window = use_sliding_window
        
        if use_sliding_window:
            self._seen = deque(maxlen=max_size)
        else:
            self._seen: List[int] = []
        
        self.stats = {
            "total_checked": 0,
            "novel_count": 0,
            "duplicate_count": 0,
        }
    
    def is_novel(self, hash_value: int) -> bool:
        """Check if a hash represents novel content.
        
        Args:
            hash_value: Hash to check
            
        Returns:
            True if novel (not a duplicate)
        """
        self.stats["total_checked"] += 1
        
        # Check against existing hashes
        for existing in self._seen:
            if hamming(hash_value, existing) <= self.threshold:
                self.stats["duplicate_count"] += 1
                return False
        
        self.stats["novel_count"] += 1
        return True
    
    def mark_and_is_novel(self, hash_value: int) -> bool:
        """Check novelty and mark hash as seen.
        
        Args:
            hash_value: Hash to check and store
            
        Returns:
            True if novel (not a duplicate)
        """
        is_novel = self.is_novel(hash_value)
        
        if is_novel:
            if self.use_sliding_window:
                self._seen.append(hash_value)
            else:
                self._seen.append(hash_value)
                # Trim if exceeded max size
                if len(self._seen) > self.max_size:
                    self._seen = self._seen[-self.max_size:]
        
        return is_novel
    
    def mark_seen(self, hash_value: int):
        """Mark a hash as seen without checking novelty.
        
        Args:
            hash_value: Hash to store
        """
        if self.use_sliding_window:
            self._seen.append(hash_value)
        else:
            self._seen.append(hash_value)
            if len(self._seen) > self.max_size:
                self._seen = self._seen[-self.max_size:]
    
    def get_novelty_rate(self) -> float:
        """Get the proportion of novel items.
        
        Returns:
            Novelty rate (0-1)
        """
        total = self.stats["total_checked"]
        if total == 0:
            return 1.0
        return self.stats["novel_count"] / total
    
    def clear(self):
        """Clear the index."""
        if self.use_sliding_window:
            self._seen.clear()
        else:
            self._seen = []
        
        self.stats = {
            "total_checked": 0,
            "novel_count": 0,
            "duplicate_count": 0,
        }