"""Path geometry trend engine — Python port of the Pine indicator.

This mirrors ``indicators/Path_Geometry_Trend_Detector.pine`` closely enough to
draw conclusions that transfer back to the chart. Where Pine semantics are
subtle the matching behaviour is called out in a comment, because a harness
that quietly disagrees with the live script is worse than no harness at all.

Parity checks live in ``tests/test_engine.py``. If you change the Pine engine,
change this too and re-run them.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class EngineParams:
    """Every tunable in the Pine script's engine and classification groups."""

    er_len: int = 20
    don_len: int = 20
    pos_len: int = 20
    bal_len: int = 20

    w_er: float = 1.0
    w_struct: float = 1.0
    w_pos: float = 1.0
    w_bal: float = 1.0

    use_gate: bool = True
    exp_len: int = 20
    exp_min: float = 0.80

    enter_thresh: float = 40.0
    strong_thresh: float = 70.0
    exit_thresh: float = 15.0

    def validate(self) -> None:
        """Mirrors the runtime.error guards in the Pine script."""
        if self.exit_thresh >= self.enter_thresh:
            raise ValueError(
                f"exit_thresh ({self.exit_thresh}) must be below enter_thresh "
                f"({self.enter_thresh}); without a gap there is no hysteresis."
            )
        if self.enter_thresh > self.strong_thresh:
            raise ValueError(
                f"enter_thresh ({self.enter_thresh}) must not exceed "
                f"strong_thresh ({self.strong_thresh})."
            )
        if self.w_er + self.w_struct + self.w_pos + self.w_bal <= 0:
            raise ValueError("At least one component weight must be > 0.")


def wilder_atr(high: pd.Series, low: pd.Series, close: pd.Series, length: int) -> pd.Series:
    """ATR using Wilder's RMA, matching Pine's ``ta.atr``.

    Pine's RMA is an EMA with alpha = 1/length, which is *not* the same as a
    simple moving average of true range. Using the wrong one shifts every stop
    level and quietly decorrelates this harness from the chart.
    """
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1.0 / length, adjust=False).mean()


def efficiency_ratio(close: pd.Series, length: int) -> pd.Series:
    """Signed Kaufman efficiency ratio: net displacement / total path length.

    +1 is a straight line up, -1 a straight line down, 0 a path that returns
    to where it started. Carries direction and straightness in one number.
    """
    net_move = close - close.shift(length)
    path_len = close.diff().abs().rolling(length).sum()
    er = np.where(path_len > 0, net_move / path_len, np.nan)
    # Every component falls back to 0 when cold, so a component that is not
    # warm contributes nothing rather than nullifying the composite (audit E1).
    return pd.Series(er, index=close.index).clip(-1.0, 1.0).fillna(0.0)


def breakout_structure(high: pd.Series, low: pd.Series, length: int) -> pd.Series:
    """Donchian break state, held until the opposite band breaks.

    The ``.shift(1)`` is essential and mirrors Pine's ``[1]``: without it the
    current bar sits inside its own channel and a break can never register.
    """
    upper = high.rolling(length).max().shift(1)
    lower = low.rolling(length).min().shift(1)

    broke_up = (high > upper).to_numpy()
    broke_down = (low < lower).to_numpy()

    state = np.zeros(len(high), dtype=float)
    current = 0.0
    for i in range(len(high)):
        if broke_up[i]:
            current = 1.0
        elif broke_down[i]:
            current = -1.0
        state[i] = current
    return pd.Series(state, index=high.index)


def range_position(high: pd.Series, low: pd.Series, close: pd.Series, length: int) -> pd.Series:
    """Where close sits inside its own recent range: +1 top, -1 bottom, 0 mid."""
    rng_high = high.rolling(length).max()
    rng_low = low.rolling(length).min()
    half = (rng_high - rng_low) / 2.0
    mid = (rng_high + rng_low) / 2.0
    pos = np.where(half > 0, (close - mid) / half, np.nan)
    return pd.Series(pos, index=close.index).clip(-1.0, 1.0).fillna(0.0)


