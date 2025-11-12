"""
Performance Monitoring and Profiling for Production Engine
Tracks computation time, memory usage, and feature performance.
"""

import time
import logging
import psutil
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import deque, defaultdict
import json

import numpy as np
import pandas as pd


logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Container for performance metrics."""
    
    timestamp: datetime
    operation: str
    duration_ms: float
    memory_mb: float
    cpu_percent: float
    success: bool
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class PerformanceMonitor:
    """
    Monitors and tracks performance metrics for production system.
    
    Features:
    - Real-time metric tracking
    - Rolling statistics
    - Alerting on thresholds
    - Performance reports
    """
    
    def __init__(
        self,
        max_history: int = 10000,
        alert_thresholds: Optional[Dict[str, float]] = None,
    ):
        """
        Initialize performance monitor.
        
        Args:
            max_history: Maximum number of metrics to store
            alert_thresholds: Dict of {metric: threshold} for alerts
        """
        self.metrics_history = deque(maxlen=max_history)
        self.operation_stats = defaultdict(lambda: {
            'count': 0,
            'total_time': 0.0,
            'errors': 0,
        })
        
        self.alert_thresholds = alert_thresholds or {
            'duration_ms': 1000.0,  # 1 second
            'memory_mb': 500.0,     # 500 MB
            'cpu_percent': 80.0,    # 80%
        }
        
        self.process = psutil.Process()
        self.start_time = time.time()
        
        logger.info("PerformanceMonitor initialized")
    
    def track(self, operation: str):
        """
        Context manager for tracking operation performance.
        
        Usage:
            with monitor.track('generate_signal'):
                # Your code here
                result = expensive_operation()
        """
        return _PerformanceTracker(self, operation)
    
    def record_metric(self, metric: PerformanceMetrics):
        """Record a performance metric."""
        self.metrics_history.append(metric)
        
        # Update operation stats
        stats = self.operation_stats[metric.operation]
        stats['count'] += 1
        stats['total_time'] += metric.duration_ms
        
        if not metric.success:
            stats['errors'] += 1
        
        # Check thresholds and alert
        self._check_alerts(metric)
    
    def _check_alerts(self, metric: PerformanceMetrics):
        """Check if metric exceeds thresholds."""
        alerts = []
        
        if metric.duration_ms > self.alert_thresholds['duration_ms']:
            alerts.append(
                f"Slow operation: {metric.operation} took {metric.duration_ms:.0f}ms"
            )
        
        if metric.memory_mb > self.alert_thresholds['memory_mb']:
            alerts.append(
                f"High memory: {metric.operation} used {metric.memory_mb:.0f}MB"
            )
        
        if metric.cpu_percent > self.alert_thresholds['cpu_percent']:
            alerts.append(
                f"High CPU: {metric.operation} used {metric.cpu_percent:.1f}%"
            )
        
        for alert in alerts:
            logger.warning(alert)
    
    def get_statistics(
        self,
        operation: Optional[str] = None,
        window: Optional[timedelta] = None,
    ) -> Dict[str, Any]:
        """
        Get performance statistics.
        
        Args:
            operation: Specific operation to analyze (None = all)
            window: Time window for analysis (None = all time)
        
        Returns:
            Dictionary of statistics
        """
        # Filter metrics
        metrics = list(self.metrics_history)
        
        if window:
            cutoff = datetime.now() - window
            metrics = [m for m in metrics if m.timestamp >= cutoff]
        
        if operation:
            metrics = [m for m in metrics if m.operation == operation]
        
        if not metrics:
            return {'error': 'No metrics found'}
        
        # Compute statistics
        durations = [m.duration_ms for m in metrics]
        memories = [m.memory_mb for m in metrics]
        cpus = [m.cpu_percent for m in metrics]
        success_count = sum(1 for m in metrics if m.success)
        
        return {
            'count': len(metrics),
            'success_rate': success_count / len(metrics),
            'duration_ms': {
                'mean': np.mean(durations),
                'median': np.median(durations),
                'std': np.std(durations),
                'min': np.min(durations),
                'max': np.max(durations),
                'p95': np.percentile(durations, 95),
                'p99': np.percentile(durations, 99),
            },
            'memory_mb': {
                'mean': np.mean(memories),
                'max': np.max(memories),
            },
            'cpu_percent': {
                'mean': np.mean(cpus),
                'max': np.max(cpus),
            },
        }
    
    def get_operation_summary(self) -> pd.DataFrame:
        """Get summary of all operations."""
        summary = []
        
        for operation, stats in self.operation_stats.items():
            if stats['count'] > 0:
                avg_time = stats['total_time'] / stats['count']
                error_rate = stats['errors'] / stats['count']
                
                summary.append({
                    'operation': operation,
                    'count': stats['count'],
                    'avg_time_ms': avg_time,
                    'total_time_ms': stats['total_time'],
                    'errors': stats['errors'],
                    'error_rate': error_rate,
                })
        
        return pd.DataFrame(summary).sort_values('total_time_ms', ascending=False)
    
    def generate_report(
        self,
        window: Optional[timedelta] = None,
        output_file: Optional[str] = None,
    ) -> str:
        """
        Generate comprehensive performance report.
        
        Args:
            window: Time window (None = all time)
            output_file: Optional file to save report
        
        Returns:
            Report as string
        """
        report_lines = [
            "=" * 80,
            "PERFORMANCE REPORT",
            "=" * 80,
            f"Generated: {datetime.now().isoformat()}",
            f"Uptime: {time.time() - self.start_time:.1f}s",
            "",
        ]
        
        # Overall statistics
        overall_stats = self.get_statistics(window=window)
        
        report_lines.extend([
            "Overall Statistics:",
            f"  Total operations: {overall_stats['count']}",
            f"  Success rate: {overall_stats['success_rate']:.2%}",
            "",
            "Duration (ms):",
            f"  Mean: {overall_stats['duration_ms']['mean']:.2f}",
            f"  Median: {overall_stats['duration_ms']['median']:.2f}",
            f"  Std: {overall_stats['duration_ms']['std']:.2f}",
            f"  P95: {overall_stats['duration_ms']['p95']:.2f}",
            f"  P99: {overall_stats['duration_ms']['p99']:.2f}",
            f"  Max: {overall_stats['duration_ms']['max']:.2f}",
            "",
            "Memory (MB):",
            f"  Mean: {overall_stats['memory_mb']['mean']:.2f}",
            f"  Max: {overall_stats['memory_mb']['max']:.2f}",
            "",
            "CPU (%):",
            f"  Mean: {overall_stats['cpu_percent']['mean']:.1f}",
            f"  Max: {overall_stats['cpu_percent']['max']:.1f}",
            "",
        ])
        
        # Operation breakdown
        operation_summary = self.get_operation_summary()
        
        if len(operation_summary) > 0:
            report_lines.extend([
                "Operation Breakdown:",
                operation_summary.to_string(index=False),
                "",
            ])
        
        # System info
        report_lines.extend([
            "System Information:",
            f"  CPU count: {psutil.cpu_count()}",
            f"  Total memory: {psutil.virtual_memory().total / 1024**3:.2f} GB",
            f"  Available memory: {psutil.virtual_memory().available / 1024**3:.2f} GB",
            "=" * 80,
        ])
        
        report = "\n".join(report_lines)
        
        # Save to file if requested
        if output_file:
            with open(output_file, 'w') as f:
                f.write(report)
            logger.info(f"Report saved to {output_file}")
        
        return report
    
    def export_metrics(self, output_file: str, format: str = 'csv'):
        """
        Export metrics to file.
        
        Args:
            output_file: Output file path
            format: 'csv' or 'json'
        """
        metrics_data = []
        
        for metric in self.metrics_history:
            metrics_data.append({
                'timestamp': metric.timestamp.isoformat(),
                'operation': metric.operation,
                'duration_ms': metric.duration_ms,
                'memory_mb': metric.memory_mb,
                'cpu_percent': metric.cpu_percent,
                'success': metric.success,
                'error': metric.error,
            })
        
        if format == 'csv':
            df = pd.DataFrame(metrics_data)
            df.to_csv(output_file, index=False)
        elif format == 'json':
            with open(output_file, 'w') as f:
                json.dump(metrics_data, f, indent=2)
        else:
            raise ValueError(f"Unknown format: {format}")
        
        logger.info(f"Metrics exported to {output_file}")


class _PerformanceTracker:
    """Context manager for tracking operation performance."""
    
    def __init__(self, monitor: PerformanceMonitor, operation: str):
        self.monitor = monitor
        self.operation = operation
        self.start_time = None
        self.start_memory = None
        self.start_cpu = None
    
    def __enter__(self):
        self.start_time = time.time()
        self.start_memory = self.monitor.process.memory_info().rss / 1024**2  # MB
        self.start_cpu = self.monitor.process.cpu_percent()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration_ms = (time.time() - self.start_time) * 1000
        memory_mb = self.monitor.process.memory_info().rss / 1024**2
        cpu_percent = self.monitor.process.cpu_percent()
        
        metric = PerformanceMetrics(
            timestamp=datetime.now(),
            operation=self.operation,
            duration_ms=duration_ms,
            memory_mb=memory_mb - self.start_memory,
            cpu_percent=cpu_percent,
            success=(exc_type is None),
            error=str(exc_val) if exc_val else None,
        )
        
        self.monitor.record_metric(metric)
        
        return False  # Don't suppress exceptions


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    monitor = PerformanceMonitor()
    
    # Simulate some operations
    for i in range(100):
        with monitor.track('test_operation'):
            time.sleep(0.01)  # Simulate work
            if i % 20 == 0:
                time.sleep(0.1)  # Simulate slow operation
    
    # Generate report
    report = monitor.generate_report()
    print(report)
    
    # Export metrics
    monitor.export_metrics('performance_metrics.csv', format='csv')
