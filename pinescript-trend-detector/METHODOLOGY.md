# Methodology: deterministic trend classification

This document explains, precisely, how the trend state (Strong Uptrend /
Uptrend / Sideways-Range / Downtrend / Strong Downtrend) is computed, and why
every step is a **closed-form deterministic calculation** rather than a
probability model.

## Design principle: no probability assumptions

"No probability assumptions" is a specific, checkable constraint. It rules
out:

- **Statistical inference** — p-values, confidence intervals, hypothesis
  tests, or anything that requires assuming a return distribution (e.g.
  Gaussian/normal returns, which real market returns are well documented to
  violate — they are fat-tailed and heteroskedastic).
- **Bayesian methods** — priors, posteriors, or belief updating.
- **Monte Carlo simulation** — sampling many random paths and reporting an
  outcome likelihood.
- **Machine-learning classifiers** that output a class probability (e.g. a
  softmax "70% chance of uptrend").
- **Probability-weighted position sizing**, such as the Kelly criterion,
  which requires an estimated win probability and payoff ratio.

It does **not** rule out ordinary descriptive/algebraic statistics — a slope,
a ratio, a sum, a correlation coefficient, a logarithm. Those are exact,
reproducible functions of the price series: given the same input bars, they
always produce the same output, with no distributional assumption and no
"confidence level" attached. The one component below that is commonly
associated with "statistics" — the linear-correlation coefficient used for
R² — is used purely as a deterministic goodness-of-fit ratio (how tightly
points sit on a line), never as an inferential statistic (no p-value or
significance test is computed or used).

Every component below is a published, closed-form formula. The composite
classifier is a fixed set of `if`/`else` threshold rules over five independent
votes — not a trained or fitted model.

## The five components

### 1. Least-squares regression slope + R² (linearity)

Over the last `regLen` bars, fit the ordinary least-squares line through
closing price:

```
slope = linreg(close, regLen, offset=0) − linreg(close, regLen, offset=1)
normSlope = slope / ATR(atrLen)
```

Dividing by ATR makes the slope comparable across instruments and volatility
regimes (a 2-point/bar slope means something different on a $20 stock than a
$2,000 one; ATR-normalizing removes that scale dependence).

`R²` (the squared Pearson correlation between price and a linearly
increasing bar index) measures how tightly the last `regLen` closes sit on
that line, from 0 (no linear relationship) to 1 (perfectly linear):

```
R² = correlation(close, bar_index, regLen)²
```

This is an algebraic ratio of sums of squares — it requires no assumption
about the distribution of price changes and produces no probability or
confidence level. It is used only as a **linearity filter**: the slope's
direction is trusted as a vote only when `R² ≥ rSquaredMin` (default 0.35)
*and* the normalized slope clears a minimum magnitude (`slopeMinATR`,
default 0.03 ATR/bar), otherwise the regression casts no vote (0). This
prevents a shallow, noisy wiggle from being read as a trend.

### 2. Wilder's Directional Movement Index / ADX

Computed from the original 1978 Wilder formulas (implemented manually in the
script rather than depending on a possibly-versioned built-in, so the exact
math is visible and auditable):

```
+DM = (up-move > down-move and up-move > 0) ? up-move : 0
−DM = (down-move > up-move and down-move > 0) ? down-move : 0
+DI = 100 · RMA(+DM, diLen) / RMA(TrueRange, diLen)
−DI = 100 · RMA(−DM, diLen) / RMA(TrueRange, diLen)
DX  = 100 · |+DI − −DI| / (+DI + −DI)
ADX = RMA(DX, adxSmoothing)
```

