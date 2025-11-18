"""
Comprehensive Benchmark Suite for Super Gnosis

Benchmarks:
1. Data fetching latency (all sources)
2. ML training speed
3. Prediction latency
4. End-to-end pipeline performance

Run with: python benchmarks/benchmark_suite.py
"""

import time
import statistics
from typing import Dict, List, Callable
from dataclasses import dataclass
from loguru import logger
import polars as pl

# Configure logger
logger.add("benchmarks/benchmark_results.log", rotation="10 MB")


@dataclass
class BenchmarkResult:
    """Single benchmark result."""
    name: str
    mean_time_ms: float
    median_time_ms: float
    std_dev_ms: float
    min_time_ms: float
    max_time_ms: float
    iterations: int
    ops_per_second: float


class BenchmarkSuite:
    """Comprehensive benchmark suite."""
    
    def __init__(self, iterations: int = 10):
        """
        Initialize benchmark suite.
        
        Args:
            iterations: Number of iterations per benchmark
        """
        self.iterations = iterations
        self.results: List[BenchmarkResult] = []
    
    def benchmark(self, name: str, func: Callable, *args, **kwargs) -> BenchmarkResult:
        """
        Benchmark a function.
        
        Args:
            name: Benchmark name
            func: Function to benchmark
            *args, **kwargs: Function arguments
        
        Returns:
            BenchmarkResult with statistics
        """
        logger.info(f"Benchmarking: {name} ({self.iterations} iterations)")
        
        times = []
        for i in range(self.iterations):
            start = time.perf_counter()
            func(*args, **kwargs)
            end = time.perf_counter()
            times.append((end - start) * 1000)  # Convert to ms
        
        mean_time = statistics.mean(times)
        median_time = statistics.median(times)
        std_dev = statistics.stdev(times) if len(times) > 1 else 0
        min_time = min(times)
        max_time = max(times)
        ops_per_sec = 1000 / mean_time if mean_time > 0 else 0
        
        result = BenchmarkResult(
            name=name,
            mean_time_ms=mean_time,
            median_time_ms=median_time,
            std_dev_ms=std_dev,
            min_time_ms=min_time,
            max_time_ms=max_time,
            iterations=self.iterations,
            ops_per_second=ops_per_sec
        )
        
        self.results.append(result)
        logger.info(f"  ✅ {name}: {mean_time:.2f}ms (±{std_dev:.2f}ms)")
        
        return result
    
    def print_results(self):
        """Print all benchmark results."""
        print("\n" + "="*80)
        print("BENCHMARK RESULTS")
        print("="*80)
        
        # Group by category
        categories = {
            "Data Fetching": [r for r in self.results if "fetch" in r.name.lower() or "data" in r.name.lower()],
            "ML Training": [r for r in self.results if "train" in r.name.lower()],
            "ML Prediction": [r for r in self.results if "predict" in r.name.lower()],
            "Feature Engineering": [r for r in self.results if "feature" in r.name.lower()],
            "End-to-End": [r for r in self.results if "e2e" in r.name.lower() or "pipeline" in r.name.lower()]
        }
        
        for category, results in categories.items():
            if not results:
                continue
            
            print(f"\n{category}:")
            print("-" * 80)
            print(f"{'Benchmark':<40} {'Mean':<12} {'Median':<12} {'Std Dev':<12} {'Ops/sec':<10}")
            print("-" * 80)
            
            for result in results:
                print(f"{result.name:<40} {result.mean_time_ms:>10.2f}ms "
                      f"{result.median_time_ms:>10.2f}ms "
                      f"{result.std_dev_ms:>10.2f}ms "
                      f"{result.ops_per_second:>8.2f}")
        
        print("\n" + "="*80)
    
    def export_results(self, filename: str = "benchmarks/results.csv"):
        """Export results to CSV."""
        import csv
        
        with open(filename, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'Benchmark', 'Mean (ms)', 'Median (ms)', 'Std Dev (ms)',
                'Min (ms)', 'Max (ms)', 'Iterations', 'Ops/sec'
            ])
            
            for result in self.results:
                writer.writerow([
                    result.name,
                    f"{result.mean_time_ms:.2f}",
                    f"{result.median_time_ms:.2f}",
                    f"{result.std_dev_ms:.2f}",
                    f"{result.min_time_ms:.2f}",
                    f"{result.max_time_ms:.2f}",
                    result.iterations,
                    f"{result.ops_per_second:.2f}"
                ])
        
        logger.info(f"Results exported to {filename}")


def run_data_benchmarks(suite: BenchmarkSuite):
    """Benchmark data fetching (Unusual Whales primary)."""
    from engines.inputs.unusual_whales_adapter import UnusualWhalesAdapter
    import os
    
    print("\n🔄 Running Data Fetching Benchmarks...")
    print("NOTE: yfinance and Yahoo Options removed - using Unusual Whales")
    
    # Unusual Whales Market Tide
    adapter = UnusualWhalesAdapter(
        api_key=os.getenv("UNUSUAL_WHALES_API_KEY", "8932cd23-72b3-4f74-9848-13f9103b9df5")
    )
    suite.benchmark("Fetch Market Tide (Unusual Whales)", adapter.get_market_tide)
    
    # Unusual Whales Options Chain
    suite.benchmark(
        "Fetch Options Chain (Unusual Whales)",
        adapter.get_ticker_chain,
        "SPY"
    )
    
    # Unusual Whales Options Flow
    suite.benchmark(
        "Fetch Options Flow (Unusual Whales)",
        adapter.get_flow_alerts,
        limit=10
    )


