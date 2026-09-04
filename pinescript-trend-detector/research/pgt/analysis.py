"""Walk-forward, parameter sensitivity, MAE calibration, component collinearity.

These four answer questions a single backtest number cannot:

* Walk-forward  — is the edge present across periods, or concentrated in one?
* Sensitivity   — is the parameter set on a plateau, or a knife-edge (i.e. fit
                  to noise and certain to fail out of sample)?
* MAE           — where should the stop actually be, measured rather than
                  guessed?
* Collinearity  — do the four components carry independent information, or is
                  the composite one factor wearing four hats?
"""

from __future__ import annotations

import itertools
from dataclasses import replace

import numpy as np
import pandas as pd

from .backtest import TradeParams, metrics, run_backtest
from .engine import EngineParams, compute


def walk_forward(
    df: pd.DataFrame,
    ep: EngineParams | None = None,
    tp: TradeParams | None = None,
    n_splits: int = 5,
) -> pd.DataFrame:
    """Run the same parameters over N contiguous slices of history.

    This is walk-forward *analysis*, not walk-forward optimisation: it does not
    re-fit per window, it asks whether one fixed configuration holds up across
    periods. That is the more important question first — a system that only
    works in one slice is not a system, and re-fitting per window would hide
    exactly that.
    """
    ep, tp = ep or EngineParams(), tp or TradeParams()
    bounds = np.linspace(0, len(df), n_splits + 1, dtype=int)
    rows = []
    for k in range(n_splits):
        seg = df.iloc[bounds[k] : bounds[k + 1]]
        if len(seg) < max(ep.er_len, ep.don_len, ep.exp_len * 2) + 10:
            continue
        trades, _ = run_backtest(seg, ep, tp)
        m = metrics(trades, seg, tp)
        rows.append(
            {
                "segment": k + 1,
                "start": seg.index[0],
                "end": seg.index[-1],
                "bars": len(seg),
                **m,
            }
        )
    return pd.DataFrame(rows)


def summarise_walk_forward(wf: pd.DataFrame) -> str:
    """Plain-language verdict on consistency across segments."""
    if wf.empty:
        return "No segment had enough bars to evaluate."
    profitable = int((wf["net_return_pct"] > 0).sum())
    total = len(wf)
    beat_bh = int((wf["net_return_pct"] > wf["buy_hold_pct"]).sum())
    worst = wf["net_return_pct"].min()
    best = wf["net_return_pct"].max()
    lines = [
        f"Profitable in {profitable}/{total} segments; beat buy-and-hold in {beat_bh}/{total}.",
        f"Segment returns span {worst:.1f}% to {best:.1f}%.",
    ]
    if profitable <= total / 2:
        lines.append(
            "VERDICT: not consistent. Any positive total is carried by a minority "
            "of periods, which is what curve-fitting looks like from the outside."
        )
    elif best > 0 and worst < 0 and best > 4 * abs(worst):
        lines.append(
            "VERDICT: profitable overall but concentrated. Check whether one "
            "segment contains a single outsized trend that carries everything."
        )
    else:
        lines.append("VERDICT: reasonably consistent across periods.")
    return "\n".join(lines)


def sensitivity(
    df: pd.DataFrame,
    grid: dict[str, list],
    ep: EngineParams | None = None,
    tp: TradeParams | None = None,
) -> pd.DataFrame:
    """Grid-search engine parameters and report the result surface.

    The point is not to find the best cell — that is how overfitting happens.
    It is to see whether the neighbourhood around your chosen cell is flat. A
    good parameter sits in the middle of a plateau; a parameter whose
    performance collapses one step away was fitted to noise.
    """
    ep, tp = ep or EngineParams(), tp or TradeParams()
    keys = list(grid)
    rows = []
    for combo in itertools.product(*(grid[k] for k in keys)):
        candidate = replace(ep, **dict(zip(keys, combo)))
        try:
            candidate.validate()
        except ValueError:
            continue
        trades, _ = run_backtest(df, candidate, tp)
        m = metrics(trades, df, tp)
        rows.append({**dict(zip(keys, combo)), **m})
    return pd.DataFrame(rows)


