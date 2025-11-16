# tests/backtesting/test_metrics.py

import math

import pytest

from backtesting.metrics import (
    compute_directional_accuracy,
    compute_naive_pnl,
    compute_sharpe_ratio,
    bucket_accuracy_by_energy,
)


class TestDirectionalAccuracy:
    def test_perfect_accuracy(self):
        preds = [1, 1, -1, -1]
        rets = [0.01, 0.02, -0.03, -0.01]
        acc = compute_directional_accuracy(preds, rets)
        assert acc == 1.0

    def test_zero_accuracy(self):
        preds = [1, 1, -1, -1]
        rets = [-0.01, -0.02, 0.03, 0.01]
        acc = compute_directional_accuracy(preds, rets)
        assert acc == 0.0

    def test_neutral_predictions_ignored(self):
        preds = [1, 0, -1, 0]
        rets = [0.01, 0.02, -0.03, -0.01]
        acc = compute_directional_accuracy(preds, rets)
        # two non-neutral predictions, both correct → 1.0
        assert acc == 1.0

    def test_threshold_filters_small_moves(self):
        preds = [1, 1, -1, -1]
        rets = [0.0001, 0.02, -0.0001, -0.03]
        acc_no_threshold = compute_directional_accuracy(preds, rets, threshold=0.0)
        acc_with_threshold = compute_directional_accuracy(preds, rets, threshold=0.001)
        # with threshold, only the 0.02 and -0.03 returns count; both are correct → 1.0
        assert acc_no_threshold == 1.0
        assert acc_with_threshold == 1.0

    def test_empty_input_returns_zero(self):
        acc = compute_directional_accuracy([], [])
        assert acc == 0.0


class TestNaivePnl:
    def test_basic_pnl(self):
        preds = [1, -1, 0]
        rets = [0.01, -0.02, 0.05]
        pnl = compute_naive_pnl(preds, rets, notional=100.0)
        # 1 * 0.01 * 100 + (-1) * (-0.02) * 100 + 0 = 1 + 2 = 3
        assert pnl == pytest.approx(3.0)

    def test_zero_notional(self):
        preds = [1, -1, 1]
        rets = [0.01, -0.02, 0.03]
        pnl = compute_naive_pnl(preds, rets, notional=0.0)
        assert pnl == 0.0

    def test_empty_series(self):
        pnl = compute_naive_pnl([], [])
        assert pnl == 0.0


class TestSharpeRatio:
    def test_zero_variance_returns_zero(self):
        pnl_series = [0.01] * 10
        sharpe = compute_sharpe_ratio(pnl_series)
        assert sharpe == 0.0

    def test_positive_sharpe(self):
        pnl_series = [0.01, 0.02, -0.005, 0.015]
        sharpe = compute_sharpe_ratio(pnl_series)
        assert sharpe > 0.0

    def test_empty_series(self):
        sharpe = compute_sharpe_ratio([])
        assert sharpe == 0.0


class TestBucketAccuracyByEnergy:
    def test_basic_bucketing(self):
        preds = [1, 1, -1, -1, 1]
        rets = [0.01, -0.02, -0.03, 0.04, 0.05]
        energies = [0.1, 0.7, 1.5, 3.0, 10.0]

        buckets = (0.5, 1.0, 2.0, 5.0)
        acc_by_bucket = bucket_accuracy_by_energy(preds, rets, energies, buckets=buckets)

        # We don't assert exact values for all buckets, just structure & range.
        assert set(acc_by_bucket.keys()) == {
            "<= 0.5",
            "0.5 - 1.0",
            "1.0 - 2.0",
            "2.0 - 5.0",
            "> 5.0",
        }
        for val in acc_by_bucket.values():
            assert 0.0 <= val <= 1.0

    def test_all_zero_predictions(self):
        preds = [0, 0, 0]
        rets = [0.01, -0.02, 0.03]
        energies = [0.1, 1.0, 10.0]

        acc_by_bucket = bucket_accuracy_by_energy(preds, rets, energies)
        # With all directions 0, totals per bucket should be 0, hence accuracy 0.0
        for v in acc_by_bucket.values():
            assert v == 0.0

    def test_empty_input(self):
        acc_by_bucket = bucket_accuracy_by_energy([], [], [])
        assert isinstance(acc_by_bucket, dict)
        # default buckets produce fixed labels even on empty input
        # all should be 0.0
        for v in acc_by_bucket.values():
            assert v == 0.0
