"""Trade simulation and performance metrics.

The trade lifecycle mirrors the Pine scripts bar for bar: entry on the rising
edge of the qualifying condition, a chandelier stop seeded at the entry bar
that only ever ratchets, and a score exit at the close. Getting this wrong
would make every downstream number describe a system you are not running.

Deliberately included here, contrary to the "no probability assumptions"
constraint that governs the *signal logic*: expectancy, drawdown, and trade
distribution statistics. That constraint keeps fitted models out of signal
generation, which is defensible. Extending it to evaluation would just mean
flying blind — a deterministic rule set still has to be measured.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .engine import EngineParams, compute, wilder_atr


@dataclass(frozen=True)
class TradeParams:
    atr_len: int = 14
    atr_stop_mult: float = 2.5
    allow_long: bool = True
    allow_short: bool = True
    # Cost model. The Pine strategy defaults to 0.05% commission and 1 tick of
    # slippage; express both here in basis points of notional per side so the
    # harness can be pointed at whatever the real venue charges.
    cost_bps_per_side: float = 5.0


@dataclass
class Trade:
    direction: int  # +1 long, -1 short
    entry_index: int
    entry_time: object
    entry_price: float
    exit_index: int | None = None
    exit_time: object = None
    exit_price: float | None = None
    exit_reason: str = ""
    entry_atr: float = np.nan
    # Excursions, in ATR-at-entry units. These are what calibrate a stop:
    # MAE says how far winning trades were allowed to go against you.
    mae_atr: float = 0.0
    mfe_atr: float = 0.0

    @property
    def gross_return(self) -> float:
        if self.exit_price is None:
            return 0.0
        return self.direction * (self.exit_price - self.entry_price) / self.entry_price

    def net_return(self, cost_bps_per_side: float) -> float:
        return self.gross_return - 2.0 * cost_bps_per_side / 10_000.0


def run_backtest(
    df: pd.DataFrame,
    engine_params: EngineParams | None = None,
    trade_params: TradeParams | None = None,
) -> tuple[list[Trade], pd.DataFrame]:
    """Simulate the strategy over an OHLC frame.

    Returns the closed trades and the per-bar engine frame (with the position
    column appended) so callers can inspect what the engine saw.
    """
    ep = engine_params or EngineParams()
    tp = trade_params or TradeParams()

    cols = {c.lower(): c for c in df.columns}
    high = df[cols["high"]].to_numpy(dtype=float)
    low = df[cols["low"]].to_numpy(dtype=float)
    close = df[cols["close"]].to_numpy(dtype=float)

    eng = compute(df, ep).frame
    score = eng["score"].to_numpy(dtype=float)
    compressing = eng["compressing"].to_numpy(dtype=bool)
    atr = wilder_atr(df[cols["high"]], df[cols["low"]], df[cols["close"]], tp.atr_len).to_numpy(dtype=float)

    long_ok = tp.allow_long & ~compressing & (score >= ep.enter_thresh)
    short_ok = tp.allow_short & ~compressing & (score <= -ep.enter_thresh)
    # The rising edge is the entry: true on exactly one bar, unlike the state,
    # which stays true for the whole run of the trend.
    long_edge = long_ok & ~np.roll(long_ok, 1)
    short_edge = short_ok & ~np.roll(short_ok, 1)
    long_edge[0] = False
    short_edge[0] = False

    trades: list[Trade] = []
    pos = 0
    stop = np.nan
    open_trade: Trade | None = None
    position_series = np.zeros(len(df), dtype=int)

    times = df.index.to_list()

    def close_trade(i: int, price: float, reason: str) -> None:
        nonlocal pos, stop, open_trade
        assert open_trade is not None
        open_trade.exit_index = i
        open_trade.exit_time = times[i]
        open_trade.exit_price = price
        open_trade.exit_reason = reason
        trades.append(open_trade)
        open_trade = None
        pos = 0
        stop = np.nan

    for i in range(len(df)):
        # 1. The stop set on the previous close is live during this bar and
        #    fills intrabar, exactly as the Pine strategy's stop order does.
        if pos == 1 and not np.isnan(stop) and low[i] <= stop:
            close_trade(i, stop, "stop")
        elif pos == -1 and not np.isnan(stop) and high[i] >= stop:
            close_trade(i, stop, "stop")

        # Track excursions while still open, before any close-based exit.
        if open_trade is not None and not np.isnan(open_trade.entry_atr) and open_trade.entry_atr > 0:
            if open_trade.direction == 1:
                adverse = (open_trade.entry_price - low[i]) / open_trade.entry_atr
                favorable = (high[i] - open_trade.entry_price) / open_trade.entry_atr
            else:
                adverse = (high[i] - open_trade.entry_price) / open_trade.entry_atr
                favorable = (open_trade.entry_price - low[i]) / open_trade.entry_atr
            open_trade.mae_atr = max(open_trade.mae_atr, adverse)
            open_trade.mfe_atr = max(open_trade.mfe_atr, favorable)

        # 2. Score exit, at the close.
        if pos == 1 and score[i] < ep.exit_thresh:
            close_trade(i, close[i], "score")
        elif pos == -1 and score[i] > -ep.exit_thresh:
            close_trade(i, close[i], "score")

        # 3. Entries fill at the close. A signal in the direction already held
        #    is ignored; the guard also prevents a re-fire from re-seeding —
        #    and so loosening — a stop that has already ratcheted.
        if long_edge[i] and pos <= 0:
            if pos == -1:
                close_trade(i, close[i], "reverse")
            pos = 1
            stop = high[i] - tp.atr_stop_mult * atr[i]
            open_trade = Trade(1, i, times[i], close[i], entry_atr=atr[i])
        elif short_edge[i] and pos >= 0:
            if pos == 1:
                close_trade(i, close[i], "reverse")
            pos = -1
            stop = low[i] + tp.atr_stop_mult * atr[i]
            open_trade = Trade(-1, i, times[i], close[i], entry_atr=atr[i])
        else:
            # 4. Ratchet for the next bar — tightens only, never loosens.
            if pos == 1:
                stop = np.nanmax([stop, high[i] - tp.atr_stop_mult * atr[i]])
            elif pos == -1:
                stop = np.nanmin([stop, low[i] + tp.atr_stop_mult * atr[i]])

        position_series[i] = pos

    eng = eng.copy()
    eng["position"] = position_series
    return trades, eng


def metrics(trades: list[Trade], df: pd.DataFrame, tp: TradeParams | None = None) -> dict:
    """Performance summary, including the buy-and-hold benchmark.

    The benchmark is not decoration. A trend system that underperforms simply
    holding the instrument has not earned the complexity it costs.
    """
    tp = tp or TradeParams()
    cols = {c.lower(): c for c in df.columns}
    close = df[cols["close"]]

    if not trades:
        return {
            "trades": 0,
            "net_return_pct": 0.0,
            "buy_hold_pct": float((close.iloc[-1] / close.iloc[0] - 1) * 100),
            "win_rate_pct": float("nan"),
            "profit_factor": float("nan"),
            "expectancy_pct": float("nan"),
            "max_drawdown_pct": 0.0,
            "avg_win_pct": float("nan"),
            "avg_loss_pct": float("nan"),
            "avg_bars_held": float("nan"),
            "stop_exit_pct": float("nan"),
        }

    rets = np.array([t.net_return(tp.cost_bps_per_side) for t in trades])
    wins, losses = rets[rets > 0], rets[rets <= 0]

    # Compounded equity across sequential trades.
    equity = np.cumprod(1.0 + rets)
    peak = np.maximum.accumulate(equity)
    max_dd = float(((equity - peak) / peak).min() * 100)

    gross_win = float(wins.sum()) if len(wins) else 0.0
    gross_loss = float(-losses.sum()) if len(losses) else 0.0
    bars = [t.exit_index - t.entry_index for t in trades if t.exit_index is not None]

    return {
        "trades": len(trades),
        "net_return_pct": float((equity[-1] - 1) * 100),
        "buy_hold_pct": float((close.iloc[-1] / close.iloc[0] - 1) * 100),
        "win_rate_pct": float(len(wins) / len(rets) * 100),
        "profit_factor": float(gross_win / gross_loss) if gross_loss > 0 else float("inf"),
        "expectancy_pct": float(rets.mean() * 100),
        "max_drawdown_pct": max_dd,
        "avg_win_pct": float(wins.mean() * 100) if len(wins) else float("nan"),
        "avg_loss_pct": float(losses.mean() * 100) if len(losses) else float("nan"),
        "avg_bars_held": float(np.mean(bars)) if bars else float("nan"),
        "stop_exit_pct": float(
            sum(1 for t in trades if t.exit_reason == "stop") / len(trades) * 100
        ),
    }
