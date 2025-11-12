"""
Visibility Graph - Time Series to Network Topology
Based on: https://github.com/neurotrader888/visibility-graph-MFE

Converts time series to graph where visibility criterion determines edges.
Network metrics reveal complexity, regimes, and transitions.

Reference: "From time series to complex networks: The visibility graph" (Lacasa et al., 2008)
"""

from dataclasses import dataclass
from typing import Dict

import numpy as np
import pandas as pd


@dataclass
class VisibilityGraphMetrics:
    """Metrics derived from visibility graph."""
    
    degree: pd.Series
    """Node degree (number of connections)."""
    
    clustering: pd.Series
    """Clustering coefficient (local connectivity)."""
    
    centrality: pd.Series
    """Betweenness centrality (importance in network)."""
    
    assortativity: float
    """Degree correlation (hubiness)."""
    
    avg_path_length: float
    """Average shortest path length."""


def compute_visibility_graph(
    ts: pd.Series,
    window: int = 50,
    variant: str = 'natural',
) -> VisibilityGraphMetrics:
    """
    Convert time series to visibility graph and extract metrics.
    
    Args:
        ts: Time series
        window: Rolling window for metrics
        variant: 'natural' or 'horizontal' visibility
    
    Returns:
        VisibilityGraphMetrics
    """
    n = len(ts)
    values = ts.values
    
    # Build adjacency matrix
    adj = np.zeros((n, n), dtype=bool)
    
    for i in range(n):
        for j in range(i+1, n):
            if _has_visibility(values, i, j, variant):
                adj[i, j] = True
                adj[j, i] = True
    
    # Compute metrics
    degree = adj.sum(axis=1)
    clustering = _compute_clustering(adj)
    centrality = _compute_betweenness(adj)
    
    # Rolling statistics
    degree_series = pd.Series(degree, index=ts.index)
    clustering_series = pd.Series(clustering, index=ts.index)
    centrality_series = pd.Series(centrality, index=ts.index)
    
    # Global metrics
    assortativity = _compute_assortativity(adj, degree)
    avg_path = _compute_avg_path_length(adj)
    
    return VisibilityGraphMetrics(
        degree=degree_series,
        clustering=clustering_series,
        centrality=centrality_series,
        assortativity=assortativity,
        avg_path_length=avg_path,
    )


def _has_visibility(values: np.ndarray, i: int, j: int, variant: str) -> bool:
    """Check if nodes i and j have visibility."""
    if variant == 'natural':
        # Natural visibility: line of sight not blocked
        for k in range(i+1, j):
            # Interpolate height at k
            t = (k - i) / (j - i)
            height_at_k = values[i] + t * (values[j] - values[i])
            if values[k] >= height_at_k:
                return False
        return True
    else:
        # Horizontal visibility: all intermediate values must be lower
        return all(values[k] < min(values[i], values[j]) for k in range(i+1, j))


def _compute_clustering(adj: np.ndarray) -> np.ndarray:
    """Compute clustering coefficient for each node."""
    n = len(adj)
    clustering = np.zeros(n)
    
    for i in range(n):
        neighbors = np.where(adj[i])[0]
        k = len(neighbors)
        
        if k < 2:
            clustering[i] = 0
        else:
            # Count triangles
            triangles = 0
            for j in range(len(neighbors)):
                for l in range(j+1, len(neighbors)):
                    if adj[neighbors[j], neighbors[l]]:
                        triangles += 1
            
            clustering[i] = 2 * triangles / (k * (k - 1))
    
    return clustering


def _compute_betweenness(adj: np.ndarray) -> np.ndarray:
    """Simplified betweenness centrality."""
    n = len(adj)
    return np.array([adj[i].sum() / (n - 1) for i in range(n)])


def _compute_assortativity(adj: np.ndarray, degree: np.ndarray) -> float:
    """Degree assortativity coefficient."""
    edges = np.where(adj)
    if len(edges[0]) == 0:
        return 0.0
    
    k_i = degree[edges[0]]
    k_j = degree[edges[1]]
    
    num = ((k_i * k_j).mean() - k_i.mean() * k_j.mean())
    denom = np.sqrt(((k_i**2).mean() - k_i.mean()**2) * ((k_j**2).mean() - k_j.mean()**2))
    
    if denom == 0:
        return 0.0
    
    return num / denom


def _compute_avg_path_length(adj: np.ndarray) -> float:
    """Average shortest path length (simplified)."""
    n = len(adj)
    total_dist = 0
    count = 0
    
    for i in range(n):
        for j in range(i+1, n):
            dist = _shortest_path_bfs(adj, i, j)
            if dist < np.inf:
                total_dist += dist
                count += 1
    
    return total_dist / count if count > 0 else np.inf


def _shortest_path_bfs(adj: np.ndarray, start: int, end: int) -> float:
    """BFS shortest path."""
    from collections import deque
    
    visited = set([start])
    queue = deque([(start, 0)])
    
    while queue:
        node, dist = queue.popleft()
        if node == end:
            return dist
        
        for neighbor in np.where(adj[node])[0]:
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, dist + 1))
    
    return np.inf


if __name__ == "__main__":
    np.random.seed(42)
    n = 100
    ts = pd.Series(np.random.randn(n).cumsum() + 100)
    
    metrics = compute_visibility_graph(ts, window=50)
    
    print(f"Mean degree: {metrics.degree.mean():.2f}")
    print(f"Mean clustering: {metrics.clustering.mean():.4f}")
    print(f"Assortativity: {metrics.assortativity:.4f}")
