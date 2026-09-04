# Research harness

A Python reimplementation of the path geometry engine, plus the analyses that
Pine cannot perform: walk-forward across periods, parameter grid search, MAE
stop calibration, and component collinearity.

**Why this is not in Pine.** TradingView has no native parameter optimiser, a
script cannot loop over parameter sets within a run, and the Strategy Tester
returns one result per configuration. Walk-forward and sensitivity work needs
to happen outside the platform.

## Quick start

```bash
pip install numpy pandas pytest

cd research
python run.py all --csv your_data.csv        # everything
python run.py backtest     --csv your_data.csv
python run.py walkforward  --csv your_data.csv --splits 5
python run.py sensitivity  --csv your_data.csv
python run.py mae          --csv your_data.csv
python run.py collinearity --csv your_data.csv
```

Omit `--csv` to run against generated synthetic data. That verifies the
harness works; it says **nothing** about the strategy, and the synthetic
series is built with clean alternating regimes that any trend follower would
profit from. Do not read those numbers as encouraging.

## Getting data

The CSV needs `open`, `high`, `low`, `close` columns and ideally a
time/date column. Column naming and case are handled loosely.

In TradingView: right-click the chart → **Export chart data**. Most vendor and
broker exports work as-is.

## What each command answers

| Command | Question |
|---|---|
| `backtest` | What did this configuration do, versus buy-and-hold? |
| `walkforward` | Is the edge present across periods, or carried by one lucky stretch? |
| `sensitivity` | Is this parameter set on a plateau, or a knife-edge fitted to noise? |
| `mae` | Where should the stop actually sit, measured rather than guessed? |
| `collinearity` | Do the four components carry independent information? |

### Reading the sensitivity output

**Do not take the best cell.** The grid exists to check whether the
*neighbourhood* around your chosen parameters is flat. A configuration whose
performance collapses one step away was fitted to noise and will not survive
out of sample. A configuration sitting mid-plateau, even at lower headline
return, is the one to trade.

### Reading the MAE output

Maximum Adverse Excursion is how far each trade went against you before
resolving. If winners rarely draw more than X ATR against you, a stop beyond X
donates room for nothing, and a stop inside X cuts trades that would have
worked. The harness reports the winners' MAE distribution and compares it to
your current `--atr-mult`.

## Parity with the Pine scripts

The engine here mirrors `indicators/Path_Geometry_Trend_Detector.pine`. Places
where that is easy to get wrong, and how it is handled:

- **ATR** uses Wilder's RMA (`alpha = 1/n`), matching `ta.atr`. An SMA of true
  range would shift every stop level and silently decorrelate the harness from
  the chart. Asserted in `tests/test_engine.py`.
- **Breakout channel** shifts by one bar, matching Pine's `[1]`. Without it the
  current bar sits inside its own channel and a break can never register.
- **Entry** is the rising edge of the qualifying condition, not the state.
- **Stop** is seeded at the entry bar and only ratchets.
- **Every component** falls back to `0` when cold, never `NaN` — see `AUDIT.md`
  E1 for why that mattered.

`tests/` asserts these properties. Run `python -m pytest tests/ -q`.

**The tests do not prove parity with the live script.** They prove the port
behaves sensibly and self-consistently. To check real parity, put the
indicator on a chart, read `Trend score` and the component values from the
Data Window on a few specific bars, and compare against this harness on the
same bars of the same data. Do that before trusting any conclusion here.

## On the "no probability assumptions" constraint

That constraint governs **signal generation** — no fitted models, no
distributional assumptions, no probability outputs. It is defensible and the
engine honours it.

It deliberately does **not** govern evaluation. Expectancy, drawdown, the MAE
distribution, and correlation between components are all statistical
quantities, and refusing to compute them would not make the system more
rigorous — it would make it unmeasurable. A deterministic rule set still has
to be measured before anyone risks money on it.
