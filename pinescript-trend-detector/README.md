# Deterministic Trend Detector (Pine Script)

A Pine Script v6 toolkit that classifies a market as **Strong Uptrend /
Uptrend / Sideways-Range / Downtrend / Strong Downtrend** using only
closed-form, deterministic mathematics — no probability distributions,
statistical inference, Bayesian models, Monte Carlo simulation, or
machine-learning probability scores anywhere in the logic.

See [`METHODOLOGY.md`](./METHODOLOGY.md) for the full math behind every
component and why each one qualifies as deterministic rather than
probabilistic.

## What's here

```
pinescript-trend-detector/
├── indicators/
│   └── Path_Geometry_Trend_Detector.pine   # trend classifier + trade overlay
├── strategies/
│   └── Deterministic_Trend_Strategy.pine   # entries/exits (older engine — see note)
├── METHODOLOGY.md                          # formulas + rationale for both engines
├── AUDIT.md                                # known defects and their status
└── README.md                               # this file
```

> ### ⚠ The indicator and the strategy currently use different engines
>
> The indicator was rewritten onto the **path geometry** engine described
> below. The strategy still runs the older **five-vote** engine (least-squares
> regression, Wilder ADX, Choppiness Index, swing pivots, moving averages),
> documented in `METHODOLOGY.md` Part A.
>
> They do not measure the same thing, so **the indicator's entry markers are
> not a preview of the strategy's trades right now.** Porting the strategy onto
> the new engine is the outstanding work; until then, run them as two separate
> tools rather than as a matched pair.

## How the classification works (summary)

The premise: **a trend is a path that covers ground efficiently in one
direction; a range is a path that travels just as far and arrives nowhere.**
That is measurable directly from the price path — no line fitting, no
smoothing, and no moving averages anywhere in the engine.

Four components, each normalized to `[-1, +1]`:

1. **Signed Efficiency Ratio** — net displacement ÷ total path length over
   `erLen` bars. A straight line up scores +1, a straight line down −1,
   thrashing that returns to its origin 0. One number carrying both direction
   and straightness.
2. **Breakout structure** — `donLen`-bar channel breaks, held until the
   opposite band breaks. Confirms on the breaking bar itself, unlike swing
   pivots, which cannot confirm until N later bars have closed.
3. **Range position** — where price sits inside its own recent high-low range,
   measured from the midpoint. Directional bias with no averaging lag.
4. **Displacement balance** — (up closes − down closes) ÷ window. A pure count,
   so it can't be dominated by one outsized bar the way an average can.

These are combined by weighted average into a **Trend Score of −100 to +100**.
Because every component shares the same scale, the weights mean exactly what
they say, and a component's contribution is proportional to its strength
rather than being flattened into a ±1 vote.

A **compression gate** (range now vs range before) blocks *new* trend calls
while the market is coiling, without cancelling an established trend.

The score drives a sticky state machine with hysteresis: entering a trend
needs `|score| ≥ enterThresh`, leaving needs it to fall below the looser
`exitThresh`, and the state only advances on a closed bar. Full formulas are
in `METHODOLOGY.md` Part B.

**Warmup is 40 bars** with the defaults, against ~210 for the previous engine,
which needed a 200-period moving average before it could produce anything.

### Signal discipline

Three behaviours carry over from the previous engine because they were fixes
for real problems, and they are independent of how the trend is measured:

- **No intrabar flicker.** With `confirmOnClose` on (default), the state
  advances only on closed bars, so a label or alert can't appear mid-bar and
  then disappear before the bar closes.
- **Hysteresis, not a single boundary.** Entering a trend and leaving it use
  different thresholds, so noise around one level can't flip the label — and
  fire an alert — on back-to-back bars.
- **Alerts fire on direction changes**, not strength upgrades: an
  Uptrend → Strong Uptrend move doesn't re-fire "entered an uptrend".

## Using the indicator

1. Open [TradingView](https://www.tradingview.com/), open any chart, then
   open the **Pine Editor** (bottom panel).
2. Create a new script, paste in the contents of
   `indicators/Path_Geometry_Trend_Detector.pine`, and click **Add to chart**.
3. On the chart you get:
   - the **breakout channel** (the `donLen` high/low bands whose breaks drive
     the structure component),
   - **background shading** following the current trend state,
   - the **trade overlay** — entry labels, a ratcheting stop line, exit
     markers (see below),
   - a **breakdown table** (top-right) showing the trend state, the −100..+100
     score, each of the four components' current readings, the compression
     gate, bars in state, and the simulated position and stop.
4. Right-click the chart → **Add alert** and pick a condition. The three
   trend-state alerts describe market conditions; the four `TRADE:` alerts
   describe entries and exits.

Every length, weight, and threshold is an input. The **component weights** are
the main tuning surface — because all four components share the same
`[-1, +1]` scale, setting a weight to 0 cleanly disables that component and
lets you see what the others are contributing on their own.

### The trade overlay — read this before trading from the chart

**The shaded background is a state, not a signal, and the two are not
interchangeable.** An entry is true for exactly one bar; the background stays
lit for every bar the state holds, which may be dozens. Buying because the
chart is green means entering the same trend far later, at a worse price, and
with no stop — a materially different trade.

So the indicator draws the trade lifecycle explicitly (`Trade Overlay` input
group, on by default):

- **`LONG` / `SHORT` labels** mark the exact bar a trend first qualifies — the
  rising edge, not the ongoing state.
- **A red chandelier stop line** tracks the protective stop, ratcheting in the
  trade's favour and never loosening.
- **`✕` marks a stop exit; `▫` marks a score exit** — the two ways a position
  ends.
- **The table** reports the position ("Long from 1.2345") and the active stop.
- **Four `TRADE:` alert conditions** fire on entries and exits. If you want
  alerts that correspond to trades, use those.

The overlay models no commission or slippage, so its marker prices are
optimistic against real fills.

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
  values. Note that the pivot triangles are drawn *at* the pivot bar, so on
  historical charts they look like perfectly-timed swing calls; nothing was on
  screen at that moment, and reading them as live turning-point signals will
  badly overstate what the tool can do.
- Every component looks backward over a finite window; nothing in this
  toolkit predicts future price. A trend *label* describes price geometry
  that has already happened, up to the confirmation lag above.
- Backtest results are for research only and are not a guarantee of future
  performance. This is not financial advice.

## Requirements

- TradingView with Pine Script v6 support (any modern free or paid plan can
  run and backtest these scripts).
