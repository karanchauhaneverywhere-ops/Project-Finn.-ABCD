# Methodology — Big Player Footprint

Every formula the indicator uses, in order. `clamp(x, a, b) = max(a, min(b, x))`.
All distances are in ATR (Wilder, `ta.atr`, gap-aware true range), so the same
settings mean the same thing on any instrument.

---

## 1. Bar anatomy

```
range     = high − low
body      = |close − open|
CLV       = ((close − low) − (high − close)) / range      # −1 closed on low, +1 on high
spreadATR = range / ATR
```

## 2. Effort: volume anomaly

Volume is heavily right-skewed, so a z-score of raw volume is dominated by a few
huge bars. The log fixes that:

```
lv    = ln(volume + 1)
zRoll = (lv − SMA(lv, 50)[1]) / max(stdev(lv, 50)[1], 0.15)
```

`[1]` means the bar is never part of its own baseline. The 0.15 floor stops a
very quiet baseline from turning an ordinary bar into an outlier.

**Time-of-day baseline (intraday, default).** Volume has a strong intraday
seasonality. The open and close are always the busiest bars, so a rolling
baseline flags them every day. For each clock slot (`hour × 60 + minute`) the
script keeps an exponentially weighted mean and variance of `lv` over the last
~20 sessions:

```
α     = 2 / (20 + 1)
z     = (lv − mean_slot) / max(√var_slot, 0.15)        # scored BEFORE updating
d     = lv − mean_slot
mean' = mean_slot + α·d
var'  = (1 − α)·(var_slot + α·d²)
```

A slot is used only after 10 observations. Until then, the rolling z is used.
**Whale bar:** `z ≥ 2.0`.

## 3. Net flow

Signed volume per bar:

* **Bar approximation** (default): `delta = CLV × volume`. This is the
  standard close-location split of a bar's volume into buying and selling.
* **Intrabar** (optional): `delta = Σ sign(close − open) × volume` over
  lower-timeframe bars (1m for charts up to 1h, 5m up to 4h, 15m up to 1D, 60m up
  to 1W). TradingView limits how many intrabars it serves, so older bars fall
  back to the approximation. The panel reports coverage.

```
NDF    = Σ(delta, 20) / Σ(volume, 20)             # −1 … +1, share of volume that was net buying
pxMove = (close − close[20]) / ATR
ACCUMULATION  = NDF ≥ +0.10 and pxMove ≤ 0         # buying without price rising
DISTRIBUTION  = NDF ≤ −0.10 and pxMove ≥ 0
```

**Rolling VWAP** = `Σ(hlc3·volume, 50) / Σ(volume, 50)`. It falls back to
`SMA(hlc3, 50)` when there is no volume. This is where volume actually traded,
i.e. "value".

## 4. Higher-timeframe trend

```
HTF       = chart × 4 (Auto), or manual
slope     = (EMA(close, 50) − EMA(close, 50)[5]) / ATR(14)      # on the HTF
read as     request.security(..., slope[1], lookahead_on)     # last CLOSED HTF bar
bias_HTF  = clamp(slope / 0.5, −1, 1)
```

`expr[1]` with `lookahead_on` is TradingView's documented non-repainting form.
It gives the same value on historical and real-time bars.

## 5. Liquidity levels and sweeps

Swing highs/lows are confirmed pivots (`ta.pivothigh/low(10, 3)`). A level only
exists 3 bars after the swing, so it can never be known early. Up to 10 per side
are tracked, for at most 300 bars.

On each bar, every level that price trades through is removed. If the bar
**closes back inside** the level, the level was **swept**:

```
bullish sweep: low < SSL level and close > level and CLV ≥ 0
bearish sweep: high > BSL level and close < level and CLV ≤ 0
```

The CLV condition requires the close to sit in the rejecting half of the bar.
When several levels are swept together, the most extreme one is recorded.

## 6. Absorption

