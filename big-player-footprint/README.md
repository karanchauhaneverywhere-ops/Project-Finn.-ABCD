# Big Player Footprint (FBPF)

A TradingView indicator, written in **Pine Script v6**, that looks for the marks
large orders leave on a chart, turns them into long/short signals, and tracks
its own accuracy on whatever chart you load it on.

| File | What it is |
| --- | --- |
| `indicators/Big_Player_Footprint.pine` | The indicator. |
| `METHODOLOGY.md` | Every formula and threshold, and why each one is there. |
| `research/reference_port.py` | A bar-by-bar Python port of the same logic. |
| `research/datasets.py` | The real-data test bed: 15 datasets across equities, FX, gold and crypto. |
| `research/experiments.py` | Compares configurations on that test bed. |

---

## What "identifying big players" can and cannot mean

No indicator can see **who** is trading. A price/volume chart does not contain
that information. What it does contain is the footprint that size cannot fully
hide:

| Footprint | What large size has to do | How FBPF measures it |
| --- | --- | --- |
| **Effort** | trade far more volume than usual for that time | log-volume z-score against the same time of day (intraday) or a rolling baseline. With no volume feed, range expansion is used instead |
| **Liquidity** | find the other side, and resting stops beyond swing highs/lows are the biggest pool of it | confirmed swing pivots tracked as liquidity levels; a wick through that closes back inside is a **sweep** |
| **Absorption** | a passive buyer/seller soaks up aggressive orders: lots of volume, little movement | high volume z with a narrow range at the edge of the recent range |
| **Initiative** | an aggressive order moves price further than normal in one bar | wide, full-bodied displacement bar that leaves a fair-value gap |
| **Net flow** | persistent buying/selling shows up before price moves | net signed volume over N bars as a fraction of all volume |

So a "big player move" here means **a move with the footprint of size behind
it**. It does not mean confirmed institutional activity.

---

## What you see on the chart

By default the chart shows only three things:

| Mark | Meaning |
| --- | --- |
| `SWEEP` / `ABSORB` / `FVG` label | A signal (green below the bar = long, red above = short). **Hover it** for conviction, entry/stop/target and the track record |
| Dashed red / green lines | Stop and target of the latest signal |
| Cyan / orange candle | **Whale bar**: effort z ≥ 2 (cyan = closed in its upper half, orange = lower half) |

Liquidity levels, fair-value gaps, unconfirmed events and the rolling VWAP can
be switched on in **⑥ Visuals**. They are off by default to keep the chart clean.

### Where the accuracy numbers went

There is no table. The same numbers are in two places:

* **Signal tooltip.** Hover any signal label. It shows that setup's record on
  this chart *up to that signal*: closed trades, win %, average R, and for all
  signals, win % against random entries with a z-score.
* **Data Window.** Shows the running record on any bar you point at: signals
  closed, win %, random win % (same long/short mix), average R, z, and whether
  the self-learning gate muted a setup on that bar.

|z| ≥ 2 is the point where the difference from random entries is unlikely to be
luck.

---

## How accuracy is handled

1. **Non-repainting.** Signals print on closed bars, and the higher timeframe is
   read from its last *completed* bar. Liquidity levels are confirmed pivots. A
   signal that has printed does not move or disappear.
2. **Confirmation.** Sweeps and absorption must be followed within 3 bars by a
   close beyond the event bar's far extreme. Tests showed removing this clearly
   hurts.
3. **Conviction gate.** Each candidate is graded 0–100 on effort, flow,
   higher-timeframe trend, location vs VWAP, and whether the opposite side's
   stops were just taken. Only grades ≥ 60 print.
4. **Self-learning gate (new).** Every qualifying setup is traded virtually in
   the background, whether or not it is shown. After 20 closed outcomes on this
   chart, a setup is shown only while its last 30 outcomes add up to a profit.
   It only uses trades that have already closed, so there is no look-ahead. This
   adapts the indicator to each market instead of assuming one set of setups
   works everywhere.
5. **Works without volume (new).** On feeds with no volume (spot FX, CFDs, many
   index feeds), effort falls back to range expansion. Alternatively, **Borrow
   volume from** a futures contract (e.g. EURUSD → `6E1!`, XAUUSD → `GC1!`,
   US500 → `ES1!`).
6. **Honest scoring.** Each signal becomes a virtual trade: stop 1.5 ATR, target
   1.5 R, closed at market after 30 bars. A bar touching both stop and target
   counts as a loss, and a gap through the stop is scored at the open. A random
   long and short are opened on every bar with the same rules for comparison.

---

## Measured on real data

The Python port was run on **15 real datasets**:

* US equities, daily: SPY, AAPL, IBM, NVDA, ORCL, YHOO, GOOG
* US equities, hourly: SPY, AAPL
* FX: EURUSD hourly, once with tick volume and once without volume
* Gold: XAUUSD daily, no volume
* Crypto: BTCUSD daily, plus 5-minute and 1-minute bars

Features were chosen on the **first 60%** of each dataset and checked on the
**last 40%**. Edges are against random entries with the same rules and the same
long/short mix:

| Configuration | Period | Signals | Win-rate edge | Avg-R edge | Datasets with positive R edge |
| --- | --- | ---: | ---: | ---: | ---: |
| v1 (previous defaults) | first 60% | 1329 | −1.6 pp | −0.03 R | 8 / 15 |
| v1 (previous defaults) | last 40% | 843 | +1.0 pp | +0.03 R | 7 / 13 |
| **v2 (current defaults)** | first 60% | 681 | +0.0 pp | +0.01 R | 9 / 15 |
| **v2 (current defaults)** | last 40% | 447 | **+3.1 pp** | **+0.07 R** | 7 / 12 |

What these results support:

* v2 beat v1 in both periods, and the two new features each helped on their own.
* The edge is **small** and varies a lot by market. For the last 40%:
  * gold daily (z +3.7), SPY hourly (+2.0) and IBM daily (+2.3) were clearly above random
  * AAPL daily and the 1-minute crypto data were below random
  * EURUSD hourly without volume was about even
* A hard higher-timeframe filter and a higher conviction gate did not improve
  both periods, so they stay optional.
* No commissions or slippage are included.

Run `python3 research/experiments.py` to reproduce these numbers. On your own
chart, trust the tooltip and Data Window record over any of these figures.

---

## Installing

1. TradingView → **Pine Editor** → *Open* → *New blank indicator*.
2. Replace the template with the contents of
   `indicators/Big_Player_Footprint.pine`.
3. **Save** → **Add to chart**.

## Alerts

`Long signal`, `Short signal`, `Whale bar`, `Sell-side / Buy-side liquidity
swept`, `Accumulation`, `Distribution`. All event alerts fire only on closed
bars. With **Any alert() function call**, the long and short signals also send
the setup, conviction, entry, stop and target.

## Tuning by market

| Situation | Adjust |
| --- | --- |
| Spot FX, CFDs, index feeds without volume | leave *range expansion as effort* on, or better, *Borrow volume from* the matching futures |
| Intraday equities / futures | leave *Volume baseline* on Auto (time-of-day), which stops the open and close being flagged as whales every day |
| Daily/weekly: too few signals | lower *Liquidity pivot · left bars* to 5 and *Minimum conviction* to 50; the self-learning gate still filters losing setups |
| You want only trend-following trades | *Require higher-timeframe agreement* → *All setups* |
| One setup keeps getting muted | it is losing on this market; turn it off in ① |
| Intrabar data available | *Delta source* → lower-timeframe intrabars (older history falls back to the approximation) |

Research and education only. Not financial advice.
