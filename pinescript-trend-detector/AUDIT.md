# Code audit — known errors and defects

Findings from a line-by-line review of both scripts, ordered by severity.
Line references below are as of commit `11af58b`, when the audit was written.

## Status

| # | Issue | Status |
|---|-------|--------|
| E1 | `voteMASlope` unguarded `na` nullifies the score | **Fixed** |
| E2 | Indicator's drawn stop ≠ strategy's real stop | **Fixed** (via E3) |
| E3 | Position unprotected on its first bar | **Fixed** |
| E4 | `exitThresh >= weakThresh` unguarded | **Fixed** — `runtime.error` |
| E5 | HTF filter silently blocks entries while warming | **Fixed** — explicit + reported |
| E6 | HTF filter repaint vector | **Fixed** — requests `[1]` |
| E7 | No guard on HTF lower than chart TF | **Fixed** — `runtime.error` |
| E8 | `weakThresh > strongThresh` unguarded | **Fixed** — `runtime.error` |
| E9 | `NaN` in table during warmup | **Fixed** (via E1) |
| E10 | Overlay models no costs | Open — inherent, documented |
| E11 | Engine duplicated across both files | Open — needs a Pine library |

A regression was introduced and caught while fixing E3: keying the stop off
`longCondition` alone meant a re-fire *while already long* (score dips to 1
without reaching `exitThresh`, then recrosses to 2) would re-seed and
**loosen** an already-ratcheted stop. Guarded with `strategy.position_size <= 0`
so only a genuinely new position seeds.

**None of this has been compiled.** There is no Pine compiler in the
development environment. In particular, the E3 fix relies on `strategy.exit()`
accepting a `from_entry` whose entry order was placed in the same script
execution and holding it until that entry fills. That is the documented
behaviour, but it is unverified here — check the Strategy Tester's trade list
shows a stop exit available from each trade's first bar.

---

## E1 — `voteMASlope` has no `na` guard, and it poisons the whole score

**Severity: high. Both scripts.**
`indicators/Deterministic_Trend_Detector.pine:214-215`,
`strategies/Deterministic_Trend_Strategy.pine:193-194`

```pine
maSlope     = slowMA - slowMA[slopeLookback]
voteMASlope = int(math.sign(maSlope))
```

Every other vote terminates in a `: 0` fallback, so a component that can't be
computed contributes nothing and the remaining four still work. This one
doesn't. While `slowMA[slopeLookback]` is unavailable, `maSlope` is `na`,
`math.sign(na)` is `na`, and because `rawScore` is a **sum**, one `na` term
makes the entire score `na`.

Every threshold comparison against `na` is false, so:

- the state machine falls through to "Sideways / Range" and pins there,
- no entry ever qualifies,
- the table prints `NaN / 5`.

With the default `slowLen = 200` and `slopeLookback = 10`, **the first ~210
bars are silently dead**. On a chart or backtest range with limited history
this presents as "the script doesn't do anything", with no error.

Fix:
```pine
voteMASlope = na(maSlope) ? 0 : int(math.sign(maSlope))
```

---

## E2 — The indicator's drawn stop does not match the strategy's real stop

**Severity: high. Defeats the purpose of the v3 trade overlay.**
`strategies/Deterministic_Trend_Strategy.pine:53,273,279-280` vs
`indicators/Deterministic_Trend_Detector.pine:331`

The strategy runs with `process_orders_on_close = true`, so an entry placed on
bar N fills at bar N's **close** — after the script has finished executing for
that bar. `strategy.position_size` therefore still reads 0 throughout bar N,
and only becomes non-zero during bar **N+1**:

```pine
longJustEntered = strategy.position_size > 0 and strategy.position_size[1] <= 0
...
if longJustEntered
    longStopLevel := high - atrStopMult * atrVal   // bar N+1's high and ATR
```

The indicator seeds its simulated stop on the entry bar itself:

```pine
if longEntrySignal and simPos <= 0
    longStopLevel := high - atrStopMult * atrVal   // bar N's high and ATR
```

So the red stop line is drawn **one bar early, at a different price**, off a
different ATR reading. The overlay was built specifically so the chart would
show what the strategy does; on this detail it doesn't.

Fix: either delay the indicator's seeding by one bar to match, or (better)
fix E3 in the strategy and align both on the entry bar.

---

## E3 — The strategy's position is unprotected for its first bar

**Severity: high.**
`strategies/Deterministic_Trend_Strategy.pine:289-292`

Same root cause as E2. On the entry bar N, `strategy.position_size` is still
0, so this guard is false:

```pine
if strategy.position_size > 0
    strategy.exit("Long stop", "Long", stop = longStopLevel)
```

No exit order is placed on the entry bar at all. The first stop order is only
submitted during bar N+1's execution. A gap against the position immediately
after entry is entirely unprotected.

For a system whose edge rests on the trailing stop cutting losers small, this
is a material hole, not a rounding detail.

---

## E4 — Nothing enforces `exitThresh < weakThresh`; misconfiguration turns the hysteresis into an oscillator

