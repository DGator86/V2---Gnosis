"""
Lookahead Transformer for Price Movement Prediction

Tiny 4-layer Transformer that predicts price changes from hedge snapshots.
Trains in background thread, adds prediction as vote to Composer Agent.

Author: Super Gnosis AI Developer
Created: 2025-11-19
"""

from __future__ import annotations
import numpy as np
import torch
import torch.nn as nn
from typing import Dict, List, Tuple, Optional
from collections import deque
import threading
import time

try:
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    print("⚠️  PyTorch not available, lookahead model disabled")


class TransformerPredictor(nn.Module):
    """
    Tiny Transformer for sequence prediction.
    
    Input: Sequence of hedge snapshots (flattened numeric features)
    Output: Predicted price change % in next 15 minutes
    """
    
    def __init__(
        self,
        input_dim: int = 10,
        hidden_dim: int = 64,
        num_layers: int = 4,
        num_heads: int = 4,
        dropout: float = 0.1
    ):
        super().__init__()
        
        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        
        # Input projection
        self.input_proj = nn.Linear(input_dim, hidden_dim)
        
        # Transformer encoder
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=hidden_dim,
            nhead=num_heads,
            dim_feedforward=hidden_dim * 2,
            dropout=dropout,
            batch_first=True
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        
        # Output head (regression)
        self.output_head = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim // 2, 1)
        )
    
    def forward(self, x):
        """
        Forward pass.
        
        Args:
            x: Input tensor of shape (batch, sequence_length, input_dim)
        
        Returns:
            Predicted price change % (batch, 1)
        """
        # Project input
        x = self.input_proj(x)  # (batch, seq_len, hidden_dim)
        
        # Transformer encoding
        x = self.transformer(x)  # (batch, seq_len, hidden_dim)
        
        # Take last timestep
        x = x[:, -1, :]  # (batch, hidden_dim)
        
        # Predict
        out = self.output_head(x)  # (batch, 1)
        
        return out