def summarise_sensitivity(sens: pd.DataFrame, metric: str = "net_return_pct") -> str:
    """Is this a plateau or a knife-edge?"""
    if sens.empty:
        return "Grid produced no valid combinations."
    vals = sens[metric].to_numpy(dtype=float)
    vals = vals[np.isfinite(vals)]
    if len(vals) == 0:
        return "No finite results in the grid."
    positive = int((vals > 0).sum())
    lines = [
        f"{len(vals)} parameter combinations tested.",
        f"Positive in {positive}/{len(vals)} ({positive / len(vals) * 100:.0f}%).",
        f"Median {np.median(vals):.1f}%, best {vals.max():.1f}%, worst {vals.min():.1f}%.",
    ]
    if positive / len(vals) < 0.5:
        lines.append(
            "VERDICT: knife-edge. Most of the parameter space loses money, so a "
            "profitable cell is more likely a lucky draw than a real edge."
        )
    elif np.median(vals) > 0 and vals.min() > -abs(np.median(vals)):
        lines.append(
            "VERDICT: plateau. Performance is broadly positive across the "
            "neighbourhood, which is what a robust parameter choice looks like."
        )
    else:
        lines.append(
            "VERDICT: mixed. Positive on balance but with real losing regions — "
            "prefer a cell surrounded by other positive cells, not the maximum."
        )
    return "\n".join(lines)


def mae_analysis(trades: list, tp: TradeParams | None = None) -> tuple[pd.DataFrame, str]:
    """Maximum Adverse Excursion, the empirical way to size a stop.

    For every trade, how far did it go against you before resolving? If winners
    rarely draw more than X ATR against you, a stop beyond X is donating room
    for nothing; a stop inside X is cutting trades that would have worked.
    """
    tp = tp or TradeParams()
    if not trades:
        return pd.DataFrame(), "No trades to analyse."

    rows = [
        {
            "direction": t.direction,
            "reason": t.exit_reason,
            "net_return_pct": t.net_return(tp.cost_bps_per_side) * 100,
            "mae_atr": t.mae_atr,
            "mfe_atr": t.mfe_atr,
            "winner": t.net_return(tp.cost_bps_per_side) > 0,
        }
        for t in trades
    ]
    frame = pd.DataFrame(rows)

    winners = frame[frame["winner"]]
    losers = frame[~frame["winner"]]
    lines = [f"{len(frame)} trades ({len(winners)} winners, {len(losers)} losers)."]

    if len(winners) >= 5:
        q = winners["mae_atr"].quantile([0.5, 0.75, 0.9, 0.95])
        lines.append(
            "Winning trades' adverse excursion (ATR): "
            f"median {q[0.5]:.2f}, 75th {q[0.75]:.2f}, "
            f"90th {q[0.9]:.2f}, 95th {q[0.95]:.2f}."
        )
        lines.append(
            f"A stop at {q[0.9]:.2f} ATR would have preserved ~90% of the winners. "
            f"Current setting is {tp.atr_stop_mult:.2f} ATR."
        )
        if tp.atr_stop_mult > q[0.95] * 1.3:
            lines.append(
                "VERDICT: the stop looks wider than it needs to be — it is giving "
                "away room that winners never used."
            )
        elif tp.atr_stop_mult < q[0.75]:
            lines.append(
                "VERDICT: the stop looks too tight — it is cutting trades that "
                "historically recovered and went on to win."
            )
        else:
            lines.append("VERDICT: the stop is in a defensible range for this data.")
    else:
        lines.append("Too few winning trades for the MAE distribution to mean anything.")

    return frame, "\n".join(lines)


def component_collinearity(df: pd.DataFrame, ep: EngineParams | None = None) -> tuple[pd.DataFrame, str]:
    """Correlation between the four components.

    The engine presents itself as four independent votes. All four are derived
    from the same OHLC series over similar windows, so they may be measuring
    one thing four times — in which case the weighted average provides far less
    diversification than the architecture implies.
    """
    ep = ep or EngineParams()
    eng = compute(df, ep).frame
    parts = eng[["er", "structure", "range_pos", "balance"]].dropna()
    corr = parts.corr()

    off_diag = corr.to_numpy()[np.triu_indices(4, k=1)]
    mean_abs = float(np.abs(off_diag).mean())
    worst = float(np.abs(off_diag).max())

    lines = [
        f"Mean |correlation| between components: {mean_abs:.2f} (worst pair {worst:.2f}).",
    ]
    if mean_abs > 0.7:
        lines.append(
            "VERDICT: heavily collinear. The four components are largely one "
            "factor; the weights are dividing up a single signal rather than "
            "combining independent ones. Real diversification would need inputs "
            "from another dimension — volume, relative strength, volatility "
            "regime — not four more price-derived windows."
        )
    elif mean_abs > 0.4:
        lines.append(
            "VERDICT: moderately collinear, as expected for price-derived "
            "measures over similar windows. Some genuine diversification, but "
            "less than four independent inputs would suggest."
        )
    else:
        lines.append("VERDICT: components carry meaningfully distinct information.")
    return corr, "\n".join(lines)
