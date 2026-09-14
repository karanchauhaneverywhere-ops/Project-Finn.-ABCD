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
age   = bar_index − bar of last break
fade  = max(0.25, 1 − age / structMem)
bias₅ = direction · fade
```

**Why decay.** A break of structure three bars ago is strong evidence; the same
break fifty bars ago, with nothing since, is stale. The floor of 0.25 keeps some
memory rather than dropping to zero.

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

The timeframe is **derived from the chart**: `chart_seconds × htfMult`, converted
to a valid timeframe string (seconds → minutes → days → weeks → months). With the
default multiple of 4: 5m→20m, 1h→4h, 1D→4D, 1W→1M. Fetched with
`lookahead = barmerge.lookahead_off` and, by default, read one HTF bar back so
only *closed* higher-timeframe data is ever used.

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
| Reversion | `score` crosses back out of the far extreme **and** the last 5 bars contained a displacement of at least `mrStretch` ATR in that direction |
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

## 7. Repainting analysis

| Component | Behaviour |
| --- | --- |
| `request.security` HTF | `lookahead_off`; default reads the last *closed* HTF bar. No future data. |
| Swing pivots | confirm `pvtLen` bars late. Updates late, never early. Inherent to pivots. |
| Score, regime, all seven factors | functions of closed data only. |
| Signals | with *Only evaluate on closed bars* (default) emitted on bar close. Turn it off for faster, intrabar-mutable signals — disclosed by the setting name and shown in the panel's last row. |
| Strategy orders | `calc_on_every_tick = false`, no `process_orders_on_close`. Fills land on the next bar's open. |

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