```
absorbing   = z ≥ 1.5 and spreadATR ≤ 0.9
bull absorb = absorbing and low  ≤ lowest(low, 20)[1]  + 0.25·ATR and CLV ≥ 0
bear absorb = absorbing and high ≥ highest(high, 20)[1] − 0.25·ATR and CLV ≤ 0
```

This is effort without result, at the edge of the range, with the close
rejecting that edge. The conjunction is strict, so absorption fires rarely.

## 7. Displacement and fair-value gap

Bar `[1]` is the displacement bar and the gap sits between bar `[2]` and bar `[0]`:

```
displacement = range[1] ≥ 1.5·ATR[1] and body[1] ≥ 0.6·range[1]      (direction = candle colour)
bull FVG     = displacement up   and low[0]  > high[2] and gap ≥ 0.1·ATR[1]
bear FVG     = displacement down and high[0] < low[2]  and gap ≥ 0.1·ATR[1]
```

The newest gap on each side is watched for 30 bars:

* invalidated when a bar closes through the far side of the gap
* **retest** once price has traded into the gap, and later a bar closes back
  out of it in the original direction with a candle of that colour

## 8. Confirmation (setups A and B)

An event arms the setup with `trigger` = event bar's far extreme and
`invalidation` = its near extreme (long: high/low). On each following bar:

```
close beyond trigger              → fire
close beyond invalidation         → cancel
3 bars elapsed without either     → cancel
```

Confirmation = 0 fires on the event bar itself. Setup C does not need this
step, because the retest close is the confirmation.

## 9. Conviction

For a candidate in direction `d` (+1 / −1):

| Factor | Weight | Points |
| --- | ---: | --- |
| Effort | 30 | `clamp(z_event / 2.0, 0, 1)`: volume of the **event** bar (sweep/absorption bar, or the displacement bar for C) |
| Flow | 20 | `clamp(d·NDF / 0.20, 0, 1)` |
| HTF | 20 | `clamp(d·bias_HTF, 0, 1)` |
| Location | 15 | reversal setups (A, B): long below VWAP / short above. Continuation (C): long above / short below |
| Liquidity | 15 | a sweep of the opposite side's stops within the last 20 bars (long: sell-side swept) |

```
conviction = 100 × Σ points / Σ weights of AVAILABLE factors
```

Without volume, Effort and Flow leave both sums. With HTF off, HTF leaves
both sums. A missing measurement therefore does not score as disagreement.

A sweep setup always earns the Liquidity points, because the sweep *is* the
opposite side's stops being taken. That is intended: it is the most direct
footprint the tool measures.

## 10. Signal gate

```
long  = closed bar and past warm-up and trigger_long  and conviction_long  ≥ 60
        and not (short also qualifies) and ≥ 5 bars since the last signal
```

When several setups trigger on one bar, the priority is sweep > absorption > FVG.

## 11. Scoreboard

Every signal becomes a virtual trade:

```
entry  = signal close
stop   = entry ∓ 1.5·ATR                        (R = 1.5·ATR)
target = entry ± 1.5·R
```

It is resolved on each **later** bar, in this order:

1. open already beyond the stop → exit at the open (can be worse than −1R)
2. bar touches the stop → −1R (so a bar touching both counts as a **loss**)
3. bar touches the target → +1.5R, counted as a win
4. 30 bars elapsed → exit at the close, R = signed move / risk (not a win)

**Baseline.** From the end of warm-up, every bar opens one long and one short
with the identical rules. That is the unconditional win rate this market gave
away over the same period, including its drift. The signal rows compare
against it:

```
edge (pp) = win%_signals − win%_random
z         = (p̂ − p₀) / √(p₀(1 − p₀)/n)        p₀ = random win rate, n = signals
```

|z| < 2 cannot be told apart from luck at conventional confidence. The
break-even win rate for a target of R is `1 / (1 + R)`, before costs and
ignoring timed-out trades.

No commissions or slippage are modelled. Subtract your own costs, in R,
from the average R.
