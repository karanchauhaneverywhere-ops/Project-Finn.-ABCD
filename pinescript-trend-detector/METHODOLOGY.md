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
