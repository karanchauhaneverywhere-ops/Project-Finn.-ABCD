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

`indicators/VWAP_Confluence.pine` adds the axis the five trend components
don't cover. All five answer *which way is price going?*; none answer *is
this a good price to act at?* A trend follower that enters the instant its
score crosses a threshold buys wherever price happens to be — often well
extended from any reference value, which is where give-back comes from.

VWAP is the volume-weighted average transaction price since an anchor: a
**location** reference, not a direction forecast. This script pairs the two —
direction from the trend score, location from VWAP — and it re-runs the
identical five-component engine in-file, so the trend label it reports is
the same one the detector shows on the same bar.

Add it the same way (Pine Editor → paste → **Add to chart**). It is designed
to sit on the chart *alongside* the detector: its table defaults to the
bottom-right so it doesn't collide with the detector's top-right one, and it
plots in a blue family that doesn't clash with the detector's MA colors.

### What it puts on the chart

- **VWAP**, colored by alignment (green aligned-long, red aligned-short,
  blue otherwise), with three deviation bands and shaded zones.
- **The previous period's closing VWAP** as a stepped line — a level that
  frequently acts as support/resistance in the next period.
- **Value-entry markers** (`VWAP+` / `VWAP-`): a pullback to VWAP that was
  then reclaimed, taken *only* in the direction the trend engine already
  confirms.
- **A breakdown table** showing the alignment verdict, current setup state,
  the combined score, both underlying scores, each VWAP vote, and the
  anchor's status.

### The three VWAP votes

Each casts `+1` / `0` / `-1` on the same convention the trend engine uses,
summing to a VWAP score in `[-3, +3]`:

1. **Side** — is price accepted above or below VWAP, beyond an ATR dead zone
   (so price sitting on top of VWAP casts no vote rather than flickering).
2. **Slope** — which way fair value itself is moving. Price above a *falling*
   VWAP is a different condition from price above a *rising* one.
3. **Band zone** — at value (inside the inner band) casts 0; participation
   between the inner and outer bands casts a directional vote; beyond the
   outer band casts 0 for *extended*, deliberately not a counter-trend vote
   (see below).

Because both scores are in the same vote units, they sum directly into a
`combinedScore` in `[-8, +8]`, available in the Data Window.

### Alignment, and how to trade it

The table's top row is the point of the script:

| Verdict | Meaning |
| --- | --- |
| **Aligned LONG** | Trend engine says up *and* VWAP location agrees |
| **Aligned SHORT** | Trend engine says down *and* VWAP location agrees |
| **Conflicted** | The two disagree — e.g. a confirmed uptrend while price sits below a falling VWAP |
| **Neutral** | No confirmed trend, or VWAP casts no net vote |

Two practical ways to use it with the existing strategy:

- **As a location filter.** Take the strategy's entries only when alignment
  agrees. "Conflicted" is the specific state worth respecting: the trend
  label is still up, but participants are transacting below a declining
  fair value.
- **As an entry trigger.** Use the `VWAP+` / `VWAP-` markers instead of the
  raw score cross. Same direction, better price — the pullback is bought at
  value rather than at whatever price the score happened to cross at.

### Key inputs

- **Anchor** — Session / Week / Month / Quarter / Year / Custom date /
  Rolling (N bars). Session is the intraday default. Note that an anchored
  mode degenerates on a chart at or above the anchor's own timeframe (a
  "Session" anchor on a daily chart resets every bar); use a lower chart
  timeframe or a longer anchor.
- **Band unit** — volume-weighted sigma (default) or ATR. See the caveat
  below on what sigma does and doesn't mean here.
- **Value entry distances** (`pullbackATR`, `triggerATR`, `invalidATR`) — all
  expressed in ATRs rather than band units, so a pinched band right after an
  anchor reset can't distort the setup logic. Defaults require the bar's low
  to actually reach VWAP and the close to finish back above it.
- **Minimum bars between signals** — a cooldown (default 3) so one extended
  consolidation around VWAP doesn't emit a cluster of near-identical
  signals.

### Two deliberate design choices worth knowing

- **The bands are not confidence intervals.** Sigma here is the
  volume-weighted RMS distance of price from its own weighted mean — a
  descriptive spread measure computed exactly from the bars in the window.
  The familiar "2σ ≈ 95%" reading requires assuming normally distributed
  returns, which this toolkit explicitly rejects. The bands are distance
  markers in a volatility-scaled unit, nothing more.
- **An outer-band tag votes 0, not counter-trend.** Treating "far from the
  mean" as a reversal signal is exactly a probability claim — that price
  reverts often enough for the bet to pay. Extension is reported as an
  *absence* of a directional read, which is what the geometry supports.

### What it costs you

If a trend never returns to VWAP, this fires no signal and the move is
missed entirely. That is the price of insisting on location, and it is the
main thing to check before wiring the markers into an entry rule: compare
how often your instrument pulls back to value against how often it just
runs.

Requires a symbol with a volume feed — a volume-weighted mean is *undefined*,
not merely noisy, without one. The script detects this and says so in its
table instead of plotting a misleading line.

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
