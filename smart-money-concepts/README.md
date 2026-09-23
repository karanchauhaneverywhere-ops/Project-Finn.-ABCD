# Smart Money Concepts Signals (FSMC)

Rule-based **Smart Money Concepts** BUY / SELL calls for TradingView, written in
**Pine Script v6**.

| File | What it is |
| --- | --- |
| `indicators/Smart_Money_Concepts_Signals.pine` | The indicator. BUY / SELL labels with a quality grade, stop and targets, order-block and FVG zones, BOS / CHoCH, a results panel and alerts. |
| `strategies/Smart_Money_Concepts_Strategy.pine` | The backtestable twin. Same engine, and it trades every call the indicator prints. |
| `METHODOLOGY.md` | Every rule, every threshold, and why each one is there. |

The two scripts share the **same engine block, copied byte for byte**, so the
backtest can never silently drift from what the indicator shows.

---

## What a call means

SMC traders mark the same few things by eye: where the stops are (liquidity),
when structure really breaks, and the zone the move started from (the order
block). This indicator turns each of those into an exact rule. The same chart
always gives the same calls, and a call is never redrawn after it prints.

A **BUY** prints when all of these happened, in this order:

1. **Structure broke up.** A candle **closed** above the last swing high. Wicks
   don't count. Against a downtrend this is a **CHoCH** (change of character);
   inside an uptrend it is a **BOS** (break of structure).
2. **With displacement.** The move that broke it had a strong candle (body ≥ 1 ATR)
   or left a **fair value gap**. Slow, drifting breaks are ignored.
3. **Price came back to the order block.** This is the last down-candle where the
   breaking move started.
4. **In discount.** The retest happened in the lower half of the move, never
   near its top.
5. **Rejection.** A candle touched the zone and **closed green**. The BUY prints
   at that close.
6. **With the higher timeframe.** The higher-timeframe structure is also
   bullish (auto-selected: 15m → 1H, 1H → 4H, 1D → 4D).

A **SELL** is the mirror image. The stop sits beyond the lowest price since the
move started, plus a small ATR buffer. TP1 / TP2 / TP3 are 1R / 2R / 3R, where R
is the distance to the stop.

### Grades

Each call scores one point for each extra confluence it has:

| Confluence | Meaning |
| --- | --- |
| **Liquidity sweep** | The move started with a stop run: a wick through an old swing low (for a BUY) that closed back above it. |
| **Fair value gap** | The breaking move left an imbalance, which shows real displacement. |
| **Deep entry (OTE)** | The retest reached a ≥ 61.8 % retracement of the move. |

`A+` = 3 of 3, `A` = 2 of 3, `B` = 1 of 3. The default **Minimum grade is A**,
so only calls with at least two confluences are shown.

---

## Installing

1. TradingView → **Pine Editor** → *Open* → *New blank indicator*.
2. Delete the template and paste the contents of
   `indicators/Smart_Money_Concepts_Signals.pine`.
3. **Save**, then **Add to chart**.
4. To backtest, paste `strategies/Smart_Money_Concepts_Strategy.pine` into a
   *New blank strategy* and open the **Strategy Tester** tab.

No libraries, no imports, no external dependencies.

---

## Reading the chart

| You see | It means |
| --- | --- |
| Green **BUY A+ / A / B** label under a candle | A long call, entered at that candle's close. |
| Red **SELL** label above a candle | A short call. |
| Grey / red / green lines after a call | Entry, stop, TP1 / TP2 / TP3 while the call is open. The stop moves to entry (breakeven) after TP1. |
| Tags to the right of the last candle | Exact prices of the open call. |
| Coloured box labelled `CHoCH · OB` or `BOS · OB` | An **armed** setup: the order block price must return to. It grows until it fires, fails or expires. |
| Lighter box labelled `FVG` | The fair value gap inside the breaking move. |
| Dotted grey line next to an armed zone | The entry limit (the 50 % equilibrium by default). A call only prints on the discount side of it (premium side for sells). |
| Solid line + `CHoCH`, dashed line + `BOS` | Structure breaks: the swing that was closed through. |
| `×` marks *(off by default)* | Liquidity sweeps. Turn on *Liquidity pools & sweeps* to also see the dotted pools. |