**Severity: medium-high. Both scripts.**
`indicators/Deterministic_Trend_Detector.pine:94-95`, and the same pair in the
strategy.

`exitThresh` accepts −4…4 and `weakThresh` accepts 1…5, independently. The
input label says "must be < weakThresh" but nothing checks it.

Set `exitThresh = 3`, `weakThresh = 2` and trace it:

| bar | state | score | result |
|-----|-------|-------|--------|
| N   | Sideways | 2 | `2 >= 2` → **Uptrend** |
| N+1 | Uptrend  | 2 | `2 <= 3` → **Sideways** |
| N+2 | Sideways | 2 | `2 >= 2` → **Uptrend** |

The label flips **every single bar**, firing alternating "Entered Uptrend" /
"Entered Sideways" alerts. In the strategy it opens and closes a position
every bar, paying commission and slippage both ways. The hysteresis is
inverted into a metronome.

Fix: a startup guard.
```pine
if exitThresh >= weakThresh
    runtime.error("exitThresh must be less than weakThresh")
```

---

## E5 — The HTF filter silently blocks every entry during its own warmup

**Severity: medium. Both scripts.**

```pine
htfAllowsLong = not useHtfFilter or close > htfMA
```

`htfMA` is `na` until the higher timeframe has accumulated `htfMaLen` bars —
by default **50 daily bars**. `close > na` is false, so with the filter
enabled `htfAllowsLong` is false and **no entry can fire**, with nothing
reported.

On a backtest window shorter than the HTF warmup this reads as "the strategy
doesn't trade", not "the filter isn't warm yet".

Fix: treat `na(htfMA)` explicitly — either block with a visible note, or pass
through until the filter is warm.

---

## E6 — The HTF filter is a repaint vector (historical ≠ realtime)

**Severity: medium.**

`request.security(..., lookahead = barmerge.lookahead_off)` returns the last
*completed* higher-timeframe bar when running over history, but on the live
bar it returns the *currently forming* HTF bar, whose value keeps changing
until that bar closes.

So `htfAllowsLong` on the realtime bar is computed from information that
won't be what history shows later. An entry marker can appear live and then
fail to reproduce once the bar becomes history — precisely the class of
problem the `confirmOnClose` work was meant to eliminate.

Fix: reference the confirmed prior HTF bar (request `ta.ema(close, htfMaLen)[1]`),
accepting one HTF bar of extra lag in exchange for a stable signal.

---

## E7 — No guard against `htfRes` being *lower* than the chart timeframe

**Severity: low-medium.**

Nothing stops the chart being Weekly while `htfRes` is `"D"`. Pine permits
requesting a lower timeframe but the result is not meaningful for this
purpose.

Fix: compare `timeframe.in_seconds(htfRes)` against `timeframe.in_seconds()`
and raise `runtime.error()` when the requested timeframe is the shorter one.

---

## E8 — `strongThresh` / `weakThresh` inversion is unguarded

**Severity: low. Both scripts.**

If `weakThresh > strongThresh` (both are freely settable in 1…5), then inside
the entry branch `rawScore >= strongThresh ? "Strong Uptrend" : "Uptrend"` is
always true, so the plain "Uptrend" label becomes unreachable. Degrades
quietly rather than erroring.

---

## E9 — Table prints `NaN` during warmup

**Severity: cosmetic.** A visible consequence of E1: `str.tostring(rawScore)`
renders `NaN / 5` for the first ~210 bars. Resolves once E1 is fixed.

---

## E10 — The overlay models no costs, so it can never tie out exactly

**Severity: low, but worth stating.**

The strategy applies `commission_value = 0.05` (%) and `slippage = 1` tick.
The indicator's overlay applies neither, so its marker prices are
systematically optimistic against the Strategy Tester's trade list. Small
differences are expected; large ones indicate a real mismatch worth chasing.

---

## E11 — The engine is duplicated with nothing keeping the copies in sync

**Severity: structural.**

Both scripts carry their own copy of the five-vote engine, because a
TradingView `indicator()` and `strategy()` cannot share a file without
publishing a Pine *library*. This has already caused real drift:

- the Choppiness divide-by-zero bug existed in both and had to be fixed twice,
- the classification logic diverged for a full revision before being realigned,
- E1 is currently present in both copies.

Every future change to the engine must be applied twice, by hand, with no
compiler assistance. Publishing the engine as a Pine library and importing it
into both scripts is the only real fix.

---

## Not errors, but worth knowing

- **Warmup is long.** With the defaults the engine needs ~210 bars before it
  can produce a score at all (see E1). Even with E1 fixed, the MA-slope vote
  stays at 0 for that period, capping the reachable score at 4 of 5.
- **Pivot markers are drawn in the past** (`offset = -pivotRight`). This is
  intentional and labelled, but on historical charts it still reads as
  perfectly-timed swing calls that were never available live.
- **None of this has been compiled.** There is no Pine compiler in the
  development environment, so every script here has been verified by reading
  it against the Pine v6 language reference, not by building it. Paste both
  into the Pine Editor and confirm they compile before relying on any of it.
