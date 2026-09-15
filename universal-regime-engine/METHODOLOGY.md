# Methodology — Universal Regime Engine

Every formula the engine uses, in order, with the reasoning for each choice.
Nothing here is a probability, a statistical inference, or a fitted parameter.

---

## 0. The normalisation principle

A measurement is portable across markets only if its units are not the
instrument's price units. Three families qualify, and the engine uses only these:

1. **Volatility-relative** — divide by ATR. `(price − MA) / ATR` answers "how
   far, *for this market*", which is a question with the same meaning everywhere.
2. **Structurally bounded** — oscillators whose range is fixed by construction
   (RSI, MFI, ADX, DI balance, efficiency ratio).
3. **Self-referencing rank** — percent-rank of a value against its own history.

ATR is computed from `ta.tr(true)`, which includes the gap between the previous
close and the current bar. That matters for session-bound instruments (equities,
futures) and for weekend gaps in FX: without it, the ruler would understate
volatility on exactly the bars where it matters most.

---

## 1. Kaufman Adaptive Moving Average (the trend reference)

```
step       = |src − src[1]|
noise      = Σ(step, erLen)                 # total path length
signal     = |src − src[erLen]|             # net displacement
ER         = signal / noise                 # 0 = pure noise, 1 = straight line
fastSC     = 2 / (fast + 1)
slowSC     = 2 / (slow + 1)
sc         = (ER·(fastSC − slowSC) + slowSC)²
KAMA       = KAMA[1] + sc·(src − KAMA[1])
```

**Why adaptive rather than a fixed EMA.** The efficiency ratio is itself a
dimensionless quantity (a ratio of two distances in the same units). In a clean
trend `ER → 1` and the average tracks price closely; in chop `ER → 0` and it
nearly freezes. That is precisely the behaviour you want from a single setting
that has to survive both a trending daily chart and a ranging 5-minute chart.
Squaring the constant makes the slow state genuinely slow.

---

## 2. The seven factors

Each produces a **bias in [−1, +1]**. `clamp(x) = max(−1, min(1, x))`.

### F1 — Trend slope

```
slopeATR = (KAMA − KAMA[slopeLen]) / ATR
bias₁    = clamp(slopeATR / slopeNorm)
```

The numerator is the move the trend reference itself made over `slopeLen` bars.
Dividing by ATR converts it into "how many average bar-ranges of progress the
trend made", which is comparable across every instrument. `slopeNorm` (default
0.75) is the amount of progress that counts as full conviction.

### F2 — Displacement

```
distATR = (src − KAMA) / ATR
bias₂   = clamp(distATR / distNorm)
```

Where price sits relative to its own adaptive fair value, in volatility units.
Separate from F1 on purpose: a market can be rising slowly with price far above
value (extended), or flat with price at value (balanced). Those are different
states and they get different evidence.

### F3 — Momentum

```
bias₃ = clamp((RSI(src, rsiLen) − 50) / 25)
```

RSI re-centred on zero. Dividing by 25 rather than 50 means RSI 75 / 25 already
counts as full momentum conviction, which matches how the reading is used in
practice.

### F4 — Directional strength

```
[+DI, −DI, ADX] = ta.dmi(diLen, adxSm)
balance = (+DI − −DI) / (+DI + −DI)        # direction,  −1 … +1
magnitude = clamp(ADX / adxFull, 0, 1)     # conviction,  0 … 1
bias₄ = clamp(balance) · magnitude
```

**Direction and conviction are computed separately and then multiplied.** This is
the important detail. ADX alone is directionless; DI alone is noisy when ADX is
low. Multiplying gives a factor that is near zero in a directionless market
regardless of which DI happens to be on top — which is the correct answer.

### F5 — Market structure (BOS / CHoCH)

Confirmed swing pivots (`ta.pivothigh` / `ta.pivotlow`, `pvtLen` bars each side)
define the most recent structural high and low. Each level is "live" until price
closes through it:

