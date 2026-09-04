# Confluence Trend Strategy v2 (CTS2) — TradingView Algo Setup

## Read this first: about "89% win rate, forced"

No trading strategy — algorithmic or discretionary — can guarantee an 89%
(or any fixed) success rate, and no amount of Pine code can force one to be
true in live markets. Claims like that are marketing, not statistics that
hold up on unseen future data. Two things this repo will **not** do:

- Ship a script tuned to show a high win rate on one historical chart
  (that's overfitting, which is very likely part of why v1 failed live —
  see "What changed in v2" below).
- Fake it by using a take-profit so tight and a stop so wide that most
  trades "win" a tiny amount right up until one loss wipes out the last
  20 wins — a common trick vendors use to advertise high win rates while
  the strategy is actually unprofitable.

What it does instead: give you a transparent, adjustable, risk-managed
strategy plus a real backtesting workflow, so you can measure its actual
performance on the markets and timeframes you care about. Good systematic
strategies usually run 40-60% win rate with a favorable risk/reward and
positive expectancy, not 80%+.

## What changed in v2 (based on v1's real-time failure)

v1 lost money, rarely traded, and entered late. Root causes and fixes:

| Problem | v1 | v2 fix |
|---|---|---|
| Entries chased the move | Fired on EMA/MACD crossover bar itself | Waits for a pullback to EMA Fast + a confirming candle before entering |
| Barely traded | Required *all* 6 filters to agree simultaneously | Confluence **score** (configurable, default 4-of-5) — trend is still mandatory, the rest just need to hit the threshold |
| Losses outweighed wins | Pure ATR stop, no breakeven management | Structure-based stop (recent swing high/low, ATR floor) + move to breakeven and trail after +1R |
| No account-level protection | None | Daily circuit breaker: max trades/session, max losses/session, max daily loss % — caps how bad a bad day can get, independent of the win rate |
| Not built for Indian markets | Generic 24/7 script, no session logic | Default NSE session (09:15–15:00 entries, flatten by 15:30), session VWAP filter, expiry/near-close awareness |

This is a genuine mechanism change, not a re-tuned version of the same
crossover-chasing logic — but it still needs to be backtested and
paper-traded on your actual instruments before you trust it (see
`BACKTESTING_GUIDE.md`). If it still underperforms, tell me the actual
numbers (win rate, profit factor, trade count, which instrument/timeframe)
and I'll diagnose further — that's how this gets fixed for real, not by
raising the promised number.

## v2.1 — autopsy of a real 20-trade backtest (25% win rate)

A real backtest (NIFTY/BANKNIFTY-type instrument, 15min-1H, underlying/
futures, Strategy Tester) came back 5/20 profitable. The diagnosis, worked
from the actual numbers instead of guesswork:

- Average win ₹392.99 vs average loss ₹420.52 → **realized reward:risk was
  ~0.93:1**, against a designed 1.8:1. That inversion, not the 25% win rate
  itself, is what made profit factor only ~0.31.
- Ruled out via data: not a long/short directional bug (wins and losses
  were mixed across both directions) and not the end-of-day flatten
  (winning trades exited through the normal stop/target bracket, not the
  session-close rule).
- Root cause: the ATR trailing stop and the breakeven move both triggered
  at the same +1R mark, so the (too-tight, 1.2x ATR) trail started
  choking winners the instant they went 1R in profit — well before they
  could reach the 1.8R target.
- Fix applied: target lowered to 1.3R (realistic for one NSE session
  instead of rarely-hit 1.8R), and trailing now only activates once a
  trade reaches `trailActivateRMult` (default 1.15R) — after breakeven,
  before target — using a wider 2.0x ATR distance so it acts as a safety
  net instead of the primary profit-taker.

This was a targeted fix to the one thing the data implicated, not a
re-tune of the entry logic (which the data showed was not the problem).
Re-run the backtest on the same instrument/period and compare average
win vs average loss again — that ratio, not the win rate alone, is the
number that tells us whether this fix worked.

## What's in here

| File | Purpose |
|---|---|
| `strategy.pine` | Pine Script **v6** strategy — pullback entries, scored confluence (trend/momentum/VWAP/volume/no-chop), structure+ATR stops, breakeven/trailing management, daily circuit breaker, NSE session defaults, on-chart dashboard. |
| `BACKTESTING_GUIDE.md` | How to backtest, walk-forward test, and paper-trade this (or any) strategy properly before using real money. |
| `options-trading-notes.md` | **Read before trading options off these signals.** Why a spot-price backtest ≠ option premium P&L, and how to translate signals to strikes/expiry sensibly. |
| `alert-webhook-template.json` | Payload format the strategy's `alert()` calls emit, for wiring into a broker/bot via TradingView webhooks. |

