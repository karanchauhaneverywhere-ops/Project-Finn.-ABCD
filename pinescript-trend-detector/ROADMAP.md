# Improvement roadmap

Written from a technical-analysis practitioner's review of the system as it
stands. Ordered by how much each item would actually change outcomes, not by
how interesting it is to build.

The organising principle: **item 1 gates everything else.** Until the
validation harness says whether a change helped, every other item on this list
is a guess wearing a lab coat.

---

## Status

| # | Item | Status |
|---|------|--------|
| 1 | Validation harness (walk-forward, sensitivity, MAE, benchmark) | **Built** — `research/` |
| 2 | Component collinearity — measure and fix | **Measured**, unfixed |
| 3 | Volume is absent from the system entirely | Open |
| 4 | No relative strength / market context | Open |
| 5 | No trend degree / top-down structure | Open |
| 6 | Static parameters across volatility regimes | Open |
| 7 | Stop distance chosen, not measured | **Tooling built**, needs real data |
| 8 | Risk management is trade-level only | Open |
| 9 | Entry is pure breakout, no pullback variant | Open |
| 10 | Exits don't separate "wrong" from "matured" | Open |
| 11 | Strategy still runs the old five-vote engine | Open |

---

## 1. Validation harness — BUILT

`research/` implements walk-forward analysis, parameter grid search, MAE/MFE
stop calibration, buy-and-hold benchmarking, and component collinearity, with
23 tests over the engine port.

**This was first for a reason.** The evidence base before it was one
instrument, one period, one parameter set — from which nothing is knowable.

**Next action:** run it against real exported data for the instruments you
actually trade. Everything below should be judged by what it does to those
numbers.

---

## 2. Component collinearity — MEASURED, and it's a problem

The engine presents four components as independent votes. They are not.
Measured on the harness:

```
Mean |correlation| between components: 0.76 (worst pair 0.85)
```

Efficiency Ratio, range position, and displacement balance are all computed
over ~20 bars of the same close series and all measure directional
persistence. Breakout structure correlates with all three. In a clean trend
they go positive together; in chop they collapse together.

So the weighted average delivers far less diversification than the
architecture implies — it is closer to one factor with three confirmations of
itself. The weights are dividing up a single signal.

**Fix:** real orthogonality requires inputs from a different *dimension*, not
four more price-derived windows over similar lookbacks. That means items 3, 4
and 6 below. Alternatively, accept it and simplify: if the components are 0.76
correlated, three of them are close to decoration, and a simpler engine would
be more honest and easier to reason about.

*(The 0.76 figure is from synthetic data. Re-measure on your real instruments
before acting — but do expect it to be high, because it follows from the
construction, not from the data.)*

---

## 3. Volume is absent from the system entirely

The most conspicuous gap against classical technical analysis. Dow Theory's
confirmation principle requires volume to validate a trend; Wyckoff's entire
framework is effort (volume) against result (price spread).

The breakout component currently fires identically whether the channel break
came on triple average volume or on a thin holiday session. Those are opposite
trades.

**Fix:** add a volume-confirmation term to the structure component, or an
effort/result ratio (spread ÷ volume) as a genuinely independent fifth input.
On instruments without reliable volume (spot FX) substitute tick count, or
disable the term — but the system should know the difference rather than being
blind to it.

**Why it ranks here:** it is the single largest source of information the
system currently ignores, and unlike items 4–6 it needs no external data feed.

---

## 4. No relative strength or market context

Every instrument is evaluated in complete isolation. There is no relative
strength versus a benchmark, no sector context, no breadth, no intermarket
read.

A stock in a technical uptrend while lagging both its sector and the index is
a materially worse long than one leading it, and the score cannot tell them
apart. Relative strength is among the most durable effects in the technical
literature and the system has none of it.

**Fix:** a relative-strength ratio line against a benchmark
(`request.security` on an index symbol), and gate entries on the broad
market's own trend state. Cheap to build, and genuinely orthogonal to
everything already in the engine — which also helps item 2.

---

## 5. No trend degree, no top-down structure

Dow classified trends as primary, secondary and minor. The script says "Strong
Uptrend" without qualifying at what degree — on a 5-minute chart it will say
that about something that is noise on the daily.

