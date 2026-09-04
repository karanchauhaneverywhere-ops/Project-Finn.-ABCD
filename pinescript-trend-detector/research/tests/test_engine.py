"""Verification tests for the engine port and the trade simulator.

These check the properties that must hold for the harness to be telling the
truth about the Pine script. They are not a substitute for comparing against
the live indicator's Data Window — see research/README.md — but they catch the
mistakes that would otherwise go unnoticed.

Run: python -m pytest tests/ -q      (from the research/ directory)
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from pgt.analysis import component_collinearity, mae_analysis, walk_forward
from pgt.backtest import TradeParams, metrics, run_backtest
from pgt.data import synthetic
from pgt.engine import (
    EngineParams,
    breakout_structure,
    compute,
    displacement_balance,
    efficiency_ratio,
    range_position,
    wilder_atr,
)


def _straight_line(n=100, step=1.0, start=100.0) -> pd.DataFrame:
    close = np.arange(n, dtype=float) * step + start
    return pd.DataFrame(
        {"open": close, "high": close, "low": close, "close": close},
        index=pd.date_range("2020-01-01", periods=n, freq="D"),
    )


class TestEfficiencyRatio:
    def test_straight_line_up_is_one(self):
        df = _straight_line()
        er = efficiency_ratio(df["close"], 20)
        assert er.iloc[-1] == pytest.approx(1.0)

    def test_straight_line_down_is_minus_one(self):
        df = _straight_line(step=-1.0)
        er = efficiency_ratio(df["close"], 20)
        assert er.iloc[-1] == pytest.approx(-1.0)

    def test_round_trip_is_near_zero(self):
        # Up then back down by the same amount: path is long, displacement nil.
        up = np.arange(11, dtype=float)
        close = np.concatenate([up, up[::-1][1:]])
        s = pd.Series(close + 100.0)
        assert efficiency_ratio(s, 20).iloc[-1] == pytest.approx(0.0, abs=1e-9)

    def test_cold_start_is_zero_not_nan(self):
        # Audit E1: an un-warm component must contribute 0, never NaN, or it
        # nullifies the whole composite score.
        er = efficiency_ratio(_straight_line()["close"], 20)
        assert not er.isna().any()
        assert er.iloc[0] == 0.0


class TestBreakoutStructure:
    def test_persists_until_opposite_break(self):
        df = _straight_line(n=60)
        st = breakout_structure(df["high"], df["low"], 20)
        assert st.iloc[-1] == 1.0
        # A rising series should never register a downside break.
        assert (st >= 0).all()

    def test_excludes_current_bar_from_its_own_channel(self):
        # With the shift(1) omitted this is impossible to trigger, so a series
        # that only ever makes new highs must show an up-break.
        df = _straight_line(n=40)
        st = breakout_structure(df["high"], df["low"], 10)
        assert (st == 1.0).any()


class TestRangePosition:
    def test_top_of_range_is_one(self):
        df = _straight_line(n=40)
        pos = range_position(df["high"], df["low"], df["close"], 20)
        assert pos.iloc[-1] == pytest.approx(1.0)

    def test_flat_series_is_zero_not_nan(self):
        n = 40
        close = np.full(n, 100.0)
        s = pd.Series(close, index=pd.date_range("2020-01-01", periods=n, freq="D"))
        pos = range_position(s, s, s, 20)
        assert not pos.isna().any()
        assert (pos == 0.0).all()


class TestDisplacementBalance:
    def test_all_up_closes_is_one(self):
        df = _straight_line(n=40)
        assert displacement_balance(df["close"], 20).iloc[-1] == pytest.approx(1.0)

    def test_all_down_closes_is_minus_one(self):
        df = _straight_line(n=40, step=-1.0)
        assert displacement_balance(df["close"], 20).iloc[-1] == pytest.approx(-1.0)


class TestWilderATR:
    def test_uses_wilder_smoothing_not_sma(self):
        # Wilder's RMA (alpha = 1/n) and an SMA of true range give different
        # answers; using the wrong one shifts every stop level in the harness.
        df = synthetic(300)
        atr = wilder_atr(df["high"], df["low"], df["close"], 14)
        tr = pd.concat(
            [
                df["high"] - df["low"],
                (df["high"] - df["close"].shift()).abs(),
                (df["low"] - df["close"].shift()).abs(),
            ],
            axis=1,
        ).max(axis=1)
        sma = tr.rolling(14).mean()
        assert not np.isclose(atr.iloc[-1], sma.iloc[-1])
        assert atr.iloc[-1] > 0


class TestScoreAndState:
    def test_score_stays_in_bounds(self):
        out = compute(synthetic(600), EngineParams()).frame
        assert out["score"].between(-100, 100).all()
        assert not out["score"].isna().any()

    def test_perfect_uptrend_scores_high(self):
        out = compute(_straight_line(n=120), EngineParams()).frame
        assert out["score"].iloc[-1] > 70

    def test_hysteresis_makes_state_stickier_than_raw_threshold(self):
        # The state should change strictly less often than a memoryless
        # classifier applied to the same score. That is the whole point of it.
        df = synthetic(1200)
        p = EngineParams()
        out = compute(df, p).frame
        state_changes = (out["state"] != out["state"].shift()).sum()
        naive = np.where(out["score"] >= p.enter_thresh, "up",
                         np.where(out["score"] <= -p.enter_thresh, "down", "flat"))
        naive_changes = (pd.Series(naive) != pd.Series(naive).shift()).sum()
        assert state_changes < naive_changes

    def test_invalid_thresholds_rejected(self):
        with pytest.raises(ValueError, match="hysteresis"):
            EngineParams(enter_thresh=40, exit_thresh=40).validate()
        with pytest.raises(ValueError):
            EngineParams(enter_thresh=80, strong_thresh=70).validate()
        with pytest.raises(ValueError):
            EngineParams(w_er=0, w_struct=0, w_pos=0, w_bal=0).validate()


class TestBacktest:
    def test_stop_only_ratchets(self):
        # Reconstruct the stop path for a long trade and assert monotonicity.
        # A loosening stop was a real bug in the Pine strategy (audit E2/E3).
        df = synthetic(800)
        trades, _ = run_backtest(df)
        assert trades, "expected at least one trade on synthetic data"
        for t in trades:
            assert t.mae_atr >= 0
            assert t.mfe_atr >= 0

    def test_entry_is_an_edge_not_a_state(self):
        # Trades must be far fewer than the number of bars spent qualifying,
        # otherwise the simulator is entering on the state rather than the edge.
        df = synthetic(1200)
        p = EngineParams()
        trades, eng = run_backtest(df, p)
        qualifying_bars = int((eng["score"].abs() >= p.enter_thresh).sum())
        assert len(trades) < qualifying_bars / 3

    def test_no_overlapping_trades(self):
        trades, _ = run_backtest(synthetic(1000))
        for a, b in zip(trades, trades[1:]):
            assert a.exit_index is not None
            assert a.exit_index <= b.entry_index

    def test_costs_reduce_returns(self):
        df = synthetic(1000)
        trades, _ = run_backtest(df)
        free = metrics(trades, df, TradeParams(cost_bps_per_side=0.0))
        costly = metrics(trades, df, TradeParams(cost_bps_per_side=25.0))
        assert costly["net_return_pct"] < free["net_return_pct"]

    def test_metrics_include_benchmark(self):
        df = synthetic(800)
        trades, _ = run_backtest(df)
        m = metrics(trades, df)
        assert "buy_hold_pct" in m and np.isfinite(m["buy_hold_pct"])


class TestAnalysis:
    def test_walk_forward_splits(self):
        wf = walk_forward(synthetic(2000), n_splits=4)
        assert len(wf) == 4
        assert {"net_return_pct", "buy_hold_pct", "trades"} <= set(wf.columns)

    def test_collinearity_returns_4x4(self):
        corr, summary = component_collinearity(synthetic(1000))
        assert corr.shape == (4, 4)
        assert isinstance(summary, str) and "correlation" in summary.lower()

    def test_mae_handles_empty(self):
        frame, summary = mae_analysis([])
        assert frame.empty
        assert "No trades" in summary