* close **above** the live swing high → **Break of Structure** up
* close **below** the live swing low → **Break of Structure** down
* a break in the direction opposite to the current structural state →
  **Change of Character** (the first sign of a regime turn)

An outside bar can break both sides in the same bar; that is resolved by where
the bar closed, so the state is never ambiguous.

```
age    = bar_index − bar of last break
live   = age ≤ structMem
fade   = live ? clamp(1 − age / structMem, 0, 1) : 0
bias₅  = (live ? direction : 0) · fade
```

**Why decay, and why it expires.** A break of structure three bars ago is strong
evidence; the same break fifty bars ago, with nothing since, is stale. The fade
runs linearly to zero and the state then **expires** — both the score contribution
and the directional entry gate return to neutral.

An earlier version floored the fade at 0.25 and never expired the direction. That
made `structMem` a misnomer: a break thousands of bars old still put a permanent
±5-point bias on the score at the default weight, and `structDir` never returning
to 0 meant the structure gate blocked one side of every entry indefinitely, even
across a year of flat price. The panel now shows `expired` for a structure that has
aged out, so the distinction is visible rather than implied.

### F6 — Volume flow, with graceful degradation

```
bias₆ = clamp((MFI(hlc3, mfiLen) − 50) / 25)   if the volume feed is usable
```

Usable is defined as `SMA(volume, 20) > 0`. Many FX, index and CFD feeds report
no volume, or tick counts that mean something different from traded size. When
the feed is unusable the factor is **dropped from both the numerator and the
denominator** of the blend — not zeroed. Zeroing would drag every score toward
the middle and silently change the meaning of the entry threshold; dropping it
preserves the scale. The panel says which of the two happened.

### F7 — Higher-timeframe bias

The same slope + displacement core, evaluated on a higher timeframe:

```
htf_bias = 0.6·clamp(slopeATR_htf / slopeNorm) + 0.4·clamp(distATR_htf / distNorm)
```

The timeframe is **derived from the chart**: `timeframe.from_seconds(chart_seconds
× htfMult)`. The built-in is used rather than a hand-rolled converter because it is
guaranteed to return a resolution `request.security()` accepts — a hand-rolled one
can emit `"3S"` (not a supported second resolution, so the request errors or snaps
elsewhere) or mis-round at the week/month boundary. With the default multiple of 4:
5m→20m, 1h→4h, 1D→4D.

Fetched with `lookahead = barmerge.lookahead_off` and, by default, read one HTF bar
back so only *closed* higher-timeframe data is ever used. The call is **guarded**:
with HTF mode off, or weight 7 at zero, no request is issued at all, so turning the
factor off genuinely costs nothing and does not consume one of TradingView's 40
`request.*` slots.

---

## 3. Blending

```
score_raw = 100 · Σ(wᵢ · biasᵢ) / Σ(wᵢ)      over factors that are
                                              enabled (wᵢ > 0) AND available
```

The denominator is recomputed every bar from the factors that actually
contributed. Consequences, all intentional:

* setting a weight to 0 **rescales** the score rather than deadening it — your
  entry threshold keeps its meaning;
* an instrument with no volume produces scores on the same −100…+100 scale as one
  with volume;
* turning the higher timeframe off does not bias the score toward zero.

### Over-extension damping

```
stretch = |distATR|
damp    = 1                                              if stretch ≤ stretchMax
        = max(0.35, 1 − (stretch − stretchMax)/(2·stretchMax))   otherwise
score   = EMA(score_raw · damp, smoothLen)
```

Every factor above is a *confirmation* factor: they all get more positive the
further a move has already run. Without a counterweight, the engine would be
loudest at exactly the worst moment to enter. The damping term is that
counterweight — conviction is reduced, not reversed, once price is unusually far
from value. The floor of 0.35 stops a genuine trend from being silenced.

The final EMA (default 2 bars) removes single-bar flicker around the threshold.

---

## 4. Regime classifier

