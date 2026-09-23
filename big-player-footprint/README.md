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

## Step-by-step: how to use it

**1. Install**
1. TradingView → **Pine Editor** (bottom of the chart) → *Open* → *New blank indicator*.
2. Delete everything in the editor and paste the whole of
   `indicators/Big_Player_Footprint.pine`.
3. Click **Save**, then **Add to chart**. The indicator draws on the **price
   chart itself**. It does not add a separate pane underneath.

**2. Let it load enough history**
* Signals only start after 100 bars of warm-up, and the self-learning filter
  needs about 20 finished trades per setup. Scroll left or zoom out so the chart
  has a few thousand bars loaded.
* Any timeframe works. 15m–4h and daily give the most useful number of
  signals.

**3. Find the signals**
* A green **BUY** label under a candle is a buy signal. A red **SELL** label
  over a candle is a sell signal.
* On the default *Balanced* setting a signal appears about **once every 80
  bars**. A normal screen shows 100–200 bars, so there may be only one or two in
  view. **Zoom out** to see more.
* The dark **status label** to the right of the last candle always says:
  * when the last signal was, and at what price
  * whether a BUY or SELL is **armed**, and the closing price that will
    trigger it
  * the running win rate against random entries

  So an empty screen does not mean the indicator is broken.

**4. Read a signal before acting on it**
* **Hover over the BUY/SELL label.** The tooltip shows the setup type, the
  conviction score, and the entry, stop and target.
* It also shows how that setup has performed **on this chart so far**, and
  whether all signals together beat random entries. A z-score of 2 or more
  means the difference is unlikely to be luck.
* The dashed red and green lines are the stop and target of the latest signal.

**5. Trade it**
* **Entry:** the close of the signal candle. Signals only print once the
  candle has closed, and they never disappear afterwards.
* **Stop:** 1.5 × ATR away (the red dashed line).
* **Target:** 1.5 × the risk (the green dashed line).
* **Time limit:** if neither is hit within 30 bars, the indicator scores the
  trade at the market price, and you should consider closing it.

**6. Set alerts** (so you don't have to watch the chart)
* Right-click the chart → **Add alert** → Condition: *Big Player Footprint* →
  choose **FBPF · Long signal** or **FBPF · Short signal** → *Once per bar
  close*.
* Or choose **Any alert() function call** to get one alert that includes
  entry, stop and target.

**7. Adjust how many signals you get** (Settings → ① Signals → *Signal frequency*)

| Setting | Signals (tested on 15 datasets) | Edge over random |
| --- | --- | --- |
| Conservative | ~1 per 190 bars | strongest per signal, but very few |
| **Balanced** (default) | ~1 per 80 bars | about as strong, 2.4× more signals |
| Active | ~1 per 55 bars | weaker |

**8. Check it is working on your market**
* Open the **Data Window** (right toolbar) and hover over the last bar.
  *Record · win %* against *Record · random win %* shows whether this market
  suits the indicator.
* If signals seem to disappear, turn on *⑥ Visuals → Signals muted by the
  self-learning gate*. Grey × marks show setups that qualified but were muted,
  because that setup has been losing on this chart.

### Why you might see no BUY/SELL at all

| Cause | Fix |
| --- | --- |
| Zoomed in; signals are once per ~80 bars | zoom out or scroll back; read the status label |
| Very little history loaded (new listing, tiny timeframe) | use a timeframe with more than ~500 bars of history |
| *Signal frequency* is Conservative | switch to Balanced or Active |
| The self-learning gate muted every setup on this market | turn on the grey × markers to confirm; it means nothing has been working here recently |
| *Require higher-timeframe agreement* is on | set it to Off |
| Looking for a pane below the chart | there isn't one; everything is drawn on the price candles |

### Other marks

| Mark | Meaning |
| --- | --- |
| Cyan / orange candle | **Whale bar**: effort z ≥ 2 (cyan = closed in its upper half, orange = lower half) |
| Liquidity lines, gap boxes, event dots, VWAP | off by default; switch on in ⑥ Visuals |

## How accuracy is handled

1. **Non-repainting.** Signals print on closed bars, and the higher timeframe is
   read from its last *completed* bar. Liquidity levels are confirmed pivots. A
   signal that has printed does not move or disappear.
2. **Confirmation.** Sweeps and absorption must be followed within 3 bars by a
   close beyond the event bar's far extreme. Tests showed removing this clearly
   hurts.
3. **Conviction gate.** Each candidate is graded 0–100 on effort, flow,
   higher-timeframe trend, location vs VWAP, and whether the opposite side's
   stops were just taken. Only grades at or above the preset's minimum print
   (Conservative 60, Balanced 40, Active 25).
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
| v1 (first version) | first 60% | 1329 | −1.6 pp | −0.03 R | 8 / 15 |
| v1 (first version) | last 40% | 843 | +1.0 pp | +0.03 R | 7 / 13 |
| Conservative | first 60% | 681 | +0.0 pp | +0.01 R | 9 / 15 |
| Conservative | last 40% | 447 | +3.1 pp | +0.07 R | 7 / 12 |
| **Balanced (default)** | first 60% | 1719 | +0.2 pp | +0.01 R | 8 / 15 |
| **Balanced (default)** | last 40% | 973 | **+3.0 pp** | **+0.08 R** | 10 / 13 |
| Active | first 60% | 2421 | −1.3 pp | −0.04 R | 8 / 15 |
| Active | last 40% | 1557 | +1.5 pp | +0.02 R | 9 / 15 |

What these results support:

* The current version beat v1 in both periods, and the two new features each
  helped on their own.
* Balanced gives about 2.4× more signals than Conservative with a similar edge.
  Going beyond Active weakens the edge further.
* The edge is **small** and varies a lot by market. On Balanced, over the last 40%:
  * gold daily, EURUSD hourly (with and without volume), ORCL and BTC daily
    were above random
  * SPY daily, NVDA and AAPL daily were below random
  * no single dataset reached z ≥ 2 on its own; the edge only shows up when the
    datasets are pooled
* A hard higher-timeframe filter did not improve both periods, so it stays
  optional.
* No commissions or slippage are included.

Run `python3 research/experiments.py` to reproduce these numbers. On your own
chart, trust the tooltip and Data Window record over any of these figures.

---

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