def displacement_balance(close: pd.Series, length: int) -> pd.Series:
    """(up closes - down closes) / window. A count, so no single bar dominates."""
    diff = close.diff()
    up = (diff > 0).astype(float).rolling(length).sum()
    down = (diff < 0).astype(float).rolling(length).sum()
    return ((up - down) / length).fillna(0.0)


def expansion_ratio(high: pd.Series, low: pd.Series, length: int) -> pd.Series:
    """Ground covered recently vs ground covered over the preceding window.

    Below 1 means the market is covering less than it was: coiling rather than
    travelling. Returned raw; NaN where the prior window has no range.
    """
    rng_now = high.rolling(length).max() - low.rolling(length).min()
    rng_past = rng_now.shift(length)
    ratio = np.where(rng_past > 0, rng_now / rng_past, np.nan)
    return pd.Series(ratio, index=high.index)


@dataclass
class EngineOutput:
    """Component series, composite score, and the classified state."""

    frame: pd.DataFrame = field(repr=False)

    @property
    def score(self) -> pd.Series:
        return self.frame["score"]

    @property
    def state(self) -> pd.Series:
        return self.frame["state"]


def compute(df: pd.DataFrame, p: EngineParams) -> EngineOutput:
    """Run the full engine over an OHLC frame.

    ``df`` needs columns open/high/low/close (case-insensitive), indexed by
    time. Returns every intermediate component so the sensitivity and
    diagnostic work can look at what actually drove a decision.
    """
    p.validate()
    cols = {c.lower(): c for c in df.columns}
    high, low, close = df[cols["high"]], df[cols["low"]], df[cols["close"]]

    er = efficiency_ratio(close, p.er_len)
    struct = breakout_structure(high, low, p.don_len)
    pos = range_position(high, low, close, p.pos_len)
    bal = displacement_balance(close, p.bal_len)
    exp = expansion_ratio(high, low, p.exp_len)

    w_sum = p.w_er + p.w_struct + p.w_pos + p.w_bal
    score = (
        100.0
        * (p.w_er * er + p.w_struct * struct + p.w_pos * pos + p.w_bal * bal)
        / w_sum
    ).clip(-100.0, 100.0)

    compressing = p.use_gate & exp.notna() & (exp < p.exp_min)

    state = _classify(score.to_numpy(), compressing.to_numpy(), p)

    out = pd.DataFrame(
        {
            "er": er,
            "structure": struct,
            "range_pos": pos,
            "balance": bal,
            "expansion": exp,
            "compressing": compressing,
            "score": score,
            "state": state,
        },
        index=df.index,
    )
    return EngineOutput(out)


def _classify(score: np.ndarray, compressing: np.ndarray, p: EngineParams) -> np.ndarray:
    """Sticky state machine with hysteresis — a direct port of the Pine block.

    Entering a trend needs |score| >= enter_thresh; leaving needs it to fall
    below the looser exit_thresh. The gap is the dead zone that stops noise
    around one boundary flipping the label on adjacent bars.
    """
    n = len(score)
    out = np.empty(n, dtype=object)
    state = "flat"

    for i in range(n):
        s = score[i]
        if state == "up":
            # Full reversal is checked first: it also satisfies the exit test.
            if s <= -p.enter_thresh:
                state = "strong_down" if s <= -p.strong_thresh else "down"
            elif s < p.exit_thresh:
                state = "flat"
            else:
                state = "strong_up" if s >= p.strong_thresh else "up"
        elif state == "strong_up":
            if s <= -p.enter_thresh:
                state = "strong_down" if s <= -p.strong_thresh else "down"
            elif s < p.exit_thresh:
                state = "flat"
            else:
                state = "strong_up" if s >= p.strong_thresh else "up"
        elif state in ("down", "strong_down"):
            if s >= p.enter_thresh:
                state = "strong_up" if s >= p.strong_thresh else "up"
            elif s > -p.exit_thresh:
                state = "flat"
            else:
                state = "strong_down" if s <= -p.strong_thresh else "down"
        elif not compressing[i]:
            if s >= p.enter_thresh:
                state = "strong_up" if s >= p.strong_thresh else "up"
            elif s <= -p.enter_thresh:
                state = "strong_down" if s <= -p.strong_thresh else "down"
        out[i] = state
    return out
