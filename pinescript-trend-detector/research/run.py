#!/usr/bin/env python3
"""CLI for the path geometry research harness.

    python run.py backtest     --csv data.csv
    python run.py walkforward  --csv data.csv --splits 5
    python run.py sensitivity  --csv data.csv
    python run.py mae          --csv data.csv
    python run.py collinearity --csv data.csv
    python run.py all          --csv data.csv

Omit --csv to run against generated synthetic data, which verifies the harness
works but says nothing about the strategy.
"""

from __future__ import annotations

import argparse
import sys

import pandas as pd

from pgt.analysis import (
    component_collinearity,
    mae_analysis,
    sensitivity,
    summarise_sensitivity,
    summarise_walk_forward,
    walk_forward,
)
from pgt.backtest import TradeParams, metrics, run_backtest
from pgt.data import load_csv, synthetic
from pgt.engine import EngineParams

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 40)


def _rule(title: str) -> None:
    print(f"\n{'=' * 78}\n{title}\n{'=' * 78}")


def _load(args) -> pd.DataFrame:
    if args.csv:
        df = load_csv(args.csv)
        print(f"Loaded {len(df)} bars from {args.csv} "
              f"({df.index[0]} .. {df.index[-1]})")
    else:
        df = synthetic()
        print(f"Loaded {len(df)} bars of SYNTHETIC data — harness smoke test only.")
        print("Nothing about strategy performance can be concluded from this.")
    return df


def cmd_backtest(df, ep, tp) -> None:
    _rule("BACKTEST")
    trades, _ = run_backtest(df, ep, tp)
    m = metrics(trades, df, tp)
    for k, v in m.items():
        print(f"  {k:<22} {v:>12.2f}" if isinstance(v, float) else f"  {k:<22} {v:>12}")
    if m["trades"] < 30:
        print("\n  WARNING: fewer than 30 trades. Nothing here is a reliable")
        print("  estimate of anything; treat every number above as anecdote.")
    if m["net_return_pct"] < m["buy_hold_pct"]:
        print("\n  NOTE: underperformed buy-and-hold on this data. A trend system")
        print("  that does not beat simply holding has not earned its complexity.")


def cmd_walkforward(df, ep, tp, splits: int) -> None:
    _rule(f"WALK-FORWARD ({splits} segments)")
    wf = walk_forward(df, ep, tp, splits)
    if wf.empty:
        print("  Not enough data to split.")
        return
    show = ["segment", "bars", "trades", "net_return_pct", "buy_hold_pct",
            "win_rate_pct", "profit_factor", "max_drawdown_pct"]
    print(wf[show].to_string(index=False, float_format=lambda x: f"{x:,.2f}"))
    print("\n" + summarise_walk_forward(wf))


def cmd_sensitivity(df, ep, tp) -> None:
    _rule("PARAMETER SENSITIVITY")
    grid = {
        "er_len": [10, 15, 20, 25, 30],
        "don_len": [10, 15, 20, 25, 30],
        "enter_thresh": [30.0, 40.0, 50.0],
    }
    print(f"  Grid: {grid}")
    sens = sensitivity(df, grid, ep, tp)
    if sens.empty:
        print("  No valid combinations.")
        return
    print("\n  Best 5 by net return:")
    print(sens.nlargest(5, "net_return_pct")[
        list(grid) + ["trades", "net_return_pct", "profit_factor", "max_drawdown_pct"]
    ].to_string(index=False, float_format=lambda x: f"{x:,.2f}"))
    print("\n  Worst 5:")
    print(sens.nsmallest(5, "net_return_pct")[
        list(grid) + ["trades", "net_return_pct", "profit_factor", "max_drawdown_pct"]
    ].to_string(index=False, float_format=lambda x: f"{x:,.2f}"))
    print("\n" + summarise_sensitivity(sens))


def cmd_mae(df, ep, tp) -> None:
    _rule("MAE / MFE — EMPIRICAL STOP CALIBRATION")
    trades, _ = run_backtest(df, ep, tp)
    frame, summary = mae_analysis(trades, tp)
    if not frame.empty:
        print(frame.describe()[["mae_atr", "mfe_atr", "net_return_pct"]]
              .to_string(float_format=lambda x: f"{x:,.2f}"))
        print()
    print(summary)


def cmd_collinearity(df, ep) -> None:
    _rule("COMPONENT COLLINEARITY")
    corr, summary = component_collinearity(df, ep)
    print(corr.to_string(float_format=lambda x: f"{x:,.2f}"))
    print("\n" + summary)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command",
                    choices=["backtest", "walkforward", "sensitivity", "mae",
                             "collinearity", "all"])
    ap.add_argument("--csv", help="OHLC CSV; omit for synthetic smoke-test data")
    ap.add_argument("--splits", type=int, default=5)
    ap.add_argument("--er-len", type=int, default=20)
    ap.add_argument("--don-len", type=int, default=20)
    ap.add_argument("--enter", type=float, default=40.0)
    ap.add_argument("--strong", type=float, default=70.0)
    ap.add_argument("--exit", dest="exit_thresh", type=float, default=15.0)
    ap.add_argument("--atr-mult", type=float, default=2.5)
    ap.add_argument("--cost-bps", type=float, default=5.0,
                    help="Cost per side in basis points (default 5 = 0.05%%)")
    ap.add_argument("--long-only", action="store_true")
    args = ap.parse_args(argv)

    ep = EngineParams(er_len=args.er_len, don_len=args.don_len,
                      enter_thresh=args.enter, strong_thresh=args.strong,
                      exit_thresh=args.exit_thresh)
    tp = TradeParams(atr_stop_mult=args.atr_mult, cost_bps_per_side=args.cost_bps,
                     allow_short=not args.long_only)

    try:
        ep.validate()
    except ValueError as exc:
        print(f"Invalid parameters: {exc}", file=sys.stderr)
        return 2

    df = _load(args)

    if args.command in ("backtest", "all"):
        cmd_backtest(df, ep, tp)
    if args.command in ("walkforward", "all"):
        cmd_walkforward(df, ep, tp, args.splits)
    if args.command in ("sensitivity", "all"):
        cmd_sensitivity(df, ep, tp)
    if args.command in ("mae", "all"):
        cmd_mae(df, ep, tp)
    if args.command in ("collinearity", "all"):
        cmd_collinearity(df, ep)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