Proper top-down analysis means the higher degree sets permission and the lower
degree sets timing. The strategy's HTF filter is off by default and is a single
EMA, which is a gate, not a trend framework.

**Fix:** run the same engine at a higher timeframe and report both degrees,
with the lower-degree signal only actionable when it agrees with the higher.

---

## 6. Static parameters across all volatility regimes

`er_len`, `don_len`, and the 40/70/15 thresholds are fixed across every
instrument and every volatility regime. Markets are not stationary and the
score distribution is not stable across them.

There is an irony worth naming: the Efficiency Ratio at the centre of the
engine is Kaufman's, and its *original* purpose was adaptive — ER drives the
smoothing constant in his Adaptive Moving Average, so the system speeds up in
trends and slows down in noise. The engine uses ER to score while ignoring the
adaptive application it was designed for.

**Fix:** let ER modulate `don_len` and the thresholds. Closer to the spirit of
the tool, and it addresses non-stationarity directly.

---

## 7. Stop distance was chosen, not measured — TOOLING BUILT

2.5 ATR is a plausible number with no evidence behind it.

`research/run.py mae` implements Maximum Adverse Excursion analysis: for every
trade, how far it drew against you before resolving. If winners rarely exceed
X ATR of adverse excursion, a stop beyond X donates room for nothing and a
stop inside X cuts trades that would have worked.

**Next action:** run it on real data. On synthetic data it already reported the
2.5 ATR default as wider than winners ever used — treat that as a demonstration
that the tool works, not as a finding.

---

## 8. Risk management is trade-level only

Fixed 10% of equity per position, no portfolio heat limit, no cap on
concurrent positions, no correlation awareness.

Run this across five correlated instruments and you hold one position at five
times the intended size, and you find out during the drawdown.

**Fix:** volatility-normalised sizing (`risk% × equity ÷ (atr_mult × ATR)`),
a portfolio heat cap, and a correlation check before adding a position.

---

## 9. Entry is pure breakout, with no pullback variant

Entering at the moment of qualification means buying extension. Many trend
systems improve materially by requiring a pullback to a reference level
*within* an already-confirmed trend.

**Fix:** implement as a switchable entry mode and let the harness settle it.
This is exactly the kind of question the sensitivity tooling exists to answer.

---

## 10. Exits don't distinguish "I was wrong" from "the trend matured"

The stop and the score exit are both just "get out". There is no separation of
initial risk from trend-maturity exit, no partial profit, no breakeven shift,
no time-based exit.

**Fix:** separate initial stop from trailing exit, and test a partial-profit
rule at a measured MFE level (the harness already computes MFE).

---

## 11. The strategy still runs the old five-vote engine

Outstanding from the indicator rewrite. The indicator uses path geometry; the
strategy still uses regression/ADX/Choppiness/pivots/moving averages. **They
measure different things**, so the indicator's markers are not a preview of the
strategy's trades — the exact mismatch that produced losing discretionary
trades earlier.

**Fix:** port the strategy onto the path geometry engine, or formally retire
one of the two.

---

## A note on the "no probability assumptions" constraint

The constraint is coherent for **signal generation**: no fitted models, no
distributional assumptions, no probability outputs. Worth keeping.

It should not extend to **evaluation and risk**, and it quietly had been.
Expectancy is probabilistic. So is risk of ruin, drawdown estimation, and any
statement about whether results could have arisen by chance. Refusing those
tools does not make the system more rigorous — it makes it unmeasurable.

`research/` deliberately computes them, and `research/README.md` states the
distinction so the constraint stops leaking into places it does not belong.

---

## What is already right

For calibration, because a review that only lists faults is not a useful one:

- **Hysteresis** between entry and exit thresholds — routinely missing in
  retail systems, and correct here.
- **Bar-close confirmation** — handles the repainting problem that most retail
  indicators get wrong.
- **A stop that only ratchets** — correct, and the loosening bug was caught.
- **The state-versus-signal distinction** in the trade overlay — now handled
  better than most commercial indicators.
- **Efficiency Ratio as the core primitive** — a good instinct, and the right
  family of measure for the problem.
