"""FinBERT model wrapper for financial sentiment analysis."""

from __future__ import annotations
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch
from typing import Dict, List, Optional
import logging
from functools import lru_cache

logger = logging.getLogger(__name__)


class FinBERT:
    """Wrapper for FinBERT sentiment analysis model."""
    
    def __init__(
        self,
        model_id: str = "ProsusAI/finbert",
        device: Optional[str] = None,
        cache_dir: Optional[str] = None,
        batch_size: int = 16
    ):
        """Initialize FinBERT model.
        
        Args:
            model_id: HuggingFace model identifier
            device: Device to run model on ('cuda', 'cpu', or None for auto)
            cache_dir: Directory to cache model files
            batch_size: Batch size for inference
        """
        self.model_id = model_id
        self.batch_size = batch_size
        
        # Load tokenizer and model
        logger.info(f"Loading FinBERT model: {model_id}")
        self.tokenizer = AutoTokenizer.from_pretrained(
            model_id,
            cache_dir=cache_dir
        )
        self.model = AutoModelForSequenceClassification.from_pretrained(
            model_id,
            cache_dir=cache_dir
        )
        
        # Set device
        if device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device
        
        self.model.to(self.device)
        self.model.eval()
        logger.info(f"Model loaded on device: {self.device}")
    
    @torch.no_grad()
    def score(self, text: str, max_length: int = 512) -> Dict[str, float]:
        """Score a single text for sentiment.
        
        Args:
            text: Text to analyze
            max_length: Maximum sequence length
            
        Returns:
            Dictionary with sentiment probabilities and signed score
        """
        if not text or not text.strip():
            return {
                "neg": 0.33,
                "neu": 0.34,
                "pos": 0.33,
                "signed": 0.0,
            }
        
        # Tokenize
        encoded = self.tokenizer(
            text,
            truncation=True,
            max_length=max_length,
            return_tensors="pt",
            padding=True
        ).to(self.device)
        
        # Get predictions
        outputs = self.model(**encoded)
        logits = outputs.logits
        probs = torch.softmax(logits, dim=-1)[0]
        
        # FinBERT label order: [negative, neutral, positive]
        return {
            "neg": float(probs[0]),
            "neu": float(probs[1]),
            "pos": float(probs[2]),
            "signed": float(probs[2] - probs[0]),  # pos - neg
        }
    
    @torch.no_grad()
    def score_batch(
        self,
        texts: List[str],
        max_length: int = 512
    ) -> List[Dict[str, float]]:
        """Score multiple texts for sentiment.
        
        Args:
            texts: List of texts to analyze
            max_length: Maximum sequence length
            
        Returns:
            List of sentiment dictionaries
        """
        if not texts:
            return []
        
        results = []
        
        # Process in batches
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            
            # Filter empty texts
            valid_texts = [(j, t) for j, t in enumerate(batch) if t and t.strip()]
            
            if not valid_texts:
                # All texts in batch are empty
                results.extend([{
                    "neg": 0.33,
                    "neu": 0.34,
                    "pos": 0.33,
                    "signed": 0.0,
                } for _ in batch])
                continue
            
            # Tokenize batch
            indices, batch_texts = zip(*valid_texts)
            encoded = self.tokenizer(
                list(batch_texts),
                truncation=True,
                max_length=max_length,
                return_tensors="pt",
                padding=True
            ).to(self.device)
            
            # Get predictions
            outputs = self.model(**encoded)
            logits = outputs.logits
            probs = torch.softmax(logits, dim=-1)
            
            # Build results maintaining original order
            batch_results = [None] * len(batch)
            for idx, prob in zip(indices, probs):
                batch_results[idx] = {
                    "neg": float(prob[0]),
                    "neu": float(prob[1]),
                    "pos": float(prob[2]),
                    "signed": float(prob[2] - prob[0]),
                }
            
            # Fill in empty text results
            for j, result in enumerate(batch_results):
                if result is None:
                    batch_results[j] = {
                        "neg": 0.33,
                        "neu": 0.34,
                        "pos": 0.33,
                        "signed": 0.0,
                    }
            
            results.extend(batch_results)
        
        return results
    
    @lru_cache(maxsize=1024)
    def score_cached(self, text: str) -> Dict[str, float]:
        """Cached version of score for repeated texts."""
        return self.score(text)