## How the strategy decides to trade

Trend direction is mandatory (never trade against it); the other four
signals are scored, and you need `minScore` of them (default 4 of 5) —
this scoring, instead of v1's "all must agree," is what fixes the
too-few-trades problem without dropping quality control:

1. **Trend (mandatory)** — 21 EMA vs 50 EMA aligned, price on the correct
   side of the 200 EMA, and a higher timeframe (default 1H) confirms the
   same direction.
2. **Momentum** — MACD line vs signal line agrees with direction *and* the
   histogram is expanding, RSI is on the correct side of center without
   being extended past 80/20.
3. **Session VWAP** — price on the correct side of the day's VWAP (a
   standard intraday index/options reference level).
4. **Participation** — volume at/above its 20-period average.
5. **Trend strength** — ADX above a threshold (default 18), filtering out
   choppy/ranging conditions.

Then it waits for a **pullback + confirmation candle** (price pulls back
near the fast EMA, then a candle closes back in the trend direction)
before entering — this is what fixes late/chasing entries.

Risk management, not signal accuracy, is what makes the strategy viable:

- Position size is calculated from a fixed **% of equity risked per
  trade** (default 1%) divided by the stop distance — not a fixed
  share/contract/lot count.
- Stop loss = the more conservative of a recent swing high/low or an ATR
  floor, so normal noise doesn't clip the stop before the real move.
- Take profit = stop distance × reward:risk multiple (default 1.8×).
- Stop moves to breakeven at +1R, then trails by ATR — this directly
  targets "losses outweighing wins" by capping how much a winner gives
  back and taking bad trades off the table at zero once they've proven
  themselves.
- **Daily circuit breaker**: trading stops for the session after N trades,
  N losses, or X% equity drawdown for the day — independent of what the
  signals say. This is standard practice for Indian index/options
  day-trading, where a few bad trades in a row can otherwise spiral.
- Session defaults to NSE hours with entries cut off before 15:00 and a
  forced flatten by 15:30 — relevant for intraday index/options trading
  where holding into the close (or into expiry) carries extra risk.
- A max-bars-in-trade exit closes trades that go nowhere.

An on-chart dashboard (top-right) shows live long/short score, ADX,
trades/losses today, and whether the circuit breaker has tripped, so you
can see *why* it is or isn't taking a trade in real time.

## Setup on TradingView

1. Open TradingView → **Pine Editor** (bottom panel).
2. Create a new script, delete the boilerplate, and paste in the full
   contents of `strategy.pine`.
3. Click **Add to Chart** on a NIFTY/BANKNIFTY/SENSEX or stock chart.
   Open **Strategy Tester** (bottom panel) to see backtest results (net
   profit, win rate, profit factor, max drawdown, etc.).
4. Use the gear icon to adjust inputs — `minScore`, risk %, session
   times, ADX threshold, long/short toggles — per instrument.
5. Follow `BACKTESTING_GUIDE.md` before trusting any single backtest
   number, and read `options-trading-notes.md` before mapping signals to
   option strikes.

## Turning signals into automated trades (optional)

TradingView alerts can't place broker orders by themselves — you need a
webhook relay to a broker/bot (e.g. a small serverless function, or a
service like your broker's own webhook bridge if it offers one).

1. On the chart with the strategy applied, click **Alert** → condition:
   "Confluence Trend Strategy (CTS)" → "Any alert() function call".
2. Set **Webhook URL** to your relay endpoint.
3. The message body is generated by the script's `alert()` calls — see
   `alert-webhook-template.json` for the exact JSON shape
   (`action`, `symbol`, `price`, `stop`, `target`).
4. Your relay/bot is responsible for actually placing and managing the
   order with your broker's API, and for its own risk controls (daily
   loss limit, duplicate-alert protection, kill switch). That part is
   broker-specific — say which broker/exchange you'd use and I can help
   build that relay next.

## Honest expectations

- Backtest results are a starting point, not a promise — always forward
  test (paper trade) before going live; see `BACKTESTING_GUIDE.md`.
- Past performance, in backtest or live, does not guarantee future
  results.
- Trading involves risk of loss. Position sizing (1% risk/trade here) is
  what keeps a string of losses from being ruinous — do not increase it
  to chase a higher win-rate claim.
