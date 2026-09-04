# Deterministic Trend Detector (Pine Script)

A Pine Script v6 toolkit that classifies a market as **Strong Uptrend /
Uptrend / Sideways-Range / Downtrend / Strong Downtrend** using only
closed-form, deterministic mathematics — no probability distributions,
statistical inference, Bayesian models, Monte Carlo simulation, or
machine-learning probability scores anywhere in the logic.

A companion VWAP indicator adds the axis the classifier lacks — *location*,
not direction — and reports whether the two agree. See
[`METHODOLOGY.md`](./METHODOLOGY.md) for the full math behind every component
and why each one qualifies as deterministic rather than probabilistic.

## What's here

```
pinescript-trend-detector/
├── indicators/
│   ├── Deterministic_Trend_Detector.pine   # trend classifier + visuals/alerts
│   └── VWAP_Confluence.pine                # VWAP value layer + alignment/value entries
├── strategies/
│   └── Deterministic_Trend_Strategy.pine   # same classifier wired to entries/exits
├── METHODOLOGY.md                          # formulas + rationale, component by component
└── README.md                               # this file
```

## How the classification works (summary)

Five independent, deterministic components each cast a vote of `+1`
(bullish), `-1` (bearish), or `0` (no signal):

1. **Regression slope + R²** — least-squares slope of price, ATR-normalized,
   trusted only when the fit is linear enough (R² above a threshold).
2. **Wilder DMI/ADX** — classical directional-movement strength/direction.
3. **Choppiness Index** — a ranging-market filter that can force a
   "Sideways / Range" label outright.
4. **Swing structure (Dow Theory)** — higher-highs/higher-lows vs
   lower-highs/lower-lows from confirmed pivots.
5. **Moving-average geometry** — fast/mid/slow stack order + slow-MA slope.

The five votes sum to a score from -5 to +5, which is mapped to a label by
fixed thresholds (all tunable via script inputs). Every formula and
threshold is documented in `METHODOLOGY.md`.

## Using the indicator