class LookaheadTransformer:
    """
    Lookahead model manager with background training.
    
    Trains on historical ledger data to predict price movements.
    Runs training in separate thread to avoid blocking main loop.
    """
    
    def __init__(
        self,
        sequence_length: int = 20,
        hidden_dim: int = 64,
        num_layers: int = 4,
        num_heads: int = 4,
        train_every_minutes: int = 10,
        prediction_weight: float = 0.3
    ):
        """
        Initialize lookahead model.
        
        Args:
            sequence_length: Number of past hedge snapshots to use
            hidden_dim: Transformer hidden dimension
            num_layers: Number of Transformer layers
            num_heads: Number of attention heads
            train_every_minutes: Background training interval
            prediction_weight: Weight in Composer vote
        """
        if not TORCH_AVAILABLE:
            self.enabled = False
            return
        
        self.enabled = True
        self.sequence_length = sequence_length
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers
        self.num_heads = num_heads
        self.train_every_minutes = train_every_minutes
        self.prediction_weight = prediction_weight
        
        # Feature dimension (hedge snapshot features)
        self.input_dim = 10  # elasticity, energy, asymmetry, gamma, pressure, etc.
        
        # Model
        self.model = TransformerPredictor(
            input_dim=self.input_dim,
            hidden_dim=hidden_dim,
            num_layers=num_layers,
            num_heads=num_heads
        )
        
        # Optimizer
        self.optimizer = torch.optim.Adam(self.model.parameters(), lr=0.001)
        self.criterion = nn.MSELoss()
        
        # Training data buffer
        self.sequence_buffer: deque = deque(maxlen=1000)  # Sequences
        self.target_buffer: deque = deque(maxlen=1000)  # Price changes
        
        # Model trained flag
        self.is_trained = False
        
        # Training metrics
        self.train_loss = 0.0
        self.mae = 0.0
        self.direction_accuracy = 0.0
        self.predictions_count = 0
        
        # Background training thread
        self.training_thread = None
        self.stop_training = False
    
    def add_sequence(
        self,
        hedge_snapshots: List[Dict[str, float]],
        price_change_pct: float
    ):
        """
        Add a training sequence.
        
        Args:
            hedge_snapshots: List of hedge snapshots (oldest to newest)
            price_change_pct: Actual price change % in next 15 minutes
        """
        if not self.enabled or len(hedge_snapshots) < self.sequence_length:
            return
        
        # Take last sequence_length snapshots
        recent_snapshots = hedge_snapshots[-self.sequence_length:]
        
        # Extract features from each snapshot
        features = [self._extract_features(snap) for snap in recent_snapshots]
        
        # Add to buffer
        self.sequence_buffer.append(features)
        self.target_buffer.append(price_change_pct)
    
    def _extract_features(self, hedge_snapshot: Dict[str, float]) -> np.ndarray:
        """
        Extract feature vector from hedge snapshot.
        
        Args:
            hedge_snapshot: Hedge Engine state
        
        Returns:
            Feature array
        """
        features = [
            hedge_snapshot.get('elasticity', 1.0),
            hedge_snapshot.get('movement_energy', 0.0),
            hedge_snapshot.get('movement_energy_up', 0.0),
            hedge_snapshot.get('movement_energy_down', 0.0),
            hedge_snapshot.get('energy_asymmetry', 0.0),
            hedge_snapshot.get('dealer_gamma_sign', 0.0),
            hedge_snapshot.get('pressure_up', 0.0),
            hedge_snapshot.get('pressure_down', 0.0),
            hedge_snapshot.get('net_pressure', 0.0),
            hedge_snapshot.get('gamma_pressure', 0.0)
        ]
        
        return np.array(features, dtype=np.float32)
    
    def train_model(self, epochs: int = 10, batch_size: int = 32):
        """
        Train model on buffered data.
        
        Args:
            epochs: Number of training epochs
            batch_size: Batch size
        """
        if not self.enabled or len(self.sequence_buffer) < batch_size:
            return
        
        try:
            # Prepare data
            X = np.array(list(self.sequence_buffer))  # (N, seq_len, input_dim)
            y = np.array(list(self.target_buffer))  # (N,)
            
            # Convert to tensors
            X_tensor = torch.FloatTensor(X)
            y_tensor = torch.FloatTensor(y).unsqueeze(1)
            
            # Training loop
            self.model.train()
            total_loss = 0.0
            
            for epoch in range(epochs):
                # Shuffle data
                indices = torch.randperm(len(X_tensor))
                X_shuffled = X_tensor[indices]
                y_shuffled = y_tensor[indices]
                
                epoch_loss = 0.0
                num_batches = 0
                
                # Mini-batch training
                for i in range(0, len(X_shuffled), batch_size):
                    batch_X = X_shuffled[i:i+batch_size]
                    batch_y = y_shuffled[i:i+batch_size]
                    
                    # Forward pass
                    self.optimizer.zero_grad()
                    predictions = self.model(batch_X)
                    loss = self.criterion(predictions, batch_y)
                    
                    # Backward pass
                    loss.backward()
                    self.optimizer.step()
                    
                    epoch_loss += loss.item()
                    num_batches += 1
                
                total_loss = epoch_loss / max(1, num_batches)
            
            self.train_loss = total_loss
            self.is_trained = True
            
            # Compute validation metrics
            self._compute_metrics(X_tensor, y_tensor)
            
        except Exception as e:
            print(f"⚠️  Lookahead training error: {e}")
    
    def _compute_metrics(self, X: torch.Tensor, y: torch.Tensor):
        """
        Compute validation metrics.
        
        Args:
            X: Input tensor
            y: Target tensor
        """
        self.model.eval()
        with torch.no_grad():
            predictions = self.model(X)
            
            # MAE
            mae = torch.abs(predictions - y).mean().item()
            self.mae = mae
            
            # Direction accuracy
            pred_direction = (predictions > 0).float()
            true_direction = (y > 0).float()
            direction_acc = (pred_direction == true_direction).float().mean().item()
            self.direction_accuracy = direction_acc * 100.0
    
    def predict(
        self,
        hedge_snapshots: List[Dict[str, float]]
    ) -> Optional[float]:
        """
        Predict price change % for next 15 minutes.
        
        Args:
            hedge_snapshots: List of recent hedge snapshots
        
        Returns:
            Predicted price change % or None if not ready
        """
        if not self.enabled or not self.is_trained or len(hedge_snapshots) < self.sequence_length:
            return None
        
        try:
            # Take last sequence_length snapshots
            recent_snapshots = hedge_snapshots[-self.sequence_length:]
            
            # Extract features
            features = [self._extract_features(snap) for snap in recent_snapshots]
            
            # Convert to tensor
            X = torch.FloatTensor([features])  # (1, seq_len, input_dim)
            
            # Predict
            self.model.eval()
            with torch.no_grad():
                prediction = self.model(X)
            
            self.predictions_count += 1
            
            return float(prediction[0, 0].item())
            
        except Exception as e:
            print(f"⚠️  Lookahead prediction error: {e}")
            return None
    
    def start_background_training(self):
        """
        Start background training thread.
        """
        if not self.enabled or self.training_thread is not None:
            return
        
        def training_loop():
            while not self.stop_training:
                time.sleep(self.train_every_minutes * 60)
                if len(self.sequence_buffer) >= 32:
                    self.train_model(epochs=5, batch_size=32)
        
        self.training_thread = threading.Thread(target=training_loop, daemon=True)
        self.training_thread.start()
    
    def stop_background_training(self):
        """Stop background training thread"""
        self.stop_training = True
        if self.training_thread:
            self.training_thread.join(timeout=5)
    
    def get_stats(self) -> Dict:
        """
        Get model statistics for dashboard.
        
        Returns:
            Dict with stats
        """
        return {
            'is_trained': self.is_trained,
            'train_loss': self.train_loss,
            'mae': self.mae,
            'direction_accuracy': self.direction_accuracy,
            'predictions_count': self.predictions_count,
            'sequences': len(self.sequence_buffer),
            'weight': self.prediction_weight
        }
    
    def to_dict(self) -> Dict:
        """
        Serialize state (model weights not serialized for simplicity).
        
        Returns:
            Dict with state
        """
        if not self.enabled:
            return {'enabled': False}
        
        return {
            'enabled': True,
            'sequence_length': self.sequence_length,
            'hidden_dim': self.hidden_dim,
            'num_layers': self.num_layers,
            'num_heads': self.num_heads,
            'train_every_minutes': self.train_every_minutes,
            'prediction_weight': self.prediction_weight,
            'is_trained': self.is_trained,
            'train_loss': self.train_loss,
            'mae': self.mae,
            'direction_accuracy': self.direction_accuracy,
            'predictions_count': self.predictions_count
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'LookaheadTransformer':
        """
        Deserialize from persistence.
        
        Args:
            data: Dict with state
        
        Returns:
            Restored LookaheadTransformer instance
        """
        if not data.get('enabled', False) or not TORCH_AVAILABLE:
            instance = cls()
            instance.enabled = False
            return instance
        
        instance = cls(
            sequence_length=data.get('sequence_length', 20),
            hidden_dim=data.get('hidden_dim', 64),
            num_layers=data.get('num_layers', 4),
            num_heads=data.get('num_heads', 4),
            train_every_minutes=data.get('train_every_minutes', 10),
            prediction_weight=data.get('prediction_weight', 0.3)
        )
        
        # Restore metrics
        instance.is_trained = data.get('is_trained', False)
        instance.train_loss = data.get('train_loss', 0.0)
        instance.mae = data.get('mae', 0.0)
        instance.direction_accuracy = data.get('direction_accuracy', 0.0)
        instance.predictions_count = data.get('predictions_count', 0)
        
        # Note: Model weights not restored (would need torch.save/load)
        # Model will retrain from ledger data on startup
        
        return instance