**Squeeze.** The standard test is `lowerBB > lowerKC and upperBB < upperKC`. Both
halves reduce to the same inequality around a shared basis, so it is computed
once:

```
squeeze = bbMult·stdev(close, n) < kcMult·SMA(TR, n)
```

**Classification**, in priority order:

| Order | Condition | Regime |
| --- | --- | --- |
| 1 | squeeze on | COMPRESSION |
| 2 | ADX ≥ floor and \|score\| ≥ 0.6·entry threshold, score > 0 | TREND UP |
| 3 | same, score < 0 | TREND DOWN |
| 4 | ATR percent-rank ≥ volHot | VOLATILE RANGE |
| 5 | — | RANGE |

Compression is tested first because a coiled market can still show a leftover
directional score from before it coiled; the squeeze is the more urgent fact.

---

## 5. Playbooks

| Playbook | Trigger |
| --- | --- |
| Continuation | `score` crosses ±entry threshold |
| Reversion | `score` crosses back out of the far extreme **and** the last `mrLook` bars (default 5) contained a displacement of at least `mrStretch` ATR in that direction. Setting `mrStretch` to 0 removes the requirement — documented in the input's tooltip, because the gate then silently passes almost every bar |
| Breakout | the squeeze releases (`squeeze[1] and not squeeze`) with `\|score\| > 0.5·threshold` and price on the right side of the basis |

The prior-stretch requirement on reversion is what stops it from firing on every
small wobble through the threshold: a fade needs something to fade.

**Gates** applied to every candidate: structure agreement, higher-timeframe
agreement, closed-bar confirmation, and a cooldown in bars since the last signal.
Each is individually switchable so you can see what each one is costing you.

---

## 6. Risk model

The stop is chosen first; targets are defined as multiples of the risk that stop
implies, never as fixed distances.

| Mode | Long stop |
| --- | --- |
| Structure + ATR buffer | `lowest(low, swingLB) − 0.5·atrStop·ATR` |
| Pure ATR | `close − atrStop·ATR` |
| Chandelier | `highest(high, swingLB) − atrStop·ATR` |

A structural stop that would land on the wrong side of price falls back to the
ATR stop — a guard that matters on gap opens and on very wide bars.

```
R      = |entry − stop|
T1..T3 = entry ± {rt1, rt2, rt3}·R
size   = (account · risk% / 100) / R
```

Because R is derived from an ATR-based stop, the same "risk 1%" setting produces
a sensible size on any instrument without being retuned. The size figure assumes
one price point equals one unit of quote currency — correct for spot and crypto,
an approximation for futures and FX lots, where you must apply the contract's
point value yourself.

---

## 5b. Signal vs entry — the arming model

A signal is a statement about the *evidence*. An entry is a statement about *price*.
Collapsing the two is the most common way a confluence tool produces trades it should
not have taken, because it acts on agreement that price then immediately contradicts.

In **Confirm** mode (default) a signal arms a setup rather than entering it:

```
on signal:    armLevel = high + 1 tick   (long)    armStop = stopL
                       = low  − 1 tick   (short)   armStop = stopS
              armBar   = bar_index
fire (long):  armAge > 0  and  high ≥ armLevel
void:         armAge > 0  and  |score| < exitTh          → setup dropped
lapse:        armAge > armExpiry                          → setup dropped
```

`armAge > 0` is what forces the entry onto a *later* bar than the signal — the same
bar cannot both propose and confirm. A trigger on the last valid bar wins over the
lapse, because the void/lapse tests require `not fire`.

The entry price, stop, targets, R and position size are all computed from `armLevel`,
not from the signal bar's close. That matters: if you enter on a break of the signal
bar's high, your risk is measured from that break, and pricing the trade at the close
would understate it.

**What this buys you.** A signal price never confirms costs nothing — it lapses
instead of becoming a trade. **What it costs you.** In a market that gaps or runs
away, confirmation means a worse entry than the close, and some good signals are
missed entirely. That is the trade being made, stated rather than hidden. Immediate
mode restores the old behaviour for comparison.

