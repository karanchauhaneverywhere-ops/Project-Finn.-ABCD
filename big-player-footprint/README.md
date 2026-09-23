# Big Player Footprint (FBPF)

A TradingView indicator, written in **Pine Script v6**, that looks for the marks
large orders leave on a chart, turns them into long/short signals, and **grades
its own accuracy** on whatever chart you load it on.

| File | What it is |
| --- | --- |
| `indicators/Big_Player_Footprint.pine` | The indicator: overlay, signals, alerts, live panel and self-scoring scoreboard. |
| `METHODOLOGY.md` | Every formula and threshold, and why each one is there. |
| `research/reference_port.py` | A bar-by-bar Python port of the same logic, used to test it on real data outside TradingView. |

---

## Read this first: what "identifying big players" can and cannot mean

No indicator can see **who** is trading. Exchanges do not publish that, and a
price/volume chart does not contain it. Any tool claiming to show "the whales'
orders" from OHLCV is guessing and presenting the guess as fact.

What a chart *does* contain is the footprint that size cannot fully hide:

| Footprint | What large size has to do | How FBPF measures it |
| --- | --- | --- |
| **Effort** | trade far more volume than usual for that time | log-volume z-score against the same time of day (intraday) or a rolling baseline |
| **Liquidity** | find the other side, and resting stops beyond swing highs/lows are the biggest pool of it | confirmed swing pivots tracked as liquidity levels; a wick through that closes back inside is a **sweep** |
| **Absorption** | a passive buyer/seller soaks up aggressive orders: lots of volume, little movement | high volume z with a narrow range at the edge of the recent range |
| **Initiative** | an aggressive order moves price further than normal in one bar | wide, full-bodied displacement bar that leaves a fair-value gap |
| **Net flow** | persistent buying/selling shows up before price moves | net signed volume over N bars as a fraction of all volume; divergence from price = accumulation / distribution |

So "big player move" here means **a move with the footprint of size behind it**.
It does not mean confirmed institutional activity.

---

## Accuracy: how it is handled

Two tools can make an indicator look accurate: repainting, and quoting a win
rate without saying what random entries would have scored. This one does
neither.

1. **Non-repainting by default.** Signals are emitted on closed bars. The
   higher timeframe is read with the documented `expr[1]` + `lookahead_on` form.
   Liquidity levels are confirmed pivots. An arrow that has printed does not
   move or disappear.
2. **Precision over frequency.** A raw footprint event does not trigger
   anything by itself:
   * sweep and absorption events must be **confirmed**: a close beyond the event
     bar's far extreme within 3 bars, cancelled if price closes beyond its near
     extreme first.
   * every setup is graded 0–100 on five independent confluence factors, and
     only setups at or above **minimum conviction** (default 60) print.
   * a cooldown stops clusters of signals, and opposing signals on the same bar
     cancel each other.
3. **It measures itself.** Every signal becomes a virtual trade (entry at the
   signal close, stop 1.5 ATR, target 1.5 R, closed at market after 30 bars).
   **On every bar**, the indicator also opens a random long and a random short
   with the *identical* rules. The panel shows:
   * win rate and average R per setup, and for all longs and all shorts
   * the same numbers for random entries on this chart
   * the difference in percentage points, and a **z-score**. Only |z| ≥ 2
     (marked ✓) is a difference you should treat as more than noise.
   * the break-even win rate for your target (`1 / (1 + R)`)

   The scoring is deliberately conservative. If one bar touches both stop and
   target, it counts as a loss. A gap through the stop is scored at the open,
   which is worse than −1 R.

**How to push accuracy up on your market:** raise *Minimum conviction* in steps
of 5 and watch the scoreboard. Stop when the win rate no longer improves or the
signal count gets too small to trust (a few dozen signals is the least worth
reading). Disable any setup whose row does not beat random on your
market/timeframe. A lower R target raises win rate mechanically without adding
any edge, so compare **average R** and **vs random** instead.

---

## What the port measured on real data

`research/reference_port.py` runs the same logic on the two real datasets that
ship with the `backtesting` PyPI package, with default settings and nothing
tuned to them:

| Data | Side | Signals | Win % | Avg R | Random win % | Random avg R | z |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| EURUSD 1h, 2017–18 | long | 35 | 45.7 | +0.31 | 40.7 | +0.06 | +0.60 |
| EURUSD 1h, 2017–18 | short | 17 | 41.2 | +0.09 | 36.0 | −0.08 | +0.44 |
| GOOG 1D, 2004–13 | long | 8 | 50.0 | +0.24 | 48.8 | +0.20 | +0.07 |
| GOOG 1D, 2004–13 | short | 3 | 33.3 | −0.20 | 33.3 | −0.23 | 0.00 |

What these results support: on these samples, signals did somewhat better than
random entries under the same rules. None of the differences are statistically
significant. The samples are small, and daily charts produce very few signals.
Absorption almost never met all of its conditions. Raising the conviction gate
cut signals sharply without a consistent gain in win rate. That is why the
default stayed at 60 and the choice is left to your own chart's scoreboard.
These numbers are a sanity check, not a performance claim.

---

## Installing

1. TradingView → **Pine Editor** → *Open* → *New blank indicator*.
2. Replace the template with the contents of
   `indicators/Big_Player_Footprint.pine`.
3. **Save** → **Add to chart**.

No libraries, no imports.

---

## Reading the chart

| Mark | Meaning |
| --- | --- |
| Cyan / orange candle | **Whale bar**: volume z ≥ 2 (cyan closed in its upper half, orange in its lower half) |
| Dotted red line from a swing high | Buy-side liquidity: resting buy-stops above. Turns grey and stops when taken |
| Dotted green line from a swing low | Sell-side liquidity: resting sell-stops below |
| Small circle | Raw liquidity sweep (not yet a signal) |
| Small square | Raw absorption bar (not yet a signal) |
| Green / red box | Fair-value gap left by a displacement bar, extended while it is watched |
| Grey line | Rolling VWAP |
| `▲ SWEEP 72` label | Long signal: setup type and conviction. Hover for entry, stop and target |
| Dashed lines after a signal | Stop and target of the latest signal |

## Reading the panel

```
BIG PLAYER FOOTPRINT        EURUSD                60
LIVE FOOTPRINT              READING
Volume z (effort)           2.41  ► █████   t-o-d   WHALE
Effort vs result            ABSORPTION      range  0.62 atr
Net delta 20b               11.3% ► ███··   approx
Flow vs price               ACCUMULATION       px -0.84 atr
HTF trend 240               0.38  ► ██···
vs rolling VWAP             discount              -1.12 atr
Stops above / below         1.08412                 1.07935
Watching                    SWEEP long > 1.08101   —
SCOREBOARD (this chart)     SIGNALS  WIN %   AVG R  vs RANDOM
A Sweep & reclaim           …
```

`Watching` shows an armed setup waiting for its confirmation close, or a live
fair-value gap waiting for its retest. It tells you what could fire next and
at what price.

## Alerts

`Long signal`, `Short signal`, `Whale bar`, `Sell-side / Buy-side liquidity
swept`, `Accumulation`, `Distribution`. With **Any alert() function call**, the
long and short signals also send a message that includes the setup, conviction,
entry, stop and target.

---

## Tuning

| Situation | Adjust |
| --- | --- |
| Want fewer, cleaner signals | raise *Minimum conviction*; raise *Confirmation window* only if sweeps confirm late |
| Too few signals on daily/weekly | lower *Liquidity pivot · left bars* to 5, lower *Minimum conviction* to 50, and judge by the scoreboard |
| Market with no real volume (some FX/CFD/index feeds) | nothing: effort and flow are dropped from the conviction denominator automatically, and the panel says so |
| Intraday equities / futures | leave *Volume baseline* on Auto (time-of-day), which stops the open and close being flagged as whales every day |
| You have intrabar data | set *Delta source* to lower-timeframe intrabars. Older history still uses the approximation, and the panel shows coverage |
| One setup underperforms on your market | turn it off in ③ |

Research and education only. Not financial advice.
