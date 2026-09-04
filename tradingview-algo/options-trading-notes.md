# Trading `strategy.pine` signals on Indian index/stock options

`strategy.pine` (CTS2) generates directional signals off the **underlying**
index or stock price (NIFTY, BANKNIFTY, SENSEX, FINNIFTY, or a stock). If
you plan to act on those signals by buying/selling **options** rather than
the underlying or futures, read this first — it's the single biggest reason
a good-looking underlying backtest turns into a losing options account.

## Why a spot-price backtest doesn't equal option P&L

The strategy's backtested P&L assumes you traded the underlying directly.
An option's premium is a function of:

- **Delta** — how much the premium moves per point of underlying move (an
  ATM option is roughly 0.5; far OTM can be 0.1 or less). A signal that's
  worth ₹100 on the underlying might only move the premium ₹20–50
  depending on strike.
- **Theta (time decay)** — premium bleeds every day, and accelerates hard
  in the final days before weekly expiry. A signal that's technically
  "right" on direction can still lose money if it takes too long to play
  out, especially on 0-2 DTE (days to expiry) weekly options.
- **IV (implied volatility)** — premiums can drop on a correct move if IV
  crushes at the same time (common right after budget/RBI/earnings
  events, or into expiry).
- **Bid-ask spread and liquidity** — far OTM and illiquid stock option
  strikes can have wide spreads that eat into any edge the signal has.

None of this is modeled by a Pine strategy backtest on the underlying. Do
not assume your backtested win rate or R:R carries over to options premium
trading.

## Practical guidelines if you trade options off these signals

1. **Prefer ATM or near-ATM strikes** (delta ~0.4–0.6) for directional
   trades — they track the underlying more linearly and have tighter
   spreads than far OTM "lottery ticket" strikes.
2. **Prefer the current/next weekly expiry with enough time left** — avoid
   entering fresh option-buying positions in the last few hours of expiry
   day, where theta and gamma risk explode (this is why `strategy.pine`
   defaults to closing everything by 15:00–15:30 and has a max-bars-in-trade
   exit).
3. **Consider index futures instead of options** for signals meant to be
   held for hours (futures P&L tracks the underlying signal directly, no
   theta/IV distortion) — options make more sense for short, high-conviction
   moves where you're comfortable with the extra decay risk.
4. **Size by premium risk, not underlying risk.** The strategy's position
   sizing (`riskPerTradePct` ÷ stop distance) is computed in underlying
   points. If you convert a signal into an option trade, size the number of
   lots so that (stop-loss premium level − entry premium) × lot size ×
   quantity stays within the same rupee risk, not just because "1 lot"
   sounds small — options risk is on the premium, not the underlying's
   move.
5. **Respect lot sizes and exchange-mandated freeze quantities** (NSE caps
   the max order size per single order for index options — split larger
   orders if needed).
6. **Don't treat a directional signal as an income (selling) strategy
   without separately managing margin and tail risk.** Selling options
   (credit strategies) has a very different risk profile — undefined/large
   loss on a wrong move — from the long-option or futures use case this
   strategy was built around. If you want a premium-selling variant, say so
   explicitly and it needs its own risk framework (defined-risk spreads,
   not naked selling).

## What automation would need (if you extend the webhook relay)

The `alert()` payloads from `strategy.pine` only carry the underlying's
`action` (buy/sell), `price`, `stop`, and `target` — they do not pick a
strike or expiry. A relay/bot that trades options off these alerts needs to
add:

- Strike selection logic (e.g. nearest ATM strike from the option chain at
  alert time).
- Expiry selection (current weekly vs next, with a cutoff to skip
  same-day expiry after a configurable time).
- Premium-based stop/target conversion (see point 4 above) — do not pass
  the underlying's `stop`/`target` values straight through as premium
  levels, they're in underlying points, not premium rupees.
- A hard rule to flatten all option positions before end of day for
  intraday use, since theta risk continues even if you stop watching.

This is broker/data-vendor specific (you need a live option chain feed),
so it's a separate build from the Pine script itself — let me know which
broker/API you'd use (e.g. Zerodha Kite Connect, Upstox, Fyers, Angel One
SmartAPI) and I can help build that relay layer next.