The strategy expresses the same model as a resting **stop order** at `armLevel`,
cancelled on void or lapse — which is both the faithful translation and the more
realistic fill assumption than a market order.

---

## 6b. Setup invalidation

A setup ends for one of three reasons, and the panel names which:

| Cause | Test |
| --- | --- |
| `stopped out` | long and `low ≤ stop`, or short and `high ≥ stop` |
| `target 3 reached` | long and `high ≥ T3`, or short and `low ≤ T3` |
| `score faded` | `\|score\| < exitTh` |

Only the third is visible to the score. A hard reversal can take the score from
+40 to −40 without ever passing through the stand-aside band, so without the first
test the panel would keep advertising a long — with its original entry, stop and
targets — long after price had traded through that stop. For a tool whose whole
purpose is decision support, reporting an invalidated position is the worst kind of
bug: it is silent, and it looks like information.

---

## 7. Repainting analysis

| Component | Behaviour |
| --- | --- |
| `request.security` HTF | `lookahead_off`; default reads the last *closed* HTF bar. No future data. |
| Swing pivots | confirm `pvtLen` bars late. Updates late, never early. Inherent to pivots. |
| Score, regime, all seven factors | functions of closed data only. |
| Signals | with *Only evaluate on closed bars* (default) emitted on bar close. Turn it off for faster, intrabar-mutable signals — disclosed by the setting name and shown in the panel's last row. |
| Strategy orders | `calc_on_every_tick = false`, no `process_orders_on_close`. Fills land on the next bar's open. |

---

## 7b. Execution model (strategy only)

The measurement engine is shared byte-for-byte with the indicator; everything below
it differs. The order layer is where backtests usually lie, so each choice is stated:

| Concern | Choice | Why |
| --- | --- | --- |
| Fill timing | next bar's open, `calc_on_every_tick = false`, no `process_orders_on_close` | filling at the close of the bar that produced the signal flatters results |
| First-bar protection | `strategy.exit` is submitted in the **same block** as `strategy.entry` | gating it on `strategy.position_size != 0` places it only after the fill is visible, leaving the position with no stop for its entire first bar |
| Stop movement | strictly monotonic — breakeven and Chandelier only ever tighten | an earlier version clamped the stop toward price when price closed through it, which ratcheted the stop down bar after bar and turned a 1R loss into an unbounded one. A close beyond the stop now exits at market instead |
| Trailing inputs | `ta.highest`/`ta.lowest` are evaluated unconditionally at engine level | calling them inside `if in_position` advances their windows only on bars where a position is open, producing a trail built from the wrong lookback |
| Scale-out | absolute thirds of the entry quantity, each leg latched once touched | `qty_percent` is a share of the position, so 33/50/remainder is 33/50/17, not thirds; and re-issuing a filled exit id re-creates it behind the market, shedding another slice every bar |
| Leverage | `margin_long`/`margin_short` = 100, plus a "max position notional" cap | a very tight stop asks risk-based sizing for many times equity, and the emulator will happily fill it |
| Sizing vs fill | size from the signal bar's close, R recomputed from the actual fill | not removable without lookahead. On a gap the realised risk differs from the configured percentage; recomputing R from the fill at least keeps the reported figures true |

---

## 8. What the engine deliberately does not do

* **No optimisation.** No parameter was chosen by scanning past results. Defaults
  are conventional round numbers (14, 20, 2.0, 1.5) so their behaviour is
  predictable rather than fitted.
* **No probabilities.** A score of +48 is not "48% likely to go up". It is the
  weighted fraction of the measured evidence currently leaning long. That is a
  statement about the present, not a forecast.
* **No hidden state.** Every factor's raw reading, normalised bias, weight and
  point contribution is on screen, and every intermediate is in the Data Window.
* **No claim about win rate.** The signals demonstrate one consistent way to act
  on the readings. Their historical performance is a property of the market and
  the settings, not evidence that the measurements are right or wrong.

Research and education only. Not financial advice.