1. Open [TradingView](https://www.tradingview.com/), open any chart, then
   open the **Pine Editor** (bottom panel).
2. Create a new script, paste in the contents of
   `indicators/Deterministic_Trend_Detector.pine`, and click **Add to
   chart**.
3. On the chart you get:
   - the regression line and the fast/mid/slow moving averages overlaid on
     price,
   - background shading that follows the current trend state,
   - triangle markers on confirmed swing pivots,
   - a breakdown table (top-right) showing the current label, composite
     score, strength %, each component's reading, and how many bars the
     current state has held.
4. Right-click the chart → **Add alert**, and pick one of the built-in
   alert conditions (entered uptrend / entered downtrend / entered sideways
   / any state change) to get notified on trend transitions.

All lengths and thresholds (regression window, ADX/DI lengths, Choppiness
window and thresholds, pivot lookback, MA lengths/type, and the score
thresholds that separate "Trend" from "Strong Trend") are exposed as inputs
so the classifier can be tuned per instrument and timeframe.

## Using the VWAP indicator

### In plain English

VWAP is the average price everyone actually traded at today, weighted by how
much traded at each price. Think of it as **today's fair price**.

Your trend detector already tells you *which way the market is going*. It does
not tell you *whether right now is a good price to get in at*. So it can put
you into a good uptrend at a bad price — right after a big run, just before a
pullback. That gap is where a lot of give-back comes from.

This indicator fills it. Simple version:

> **Trade in the direction your trend detector confirms — but wait to get in
> until price comes back to fair value.**

That is the whole idea. Everything else in the script is bookkeeping for it.

### The one row that matters

Add the script (Pine Editor → paste → **Add to chart**) and you get a small
table. The top row is the answer:

| Bottom line | What it means |
| --- | --- |
| **Look for BUYS** | Trend is up *and* price/VWAP agree. Buy the next pullback to VWAP. |
| **Look for SELLS** | Trend is down *and* price/VWAP agree. Sell the next bounce to VWAP. |
| **Stand aside - signals disagree** | Trend says one thing, VWAP says the other. Usually worth skipping. |
| **No clear edge right now** | No confirmed trend. Nothing to do. |

The second row, "Right now", tells you what it's waiting for — *"Waiting for a
pullback down to VWAP"*, *"At VWAP - waiting for it to hold"*, or
*"BUY - bounced off VWAP"* when a signal actually fires. Between those two
rows you can read the whole state without knowing any of the math.

The rest of the table is supporting detail in the same plain language:

- **Trend** — Up / Up (strong) / Sideways / Down / Down (strong)
- **Price vs VWAP** — above, below, or right at fair value
- **Fair value is** — rising, falling, or flat (price above a *falling* VWAP is
  a very different situation from price above a rising one)
- **Position** — near fair value, extended, or very stretched
- **Agreement** — how many of the 8 underlying checks point the same way

Set **Table detail** to *Full* in the settings if you want the raw numbers
(VWAP price, distance, the two scores) added underneath. They are always in
the Data Window either way.

### The markers

`VWAP+` under a bar means: the trend was confirmed up, price pulled back and
touched VWAP, and this bar closed back above it. `VWAP-` is the mirror image.
Those are the entries — same direction your strategy would have taken, but
bought at fair value instead of wherever the score happened to cross.

### Settings

Only three groups matter to start:

- **Main settings** — how often VWAP resets (Session = each trading day, the
  usual choice for day trading; pick a longer one for swing trading).
- **Buy / sell signals** — how strict the pullback and reclaim have to be.
- **Chart display** — what to show, and how much table detail.

Everything prefixed **Advanced** can be left alone. The "Advanced trend
engine" groups are the same settings as `Deterministic_Trend_Detector.pine`
and mean exactly what they mean there — only change them if you've already
tuned that indicator and want this one to match.

### How it fits your existing strategy

Two ways to use it:

- **As a filter.** Take your strategy's entries only when the bottom line
  agrees. "Stand aside" is the state worth respecting: the trend label is
  still up, but people are trading *below* a falling fair value.
- **As the entry trigger.** Use the `VWAP+` / `VWAP-` markers instead of the
  raw score cross. Same direction, better price.

### Under the hood

The script re-runs your identical five-component trend engine in-file, so the
trend it reports matches the detector bar-for-bar. (It duplicates the engine
for the same reason the strategy does: TradingView scripts can't share code
without publishing a separate Pine library.)

On top of that it adds three readings of its own, each casting the same
`+1` / `0` / `-1` vote the trend components use:

1. **Side** — is price above or below VWAP, beyond a small dead zone so price
   sitting right on VWAP doesn't flicker between readings.
2. **Slope** — is fair value itself rising or falling.
3. **Position** — at value, participating away from value, or extended.

Those sum to a VWAP score in `[-3, +3]`, which adds to the trend score for the
"Agreement" row's `[-8, +8]`. On the chart you also get the VWAP line coloured
by the bottom line, three bands either side, and the previous period's closing
VWAP as a stepped line — a level that often acts as support or resistance in
the next period.

Full math and the reasoning behind each choice is in
[`METHODOLOGY.md`](./METHODOLOGY.md).

### Two things it deliberately does not claim

- **The bands are not confidence intervals.** Sigma here is just how far price
  normally strays from VWAP since the reset, measured from the bars in front
  of you. The familiar "2 sigma ≈ 95% of the time" reading needs price moves
  to follow a normal distribution, which they demonstrably don't — that's why
  this toolkit avoids probability claims in the first place. Treat the bands
  as distance markers, nothing more.
- **Hitting the outer band is not a reversal signal.** The script reports it
  as "very stretched" and casts no directional vote. Calling it a reversal
  would be a bet that price snaps back often enough to pay, which is exactly
  the kind of claim this toolkit doesn't make.

### What it costs you

If a trend never pulls back to VWAP, no marker fires and you miss the move
entirely. That's the real price of insisting on a good entry, and it's the
main thing to check before wiring the markers into a rule: see how often your
instrument actually returns to value versus how often it just runs.

It also needs a symbol with volume data. Without it a volume-weighted average
is *undefined*, not merely noisy — the table says so outright rather than
drawing a misleading line.

## Using the strategy

`strategies/Deterministic_Trend_Strategy.pine` reuses the identical
five-component engine (duplicated in-file, since Pine strategies and
indicators can't share code without publishing a separate Pine *library* on
TradingView) and wires it to orders. As of **v2**, the order-management layer
was reworked specifically to reduce whipsaw/give-back costs:

- **Entry/exit hysteresis.** Entries require the score to reach `weakThresh`;
  an open position only closes once the score falls back to the separate,
  looser `exitThresh` (default 0). v1 used the same threshold for both,
  so a single point of noise could flip a position open and shut on
  consecutive bars.
- **Choppiness Index is now an entry filter, not an exit trigger.** A chop
  spike blocks *new* entries but no longer force-closes an existing
  position — v1 would flatten a strong trend on a transient chop reading
  during a normal pullback.
- **Chandelier-style ATR trailing stop.** The stop is seeded at entry and
  only ever ratchets in the trade's favor (never loosens), so it bounds
  initial risk *and* locks in open profit, instead of relying solely on
  the lagging score-flip exit.
- **Optional higher-timeframe filter** (`Higher-Timeframe Filter` group,
  off by default): requires price to be above/below a higher-timeframe EMA
  before allowing longs/shorts respectively. Turn this on if the Strategy
  Tester's long/short breakdown shows one side is the P&L drag (e.g.
  countertrend shorts losing money against a persistent higher-timeframe
  uptrend).
- Uses fixed-fractional percent-of-equity position sizing — a deterministic
  capital-allocation rule, not a win-probability-based scheme like the
  Kelly criterion.

Add it to a chart the same way (paste into Pine Editor → Add to chart), then
use TradingView's **Strategy Tester** tab — check the **Performance
Summary**'s Long/Short breakdown specifically before tuning further — and
adjust commission/slippage inputs at the top of the script to match your
broker before drawing any conclusions from the results.

## Limitations, honestly stated

- The swing-structure component can only confirm a pivot `pivotRight` bars
  after it forms — a bounded, disclosed lag, not repainting of already-set
  values.
- Every component looks backward over a finite window; nothing in this
  toolkit predicts future price. A trend *label* describes price geometry
  that has already happened, up to the confirmation lag above.
- VWAP needs a volume feed, and its value depends on where the anchor was
  placed — two traders using different anchors get different "fair values",
  and neither is more correct. Its deviation bands are distance markers, not
  confidence intervals; see the VWAP section above.
- Insisting on a pullback to value means trends that never return to VWAP
  produce no value-entry signal at all. That missed-move cost is real and
  should be measured against your instrument, not assumed away.
- Backtest results are for research only and are not a guarantee of future
  performance. This is not financial advice.

## Requirements

- TradingView with Pine Script v6 support (any modern free or paid plan can
  run and backtest these scripts).