def run_ml_benchmarks(suite: BenchmarkSuite):
    """Benchmark ML operations."""
    from ml.labels.generator import LabelGenerator, LabelConfig
    from ml.features.technical import TechnicalIndicators
    # NOTE: yfinance removed - ML benchmarks need to be updated to use Unusual Whales
    
    print("\n🔄 Running ML Benchmarks...")
    print("WARNING: ML benchmarks temporarily disabled - yfinance removed")
    return  # Skip ML benchmarks until updated for Unusual Whales
    
    # TODO: Update to use Unusual Whales historical data
    # adapter = UnusualWhalesAdapter(...)
    # df = adapter.get_ticker_historical("SPY", start_date, end_date)
    
    # Label generation
    config = LabelConfig(horizons=[5, 15, 60])
    generator = LabelGenerator(config)
    suite.benchmark(
        "Generate Labels (3 horizons)",
        generator.generate,
        df, "close"
    )
    
    # Feature engineering
    tech = TechnicalIndicators()
    suite.benchmark(
        "Add Technical Indicators",
        tech.add_all_indicators,
        df
    )


def run_prediction_benchmarks(suite: BenchmarkSuite):
    """Benchmark prediction latency."""
    import numpy as np
    import pandas as pd
    
    print("\n🔄 Running Prediction Benchmarks...")
    
    # Create mock model for benchmarking
    from lightgbm import LGBMClassifier
    
    # Create sample data
    n_samples = 1000
    n_features = 100
    X_train = np.random.randn(n_samples, n_features)
    y_train = np.random.randint(0, 2, n_samples)
    
    # Train quick model
    model = LGBMClassifier(n_estimators=10, max_depth=3, verbose=-1)
    model.fit(X_train, y_train)
    
    # Single prediction
    X_single = X_train[0:1]
    suite.benchmark(
        "Single Prediction (LightGBM)",
        model.predict,
        X_single
    )
    
    # Batch prediction (100 samples)
    X_batch = X_train[:100]
    suite.benchmark(
        "Batch Prediction 100x (LightGBM)",
        model.predict,
        X_batch
    )


def run_end_to_end_benchmark(suite: BenchmarkSuite):
    """Benchmark end-to-end pipeline."""
    # NOTE: yfinance removed - End-to-end benchmarks need update
    from ml.labels.generator import LabelGenerator, LabelConfig
    from ml.features.technical import TechnicalIndicators
    
    print("\n🔄 Running End-to-End Benchmark...")
    print("WARNING: E2E benchmarks temporarily disabled - yfinance removed")
    return  # Skip until updated for Unusual Whales
    
    # TODO: Update to use Unusual Whales
    def e2e_pipeline():
        # Fetch data
        adapter = YFinanceAdapter()
        df = adapter.fetch_history("SPY", "5d", "1d")
        
        # Generate labels
        config = LabelConfig(horizons=[5])
        generator = LabelGenerator(config)
        df_with_labels = generator.generate(df, "close")
        
        # Add features
        tech = TechnicalIndicators()
        df_final = tech.add_all_indicators(df_with_labels)
        
        return df_final
    
    suite.benchmark("E2E Pipeline (fetch + labels + features)", e2e_pipeline)


def main():
    """Run all benchmarks."""
    print("\n" + "🚀"*35)
    print("  SUPER GNOSIS BENCHMARK SUITE")
    print("🚀"*35)
    
    suite = BenchmarkSuite(iterations=10)
    
    # Run all benchmark categories
    run_data_benchmarks(suite)
    run_ml_benchmarks(suite)
    run_prediction_benchmarks(suite)
    run_end_to_end_benchmark(suite)
    
    # Print results
    suite.print_results()
    
    # Export to CSV
    suite.export_results()
    
    print("\n✅ Benchmarks complete!")
    print("📊 Results saved to: benchmarks/results.csv")
    print("📝 Logs saved to: benchmarks/benchmark_results.log")
    
    # Performance targets
    print("\n🎯 Performance Targets:")
    print("   ✅ Data fetch < 1000ms: PASS" if any(r.mean_time_ms < 1000 for r in suite.results if "fetch" in r.name.lower()) else "   ❌ FAIL")
    print("   ✅ Single prediction < 10ms: PASS" if any(r.mean_time_ms < 10 for r in suite.results if "single prediction" in r.name.lower()) else "   ❌ FAIL")
    print("   ✅ E2E pipeline < 5000ms: PASS" if any(r.mean_time_ms < 5000 for r in suite.results if "e2e" in r.name.lower()) else "   ❌ FAIL")


if __name__ == "__main__":
    main()
