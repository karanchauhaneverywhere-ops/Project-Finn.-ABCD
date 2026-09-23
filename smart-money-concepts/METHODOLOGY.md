# Methodology: Smart Money Concepts Signals

Every rule the engine uses, in the order it runs on each bar, with the reason
for each choice. Nothing here is fitted to past data. Where a number was
needed, it is the conventional one.

Notation: offsets are in bars back from the current bar (`x[3]` = three bars
ago). `ATR` is `ta.atr(atrLen)`, Wilder's average true range, which includes
gaps. Every step runs only on a **closed** bar (`barstate.isconfirmed`).

---

## 0. One unit for every size: ATR

Displacement, gap size, zone height, stop buffer and the stop-width limits are
all written as multiples of ATR. "A candle body of 1 ATR" is the same statement
about any market. A fixed number of pips or dollars would mean something
different on every symbol. Lookbacks are in bars, so a 5-bar swing is the same
structural object on every timeframe.

---

## 1. Swing points

```
swing high  = ta.pivothigh(high, L, L)      L = swing length (default 5)
swing low   = ta.pivotlow(low,  L, L)
```

A swing high is a high with `L` lower highs on each side. It can only be known
`L` bars after it forms, so every swing is registered with that delay. Nothing
in the engine sees a swing before it is confirmed.

---

## 2. Liquidity pools and sweeps

Resting orders (stops of shorts, breakout buys) sit above swing highs, called
**buy-side liquidity**. Resting sells sit below swing lows, called **sell-side
liquidity**. The engine keeps the last 10 unbroken swing highs and 10 unbroken
swing lows as pools.

On every bar, each pool is checked:

```
buy-side pool at P:   high > P  →  pool consumed
                      … and close < P  →  it was a SWEEP (stop run)
sell-side pool at P:  low  < P  →  pool consumed
                      … and close > P  →  it was a SWEEP
```

A pool can only be taken once. A **sweep** is the classic "stop hunt": price
trades through the level, triggers the stops resting there, and closes back
inside the range. The bar of the most recent sweep on each side is stored.

---

## 3. Market structure: BOS and CHoCH

The engine tracks the most recent confirmed swing high and swing low. Each can
be broken once.

```
bullish break  = close > last swing high        (a CLOSE, never a wick)
bearish break  = close < last swing low
CHoCH          = a break against the current structure trend
BOS            = a break in the direction of the current trend
```

After a bullish break the structure trend is `+1`. After a bearish one it is
`−1`. If a single outside bar closes through both levels, its close decides:
up if `close ≥ open`, down otherwise.

**Why closes only:** a wick through a swing is exactly what a sweep looks like
(§2). If wicks counted as breaks, every stop hunt would flip the structure.

---

## 4. Measuring the breaking leg

When a bullish break confirms, the leg that caused it is measured once, from
data that exists on that bar (bearish is the mirror image):

| Measurement | Rule |
| --- | --- |
| **Origin** | The lowest low between the broken swing high and the break bar (scan capped at 300 bars). |
| **Order-block candle** | The last *down-close* candle at the origin or up to 3 bars before it. If there is none, the origin candle itself. |
| **Zone** | Bottom = the origin low. Top = the order-block candle's high, capped at `bottom + 1.5 ATR` so a single huge candle cannot make the zone meaningless. |
| **Displacement** | At least one candle in the leg (origin → break) with `close − open ≥ 1.0 × ATR`. |
| **Fair value gap** | A 3-candle pattern inside the leg where `low[i] > high[i+2]`, the middle candle closes above `high[i+2]`, and the gap is ≥ 0.1 ATR. The first gap after the origin is kept. |
| **Sweep at origin** | The last sell-side sweep happened no earlier than 3 bars before the origin. In practice it is the origin candle's own wick. |
| **Dealing range** | From the origin low to the highest high of the leg. The top keeps extending while the setup is armed. |

A break becomes an **armed setup** only if it shows **displacement or a fair
value gap**. A slow, overlapping crawl through a swing high shows neither, and
that is the kind of break retail breakout traders get trapped in. The
*Trade which breaks* option can also restrict setups to CHoCH-only or BOS-only.

A newer break in the same direction replaces the armed setup, because the most
recent structure is the relevant one. An opposite break does not cancel it. A
retest into a bullish order block often breaks a minor internal low on the way
down, and that is the retest itself, not an invalidation. Real invalidation is
defined in §5.

---

## 5. Life of an armed setup

On every bar after the break, for a bullish setup:

```
rangeHigh = max(rangeHigh, high)
extreme   = min(extreme, low)                 # stop anchor
touched   = low ≤ zoneTop                     # (or ≤ FVG top in "Order block or FVG" mode)
position  = (close − rangeLow) / (rangeHigh − rangeLow) × 100     # 0 = origin, 100 = top

invalidated  if close < zoneBottom            # closed through the order block
expired      if bars since break > 30
TRIGGER      if touched within the last 2 bars
             and close > open                 # rejection candle
             and position ≤ 50                # discount (entry limit)
```

* **Discount / premium.** Buying below the 50 % equilibrium of the move is the
  core SMC idea of buying cheap relative to the displacement that created the
  zone. It also keeps the stop close relative to the room left to the targets.