`RMA` is Wilder's own smoothing (an exponential moving average with
α = 1/length) — a deterministic recursive filter, not a statistical
estimator. ADX measures trend *strength* (regardless of direction); +DI vs
−DI gives *direction*. The vote is direction-signed only when
`ADX ≥ adxThreshold` (default 20, Wilder's own published threshold for "a
trend exists"); otherwise it casts no vote (0).

### 3. Choppiness Index

Published by E. W. Dreiss:

```
CHOP = 100 · log10( Σ TrueRange over chopLen bars / (Highest High − Lowest Low over chopLen bars) ) / log10(chopLen)
```

This is a ratio of "distance actually traveled" (summed true range) to "net
distance covered" (the high-low range of the window), log-scaled to sit
between 0 and 100. A market chopping sideways burns a lot of true range to
cover very little net distance (CHOP near 100); a market trending in a
straight line covers close to its full traveled distance as net displacement
(CHOP near 0). The thresholds `61.8` and `38.2` are Fibonacci ratios chosen
by the index's author as fixed calibration constants — they are not
confidence levels or probabilities. By default (`chopOverride = true`), a
CHOP reading at or above `chopSidewaysMin` forces the final label to
"Sideways / Range" outright, since this index is specifically built to catch
range conditions that slope/ADX can misread.

### 4. Swing structure (Dow Theory)

Confirmed swing pivots are located with `ta.pivothigh` / `ta.pivotlow`
(a pivot at bar *t* confirms once `pivotRight` bars have closed after it —
this is an unavoidable lag of any pivot-based method, not repainting of
already-confirmed values: once a pivot prints, its price and bar location
never change). The last two confirmed highs and the last two confirmed lows
are compared directly:

```
Higher High and Higher Low  -> structure vote = +1 (uptrend)
Lower High  and Lower Low   -> structure vote = −1 (downtrend)
anything else                -> structure vote =  0 (mixed / transition)
```

This is the classical Dow Theory definition of trend, expressed as simple
inequalities between four price levels — pure geometry, no statistics.

### 5. Moving-average geometry

Three moving averages (fast/mid/slow, default lengths 21/55/200, selectable
type: EMA/SMA/WMA/HMA/RMA) are compared two ways:

```
Stack:  fast > mid > slow  -> vote = +1
        fast < mid < slow  -> vote = −1
        otherwise           -> vote =  0

Slope:  sign(slowMA − slowMA[slopeLookback])  -> vote ∈ {−1, 0, +1}
```

The stack captures whether shorter-term average price is above/below
longer-term average price in the correct order; the slope captures the
long-term average's own direction. Both are plain arithmetic comparisons.

## Composite score and final classification

The five votes (regression, ADX/DMI, structure, MA stack, MA slope), each in
`{−1, 0, +1}`, are summed into a single integer `score ∈ [−5, +5]`. The final
label is then assigned by fixed thresholds (defaults shown):

```
Choppiness override active and CHOP ≥ 61.8      -> Sideways / Range
score ≥ 4                                        -> Strong Uptrend
score ≥ 2                                        -> Uptrend
score ≤ −4                                        -> Strong Downtrend
score ≤ −2                                        -> Downtrend
otherwise                                         -> Sideways / Range
```

`strength% = |score| / 5 × 100` gives a magnitude reading independent of the
label. All thresholds are exposed as script inputs so they can be tuned per
instrument/timeframe without changing the underlying math.

## The VWAP layer (`indicators/VWAP_Confluence.pine`)

The five components above all answer one question: *which way is price
going?* None of them answer *is this a good price to act at?* The VWAP layer
adds that second axis. It does not replace or re-weight any of the five
votes — it runs the identical engine, then reports whether its own reading
agrees.

### Why VWAP is deterministic

VWAP is the volume-weighted arithmetic mean transaction price since an
anchor:

```
VWAP_t = Σ(p_i · v_i) / Σ(v_i)      for i from the anchor bar to t
```

where `p_i` is the chosen price source (default `hlc3`). This is a ratio of
two running sums — a weighted average, nothing more. Given the same bars it
returns the same number, with no distributional assumption and no parameter
fitted to anything.

The deviation bands use the **volume-weighted variance about that mean**:

```
σ²_t = Σ(v_i · (p_i − VWAP_t)²) / Σ(v_i)
     = Σ(v_i · p_i²) / Σ(v_i) − VWAP_t²      (algebraically identical, one pass)
```

The script computes the second form so it can maintain three running sums
instead of re-walking the window every bar; `math.max(σ², 0)` only clamps
the floating-point rounding that can push a true zero fractionally negative.

**This σ is a descriptive dispersion measure, not a confidence interval.**
It is the root-mean-square distance of traded price from its own weighted
mean over a finite, known set of bars — the same kind of closed-form
descriptive statistic as the correlation coefficient used for R² above. The
usual "2σ contains ~95% of observations" reading requires assuming normally
distributed returns, which this toolkit explicitly rejects (real returns are
fat-tailed and heteroskedastic). Nothing in the script makes, or depends on,
any claim about how often price should sit inside a band. The bands are
distance markers, drawn in a volatility-scaled unit. An ATR unit can be
selected instead of σ, and the logic is unchanged either way.

Because dispersion is meaningless in the first few bars after an anchor
reset (σ starts at zero), the bands and the band vote are suppressed until
`bandWarmup` bars have accumulated.

### The three VWAP votes

Each casts `+1` / `0` / `−1` on the same convention as the five trend
components, summing to a VWAP score in `[−3, +3]`.

**1. Side.** Is price accepted above or below the volume-weighted mean?

```
distATR = (close − VWAP) / ATR
vote    = sign(distATR)  if |distATR| ≥ sideDeadATR,  else 0
```

The ATR dead zone (default 0.05) exists so price oscillating on top of VWAP
casts no vote instead of alternating ±1 bar to bar.

**2. Slope.** Which way is fair value itself moving? Normalized per bar and
by ATR, on the same convention as the regression-slope vote:

```
slopeATR = (VWAP − VWAP[n]) / n / ATR
vote     = sign(slopeATR)  if |slopeATR| ≥ vwapSlopeMinATR,  else 0
```

Price above a *falling* VWAP is a materially different condition from price
above a *rising* one; the side vote alone cannot tell them apart.

**3. Band zone.** Where does price sit in the envelope, in band units
(`z = (close − VWAP) / bandUnit`)?

```
|z| ≤ mult1              ->  0   (at value; no directional read)
mult1 < |z| ≤ mult3      -> ±1   (directional participation away from value)
|z| > mult3              ->  0   (extended)
```

The outer case is worth stating explicitly: a tag of the outer band returns
**0, not a counter-trend −1**. Treating "far from the mean" as a reversal
signal is precisely a probability claim — that price reverts often enough
for the bet to pay — and this toolkit does not make one. Extension is
reported as an absence of a directional read, which is what the geometry
actually supports.

### Alignment and value entries

`alignment` is a direct comparison of the two independent readings:

```
trend label is Up*   and vwapScore > 0  -> Aligned LONG
trend label is Down* and vwapScore < 0  -> Aligned SHORT
the two disagree in sign                 -> Conflicted
otherwise                                -> Neutral
```

Both scores are in the same `{−1, 0, +1}` vote units, so they also sum
directly into `combinedScore ∈ [−8, +8]`.

The value-entry signal is a three-state machine over hard comparisons on
closed bars — it stores one boolean, and never looks ahead:

```
ARM       trend label is Up  AND  low ≤ VWAP + pullbackATR·ATR
CANCEL    trend label leaves Up  OR  close < VWAP − invalidATR·ATR
TRIGGER   armed  AND  close > VWAP + triggerATR·ATR  AND  cooldown elapsed
```

(mirrored for shorts). Arming is evaluated *before* cancelling on each bar,
so a bar that trades down to value and then closes straight through it is a
failed reclaim and ends the bar disarmed, rather than arming on its own low.

The purpose is location, not extra prediction: the trend engine already
decided the direction, and this only changes *where* that direction gets
acted on — at fair value on a pullback, rather than wherever the score
happened to cross. The trade-off is disclosed rather than hidden: in a trend
that never returns to VWAP, this fires no signal at all and the move is
missed entirely. That is the cost of insisting on location.

### Additional limitations of this layer

- **VWAP requires volume.** On symbols with no volume feed (many indices,
  some FX sources) the weighted mean is undefined, not merely inaccurate.
  The script detects this and says so in its table rather than plotting a
  misleading line.
- **The anchor must be shorter than the chart timeframe is long.** A
  "Session" anchor on a daily-or-higher chart resets every bar, making VWAP
  equal to that bar's own price source. Use an intraday chart, or a longer
  anchor.
- **Anchored VWAP is path-dependent by construction.** Its value at bar *t*
  depends on where the anchor was placed. Two traders using different
  anchors get different "fair values", and neither is more correct — the
  anchor is a choice about which participants' cost basis you care about.

## Known limitations (disclosed, not hidden)

- **Pivot confirmation lag.** The swing-structure vote can only update
  `pivotRight` bars after a swing actually forms. This is a real, bounded
  lag inherent to any pivot method — the script does not use unconfirmed,
  repainting pivots.
- **Lagging inputs generally.** Every component (regression window, RMA
  smoothing, moving averages) looks backward over a finite window by
  construction; none of this predicts future price, and none of it should be
  read as one.
- **Threshold sensitivity.** Like any rule-based system, the classification
  is sensitive to its input lengths and thresholds. Defaults are the
  commonly published values for each underlying method (Wilder's ADX = 20,
  Dreiss's Choppiness Fibonacci levels), not values fitted to any particular
  market or backtest.
- **No performance guarantee.** A deterministic trend label is a description
  of price geometry, not a prediction. Backtested results in
  `strategies/Deterministic_Trend_Strategy.pine` are shown for research only
  and do not indicate future returns.
