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
│   └── Deterministic_Trend_Detector.pine   # trend classifier + visuals/alerts
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
3. **Choppiness Index** — a ranging-market filter that blocks new trend calls
   while conditions are choppy (it does not cancel an established trend).
4. **Swing structure (Dow Theory)** — higher-highs/higher-lows vs
   lower-highs/lower-lows from confirmed pivots.
5. **Moving-average geometry** — fast/mid/slow stack order + slow-MA slope.

The five votes sum to a score from -5 to +5, which drives a sticky state
machine with hysteresis: entering a trend needs the score to reach
`weakThresh`, leaving it needs the score to fall back to the looser
`exitThresh`, and the state only advances on a closed bar. Every formula and
threshold is documented in `METHODOLOGY.md`.

### Signal-accuracy behavior (v2)

Both scripts were revised to make the printed signal match the underlying
math more honestly:

- **No intrabar flicker.** With `confirmOnClose` on (default), the state
  advances only on closed bars, so a label or alert can't appear mid-bar and
  then disappear before the bar closes.
- **Hysteresis instead of a single boundary.** One point of score noise no
  longer flips the label (and fires an alert) on back-to-back bars.
- **Choppiness filters entries, not established trends**, so a transient chop
  spike during a pullback no longer hides a strong trend. The table reports
  chop status separately under "New entries".
- **Alerts fire on direction changes**, not strength upgrades — an
  Uptrend → Strong Uptrend move no longer re-fires "entered an UPTREND".
- **Bug fix:** a zero-range Choppiness window returned `0`, the *trending* end
  of the scale, making a dead-flat window read as a perfect trend. It now
  returns `na`.

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
- Backtest results are for research only and are not a guarantee of future
  performance. This is not financial advice.

## Requirements

- TradingView with Pine Script v6 support (any modern free or paid plan can
  run and backtest these scripts).
