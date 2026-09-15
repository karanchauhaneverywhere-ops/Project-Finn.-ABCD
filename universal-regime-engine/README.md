# Universal Regime Engine (FURE)

A market-agnostic, timeframe-agnostic context and signal engine for TradingView,
written in **Pine Script v6**.

| File | What it is |
| --- | --- |
| `indicators/Universal_Regime_Engine.pine` | The indicator. Chart overlay + full transparency panel. |
| `strategies/Universal_Regime_Strategy.pine` | The executable twin. Identical engine, plus order execution, sizing, scale-outs and trailing. |
| `METHODOLOGY.md` | Every formula, every threshold, and why each one is there. |
| `tools/check_engine_drift.py` | Fails if the shared engine block has drifted between the two scripts. |

The two scripts share the **same engine source block**, copied verbatim between
`>>>>> ENGINE BLOCK START` and `<<<<< ENGINE BLOCK END` markers, so the strategy
cannot silently diverge from what the indicator draws. TradingView has no way to
share code between two *unpublished* scripts — a Pine `library()` must be published
before it can be imported — so the duplication is deliberate. Run

```bash
python3 tools/check_engine_drift.py
```

after editing the engine; it exits non-zero and prints a diff if the two copies no
longer match. Display-only inputs deliberately live *outside* the marked block, so
the strategy never carries an input that does nothing.

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

## Running both on one chart

The two scripts draw the same layers. With both loaded and both drawing you get two
adaptive MAs, two sets of structure lines, two sets of arrows and two panels on top
of each other — it looks like a rendering bug and is really just double-drawing.

So they ship pre-divided — **the indicator is the display, the strategy is the
execution**:

| | Indicator | Strategy |
| --- | --- | --- |
| MA, ribbon, bar colour, structure, arrows, shading | **on** | **off** |
| Dashboard panel | **on**, top right | **off** |
| Live stop / target of the open trade | — | **on** (the indicator has no open trade) |

Only one panel renders. Everything the strategy alone knows — position, P&L,
drawdown — is already in TradingView's Strategy Tester below the chart, so a second
panel repeating it costs screen height and adds nothing.

Running the strategy *without* the indicator? Turn its layers back on in **⑦
Visuals**; each toggle says so in its tooltip, and its panel defaults to the
opposite corner so even both-on does not overlap.

**Tight on screen height?** Set the indicator's **Panel detail** to `Compact ·
essentials only` — 12 rows instead of 25, keeping score, regime, playbook, entry
trigger and the full active setup, dropping the factor breakdown and context block.

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

## What the chart draws

| Element | What it tells you |
| --- | --- |
| **Adaptive MA + ribbon** | Trend reference, with bands at ±0.6 and ±1.2 ATR. The ribbon's *width* is a live read on volatility — it breathes as ATR expands and contracts |
| **Bar colour** | Solid = score past the entry threshold, faded = leaning, grey = no edge |
| **Risk / reward zones** | Stop zone and target zone as shaded boxes, T1/T2 dotted inside. The ratio between the two boxes *is* the R multiple, readable without arithmetic |
| **Bold line + ENTRY tag** | The armed trigger price, and the bar price confirmed it |
| **Grey background** | Compression — volatility contracting |
| **Step line + BOS/CHoCH tags** | The active structure level and the breaks that set it |

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

## The entry moment

A signal means *the evidence has lined up*. It does not mean *buy here*. Those are
different moments, and the engine now separates them.

**Confirm mode (default).** A signal only **arms** a setup, at the signal bar's high
for a long or its low for a short. The entry moment is the later bar where price
actually trades through that level. You see:

| On the chart | Meaning |
| --- | --- |
| Small faded triangle | Signal — setup **armed** |
| Bold line extending right | The exact price that confirms it |
| **ENTRY** label | Price took the level out — this is the moment |
| Small ✕ | The setup lapsed: price never confirmed, or the score faded first |

The panel's **Entry trigger** row shows the armed price, which direction confirms it,
and how many bars remain before it lapses.

Everything downstream — stop, targets, R, size — is built from the **trigger price**,
not the signal bar's close, so the numbers describe the trade you would actually get.

Two alert tiers follow the same split: *armed* gives you time to get ready, *ENTRY*
is the one you act on.

**Immediate mode** restores the old behaviour: the signal bar is the entry moment.

Why this matters: a signal price refuses to confirm is exactly the signal you did not
want. In confirm mode those cost you nothing — they lapse untriggered instead of
becoming trades. The strategy implements this as a resting **stop order** at the
armed level, cancelled if the setup lapses, which is also the more realistic fill
assumption.

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
* A displayed setup is **invalidated** when price trades through its stop or
  reaches T3, not only when the score fades. A hard reversal can take the score
  from +40 to −40 without ever crossing the stand-aside band, so without that check
  the panel would keep showing a long that was stopped out hundreds of bars ago.
  The panel says which of the three ended it.

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
| You distrust the higher timeframe | set *HTF mode* to `Off` (or weight 7 to 0); the weight leaves the denominator, the score stays on the same scale, and no `request.security` call is issued at all |
| Structure keeps gating entries you want | lower *Structure memory*; the state now expires at that age instead of biasing the score forever |

Changing the *Auto multiple* from 4 changes the HTF for every chart at once:
4 gives 5m→20m, 1h→4h, 1D→4D.

---

## Backtesting the strategy honestly

The strategy's order layer is where backtests usually lie. What it does, and what
it cannot fix:

* Fills land on the **next bar's open**. No `process_orders_on_close`.
* Commission (0.03%) and 1-tick slippage are on by **default**.
* `margin_long`/`margin_short` are 100 and size is capped by *Max position
  notional*, so a tight stop cannot silently buy many times equity.
* The protective stop is submitted in the same block as the entry, so a position
  is never naked for its first bar.
* Stops only ever tighten. A close beyond the stop exits at market rather than
  moving the stop to meet price.
* Scale-outs are **absolute thirds** of the entry quantity and each leg is latched
  once it trades, so a filled target is never re-submitted behind the market.
* **Not fixable:** size is computed from the signal bar's close but fills at the
  next bar's open. On a gap the realised risk differs from the configured
  percentage. R is recomputed from the actual fill so the reported figures stay
  true, but the sizing itself cannot see the gap without lookahead.

---

## What this does not claim

It does not forecast price, and it is not tuned for a win rate. It is a
measuring instrument: it tells you, in portable units, what kind of market you
are in, how much of the evidence agrees, and where the risk on a trade would sit
if you took one. The signals are a worked example of applying those readings
consistently — not a promise.

Research and education only. Not financial advice.