* **Rejection close.** A touch alone does not trigger. A candle has to close in
  the trade direction, which shows the zone is being defended.
* **Wicks below the zone are allowed** as long as the candle closes back
  inside. The stop anchor (`extreme`) follows such a wick, so the stop always
  sits beyond the real low of the move.

A trigger that fails one of the gates in §7 leaves the setup armed, because a
deeper retest a few bars later can still qualify.

---

## 6. Grade

```
grade = [sweep at origin] + [FVG in the leg] + [position ≤ 38.2]
A+ = 3   A = 2   B = 1   C = 0
```

`position ≤ 38.2` of the range is a ≥ 61.8 % retracement, the start of the
"optimal trade entry" band. The three confluences are independent of each
other and of the required conditions. Each is something a discretionary SMC
trader would name when explaining why a setup is better than average.

---

## 7. Gates

A trigger becomes a **BUY** only if all of these hold:

| Gate | Rule |
| --- | --- |
| Grade | `grade ≥ minimum grade` (default A = 2) |
| Higher timeframe | HTF structure trend = `+1` (skipped when the HTF filter is off) |
| Stop width | `close − stop ≤ 3.0 ATR` |
| One call at a time | no BUY call is currently open |

### Higher-timeframe bias

The same swing and close-beyond-swing rules as §1 and §3, evaluated on a
higher timeframe:

```
htfDir = request.security(ticker, HTF, structDir(L)[1], lookahead = barmerge.lookahead_on)
```

`[1]` combined with `lookahead_on` returns the value of the last **completed**
HTF bar, both on history and in real time. This is the non-repainting form in
TradingView's documentation. In Auto mode the HTF is derived from the chart
(`chart × 4`: 5m → 20m, 15m → 1H, 1H → 4H, 1D → 4D), so the ratio stays the
same on every timeframe.

---

## 8. Stop and targets

```
stop  = min(extreme − 0.25 ATR,  close − 0.5 ATR)      # beyond the move's low, never tighter than 0.5 ATR
R     = close − stop
TP1   = close + 1R     TP2 = close + 2R     TP3 = close + 3R
```

* The stop sits beyond the lowest price since the origin. If price trades
  there, the order block has failed.
* The minimum width of 0.5 ATR stops a call whose entry sits right on the zone
  bottom from getting a stop inside normal noise. The maximum of 3 ATR (§7)
  skips calls where the retest came so late that the risk is out of
  proportion.
* After TP1 the stop moves to the entry price (breakeven), if that option is
  on.

---

## 9. The call tracker and the scoreboard

One call is followed at a time. On every bar after the call bar:

```
long:   if low ≤ stop                → closed at min(open, stop)      # the stop is checked FIRST
        else  high ≥ TP1  → hit 1  (stop → entry if breakeven is on)
              high ≥ TP2  → hit 2
              high ≥ TP3  → hit 3, call complete
```

* **The stop is checked before the targets.** Bar data cannot show whether the
  high or the low came first. When a bar spans both, the pessimistic outcome
  is recorded.
* **A gap through the stop** fills at the open, not at the stop price.
* **An opposite call** closes the open call at its close and opens the new one.
  A new call in the same direction is not printed while one is open. Its setup
  stays armed and can fire after the open call ends.

Realised result of a resolved call, scaled out in thirds:

```
R_realised = (hit1·TP1_R + hit2·TP2_R + hit3·TP3_R) / 3  +  (3 − hits)/3 · exit_R
```

`exit_R` is `−1` at the original stop, `0` at breakeven, or the open profit or
loss at a reversal. The panel shows the share of calls that reached each
target, the sum of `R_realised`, and the profit factor
(`Σ positive R / Σ negative R`).

---

## 10. The strategy

`Smart_Money_Concepts_Strategy.pine` contains §1–§9 unchanged and adds:

* a market entry on the call, filled at the **next bar's open**
  (no `process_orders_on_close`);
* a bracket placed together with the entry: ⅓ at TP1, ⅓ at TP2, the rest at
  TP3, all behind the call's stop, which the engine moves to breakeven after
  TP1;
* risk-based sizing: `equity × risk% / |entry − stop|`;
* commission 0.03 % and 1 tick of slippage by default;
* direction and date-window filters. A call the strategy does not take
  closes any position it still holds.

The panel scoreboard and the Strategy Tester can disagree slightly. The
scoreboard always assumes the stop filled first, while TradingView's broker
emulator guesses the path inside the bar. The strategy also enters one bar
later, at the next open.

---

## 11. Known limitations

* **One structure level.** The engine tracks one swing length. It has no
  separate "internal" and "swing" structure, so what counts as a CHoCH depends
  on the swing length you choose.
* **Order blocks are approximations.** "The last opposite candle at the
  origin" is the most common written definition. Traders draw order blocks
  differently, and no single rule matches every one of them.
* **Swing lag.** Structure is known `L` bars late (§1). A larger swing length
  gives more meaningful structure and later setups.
* **Bar data only.** No order flow, volume profile or intrabar data is used.
  "Smart money" here is a set of price-pattern rules, not a view of
  institutional orders.
* **No guarantee.** The rules describe where SMC traders expect reactions.
  They do not make those reactions happen. Use the scoreboard and the strategy
  to measure how the rules behave on your market before relying on them.
