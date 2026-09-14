# Universal Regime Engine (FURE)

A market-agnostic, timeframe-agnostic context and signal engine for TradingView,
written in **Pine Script v6**.

| File | What it is |
| --- | --- |
| `indicators/Universal_Regime_Engine.pine` | The indicator. Chart overlay + full transparency panel. |
| `strategies/Universal_Regime_Strategy.pine` | The executable twin. Identical engine, plus order execution, sizing, scale-outs and trailing. |
| `METHODOLOGY.md` | Every formula, every threshold, and why each one is there. |

The two scripts share the **same engine source block**, copied verbatim, so the
strategy can never silently diverge from what the indicator draws.

---

## The one idea behind it

Most indicators break when you change instrument or timeframe because somewhere
inside them there is a number measured in the instrument's own price units — a
50-pip stop, a $2 filter, a "price moved 100 points" threshold. Move to another
symbol and that number means something completely different.

This engine has none. Every single measurement is one of three portable kinds:

| Kind | Examples here | Why it ports |
| --- | --- | --- |
| **ATR multiples** | trend slope, displacement, stop distance, over-extension | 1.5 ATR is the same *statement about this market* on BTCUSD at 100,000 and on EURUSD at 1.08 |
| **Bounded oscillators** | RSI, MFI, ADX / DI balance, Kaufman efficiency ratio | already 0–100 or −1…+1 by construction |
| **Self-referencing percentiles** | volatility percent-rank over its own history | calibrates itself to the instrument, no absolute assumption |

The higher-timeframe reference is **derived from the chart** (chart × N) rather
than hard-coded, so the multi-timeframe logic keeps the same proportions whether
you open a 15-second chart or a monthly one.

Lengths stay in **bars**, deliberately. A 20-bar efficiency window is the same
structural object on every timeframe; converting lengths to clock time would make
the engine behave differently per timeframe, which is exactly what we are trying
to avoid.

---

## Installing

1. TradingView → **Pine Editor** → *Open* → *New blank indicator*.
2. Delete the template, paste the contents of
   `indicators/Universal_Regime_Engine.pine`.
3. **Save**, then **Add to chart**.
4. Repeat with `strategies/Universal_Regime_Strategy.pine` if you want the
   backtestable version (paste into a *New blank strategy*).

No libraries, no imports, no external dependencies.

---

## Reading the panel

The panel is the point of the tool. Nothing in the score is hidden:

```
UNIVERSAL REGIME ENGINE   BTCUSD                 240
Confluence score   +48.3   ► ███··      ±100    7.00w
Regime             TREND UP                bars   34
Playbook           continuation

FACTOR             READING     BIAS       W     PTS
1 Trend slope      0.91 atr    ► ████·  1.50    18.4
2 Displacement     1.12 atr    ► ███··  1.00     8.0
3 Momentum (RSI)   61.4        ► ██···  1.00     6.5
4 Directional      27.3 adx    ► ██···  1.00     5.1
5 Structure        bullish     ► █████  1.50    19.6
6 Volume flow      58.2        ► █····  0.75     2.5
7 HTF 1D           0.44        ► ███··  1.25     7.9
```

* **READING** — the raw, unmodified measurement. Verify it against any other
  tool you trust.
* **BIAS** — that reading normalised to −1…+1 by a stated formula.
* **W** — the weight you assigned it.
* **PTS** — the exact number of score points this factor contributed *on this
  bar*. The PTS column sums to the score. That is the whole audit trail.

Below it: the volatility ruler (ATR% and its percentile), squeeze state,
over-extension damping, whether the volume feed is usable, and the current
stance with its stop, targets and a position-size hint.

Every intermediate value is also plotted to the **Data Window** (score, each of
the seven factor biases, ATR%, volatility percentile, raw slope and
displacement in ATR), so you can inspect any historical bar, not just the last.

---

## The five regimes and the three playbooks

| Regime | Detected by | Playbook in Auto mode |
| --- | --- | --- |
| **COMPRESSION** | Bollinger bands inside Keltner channels | stand aside, wait for the release |
| **TREND UP / DOWN** | ADX above floor **and** \|score\| above 60% of entry threshold | continuation — enter when the score pushes through ±threshold |
| **VOLATILE RANGE** | ATR in the top percentile band, no directional agreement | reversion, with wider expectations |
| **RANGE** | everything else | reversion — enter when the score recovers out of an extreme *after* a stretched move |
| *(any)* | the squeeze releasing with the score already leaning | breakout |

You can force a single playbook (`Trend-following only`, `Mean-reversion only`,
`Breakout only`) if you want to study one behaviour in isolation.

---

## Repainting: stated plainly

* `request.security` uses `lookahead_off`, and with **Use last CLOSED HTF bar**
  on (the default) it reads the previous *completed* higher-timeframe bar. No
  future leak.
* Swing pivots confirm `pivot strength` bars **after** they form. Market
  structure therefore updates *late*, never early. That lag is inherent to
  pivots and is disclosed rather than hidden.
* With **Only evaluate on closed bars** on (the default) signals are emitted on
  bar close, so a live bar cannot paint and un-paint an arrow.
* Turn that option off and you get faster, intrabar-mutable signals. That is a
  deliberate trade-off — the setting names it.

---

## Tuning notes

The defaults are round, standard numbers chosen because they are conventional,
**not** because they maximised a past P&L. Sensible adjustments:

| Situation | Adjust |
| --- | --- |
| Very fast timeframes (≤ 5m), lots of noise | raise *Score smoothing* to 3–5, raise *Cooldown*, raise *Entry threshold* toward 45 |
| Weekly / monthly charts | lower *Pivot strength* to 2–3 so structure still updates within your holding period |
| Instrument without real volume (many FX / index / CFD feeds) | nothing — the engine detects it and drops the volume factor automatically, rescaling the remaining weights |
| 24/5 FX vs 24/7 crypto vs session-bound equities | nothing — `ta.tr(true)` accounts for gaps, so session breaks do not distort the ATR ruler |
| You want pure trend behaviour | set weights 3/6 to 0, raise *Trend slope* weight |
| You distrust the higher timeframe | set *HTF mode* to `Off`; the weight is removed from the denominator and the score stays on the same scale |

Changing the *Auto multiple* from 4 changes the HTF for every chart at once:
4 gives 5m→20m, 1h→4h, 1D→4D.

---

## What this does not claim

It does not forecast price, and it is not tuned for a win rate. It is a
measuring instrument: it tells you, in portable units, what kind of market you
are in, how much of the evidence agrees, and where the risk on a trade would sit
if you took one. The signals are a worked example of applying those readings
consistently — not a promise.

Research and education only. Not financial advice.
