# Backtesting & Validation Guide

A single backtest number (e.g. "68% win rate on BTCUSD 1H, last 2 years")
is close to meaningless on its own. Use this checklist before trusting or
trading any strategy, including `strategy.pine`.

## Indian markets specifics

- **Data**: TradingView's NSE data for indices (NIFTY, BANKNIFTY, SENSEX,
  FINNIFTY) and stocks is generally good for backtesting the underlying.
  Backtesting actual **option premium** history requires an options-chain
  data source Pine doesn't have natively — see `options-trading-notes.md`
  for why the strategy backtests the underlying, not the option.
- **Test across expiry cycles**, not just calendar time — weekly expiry
  days (and the day after a big move) behave differently (higher
  gap/whipsaw risk) from a normal mid-week session.
- **Segment-specific volatility regimes**: backtest separately across at
  least one strong trending period (e.g. a multi-month rally or selloff)
  and one range-bound/choppy period (common in Indian indices between
  major catalysts) — a strategy tuned only on a trending stretch will get
  chopped up in the next range.
- **Costs**: set commission/slippage to match your actual broker
  (brokerage + STT + exchange charges + GST for the segment you trade —
  intraday equity, F&O futures, and options each have different cost
  structures) rather than the script's generic defaults.
- **Circuit limits & liquidity**: illiquid stock options can gap through
  stops — a backtested stop-loss price is not guaranteed to be your actual
  fill in a fast or illiquid move.

## 1. Sample size

- Require at least 100 closed trades in the backtest before drawing any
  conclusion. Fewer than that and the win rate is mostly noise.
- Test across multiple market regimes: a trending bull run, a range-bound
  period, and a sharp drawdown/crash period. A strategy that only works in
  one regime will lose money when that regime ends.

## 2. Walk-forward testing (avoid curve-fitting)

1. Split history into an **in-sample** window (e.g. first 70%) and an
   **out-of-sample** window (remaining 30%).
2. Tune inputs (EMA lengths, ATR multiples, risk %) only on the in-sample
   window.
3. Run the *unchanged* settings on the out-of-sample window. If
   performance collapses, the strategy was overfit to the in-sample data
   — go back and simplify, don't just re-tune on the new window too.
4. Repeat on a second, different symbol without changing settings. A
   strategy that only works on the one pair it was tuned on isn't robust.

## 3. Metrics that matter more than win rate

In TradingView's Strategy Tester "Performance Summary" tab, look at:

- **Profit factor** (gross profit / gross loss) — want > 1.3 at minimum,
  ideally > 1.5, across the full test.
- **Max drawdown** (equity, not just closed trades) — ask yourself if you
  could psychologically and financially withstand that drawdown live.
- **Average win / average loss ratio** vs win rate — a 45% win rate with
  2:1 average win:loss is profitable; an 80% win rate with 1:3 win:loss
  is not.
- **Sharpe/Sortino ratio** if available — reward relative to volatility of
  returns, not just total return.
- **Largest losing streak** — size positions so this streak doesn't wipe
  out the account (this is what the 1% risk/trade default is for).

## 4. Costs

Make sure commission and slippage are set realistically for your
broker/exchange (the strategy defaults to 0.05% commission, 2 ticks
slippage — adjust to match your actual venue). Strategies that look great
with zero costs often turn negative once real costs are included,
especially on shorter timeframes.

## 5. Forward test before going live

1. **Paper trade** the strategy in real time (TradingView's paper trading,
   or your broker's paper account) for at least several weeks and a
   meaningful number of trades.
2. Compare paper-trading results to the backtest for that same period —
   large discrepancies mean the backtest had look-ahead bias, unrealistic
   fills, or the market regime changed.
3. Start live with a small size (e.g. a fraction of your intended
   capital) and scale up only after the strategy proves itself with real
   fills and real emotions involved.

## 6. Ongoing monitoring

- Re-check performance periodically (e.g. monthly). Markets change;
  a strategy that stops working is a signal to pause and re-validate, not
  to override the stop losses "just this once."
- Keep a trade log (entry/exit reason, size, result) separate from the
  platform's own report — it's the fastest way to notice if live
  execution is drifting from backtest assumptions (slippage, missed
  fills, alert delays).