### The panel

Layout example (the values are illustrative, not a result):

```
SMC SIGNALS                EURUSD · 60
Structure                   ▲ bullish
HTF bias · 240              ▲ bullish
Armed setup          buy zone · 6 bars
OPEN CALL
Call                    BUY A · 4 bars
Entry                         1.08412
Stop                   1.08412  (BE)
TP1 / TP2 / TP3   1.08527 ✓ / 1.08642 / 1.08757
RESULTS ON THIS CHART
Closed calls               37  (+1 open)
Reached TP1 / TP2 / TP3   51% / 32% / 22%
Net (⅓ at each TP) · PF     +9.4R · PF 1.41
```

**Results on this chart** follows every past call bar by bar until its stop, its
last target or an opposite call. The net figure assumes one third is closed at
each target. When a single candle touches both the stop and a target, the stop
counts as filled first, so the scoreboard leans pessimistic. The numbers are
for the symbol and timeframe you are looking at. Nothing is carried over from
anywhere else.

---

## Alerts

*Create alert* → condition **FSMC** → then either:

* **Any alert() function call**: the detailed version. Every call arrives with
  its entry, stop, TP1–TP3 and risk in ATR, followed by updates ("TP1 hit",
  "stopped after TP1 (breakeven)", …) as the call plays out.
* Or one of the simple conditions: **FSMC · BUY call**, **FSMC · SELL call**,
  **FSMC · Any call**, **FSMC · Change of character**.

Every alert fires once, at bar close.

---

## Settings that matter

The defaults are conventional round numbers. They were **not** picked because
they maximised a past P&L.

| You want… | Change |
| --- | --- |
| Fewer, cleaner calls | *Minimum grade* → `A+`, or *Swing length* 5 → 8–10 |
| More calls | *Minimum grade* → `B`, and/or *Entry zone* → `Order block or FVG` |
| Only reversals (sweep → CHoCH → retest) | *Trade which breaks* → `CHoCH only (reversals)` |
| Only trend continuation | *Trade which breaks* → `BOS only (continuations)` |
| Very fast charts (≤ 5m) | *Swing length* 7–10, keep the HTF filter on |
| Weekly / monthly charts | *Swing length* 3 so structure still updates |
| A fixed HTF (e.g. always the 4H) | *Higher-timeframe bias* → `Manual`, pick the timeframe |
| To trade against the HTF | *Higher-timeframe bias* → `Off` (not recommended) |

Every size (displacement, gap, zone height, stop buffer, stop limits) is in
**ATR**, so one set of settings behaves the same on FX, indices, stocks and
crypto. Instruments without volume need nothing special, because volume is not used.

---

## Repainting: stated plainly

* Everything is decided on **bar close**. A printed call never disappears, and a
  live candle never flashes one.
* Swing points confirm *swing length* bars after they form, so structure
  updates **late, never early**. That lag is inherent to swings.
* The HTF bias reads the last **closed** higher-timeframe bar
  (`expression[1]` with `lookahead_on`, TradingView's documented
  non-repainting form).
* Order-block boxes start at a candle in the past, but they are only created
  on the bar the break confirmed, using data that existed on that bar.

---

## About "accuracy"

No indicator is accurate in the sense of being right every time, and this one
does not claim to be. What it does:

* It only calls setups where the whole SMC sequence lines up: a displaced
  break, an order-block retest in discount/premium, a rejection close, and
  higher-timeframe agreement.
* It **grades** each call on the optional extras (sweep, FVG, deep entry), so
  you can filter down to the best ones.
* It **measures itself**. The panel shows the real hit rate and net R of every
  call on your chart. The strategy lets you backtest the same calls with
  commission and slippage.

Check those numbers on your own market and timeframe. Forward-test on a demo
account, and risk a small fixed fraction per call. Hit rates differ between
instruments, timeframes and market regimes, and past results do not carry over
to the future.

Research and education only. Not financial advice.
