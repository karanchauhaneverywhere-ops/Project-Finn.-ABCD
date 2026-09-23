"""Bar-by-bar Python port of indicators/Big_Player_Footprint.pine.

Used to test the signal logic and the scoreboard outside TradingView on the
real OHLCV test bed in datasets.py. Defaults mirror the Pine inputs.

Known differences from TradingView: the higher timeframe is approximated by
grouping chart bars, pivots use strict inequalities on both sides, and the
delta source is always the bar approximation.

    pip install pandas numpy pyarrow backtesting
    python3 reference_port.py            # defaults, every dataset, IS / OOS split
"""
import math
from collections import deque
import numpy as np
import pandas as pd

P = dict(
    # effort
    volLen=50, todLen=20, todMin=10, zWhale=2.0,
    # flow
    flowLen=20, flowFull=0.20, vwLen=50,
    # liquidity & setups
    atrLen=14, liqLeft=10, liqRight=3, liqMax=10, liqAge=300,
    useSweep=True, useAbs=True, useFvg=True,
    absZ=1.5, absSpread=0.9, locLen=20,
    dispATR=1.5, dispBody=0.6, fvgMinATR=0.1, fvgAge=30, confirmN=3,
    # conviction
    wEff=30, wFlow=20, wHtf=20, wLoc=15, wLiq=15, minConv=60, liqCtx=20,
    htfMult=4, htfLen=50, htfFull=0.5, cooldown=5,
    # accuracy features (Pine ② and ④)
    rangeProxy=True, adaptive=True, adMin=20, adWin=30,
    htfGate="Off",                     # "Off" | "Continuation setups only" | "All setups"
    # geometry
    stopATR=1.5, tgtR=1.5, horizon=30, warmup=100,
)


# ---------------------------------------------------------------- primitives
def rma(x, n):
    out = np.full(len(x), np.nan); s = None; acc = 0.0; cnt = 0
    for i, v in enumerate(x):
        if np.isnan(v):
            continue
        if s is None:
            acc += v; cnt += 1
            if cnt == n:
                s = acc / n; out[i] = s
        else:
            s += (v - s) / n; out[i] = s
    return out


def true_range(h, l, c):
    pc = np.r_[np.nan, c[:-1]]
    return np.where(np.isnan(pc), h - l, np.maximum(h - l, np.maximum(abs(h - pc), abs(l - pc))))


def ema(x, n):
    out = np.full(len(x), np.nan); a = 2 / (n + 1); s = None; buf = []
    for i, v in enumerate(x):
        if s is None:
            buf.append(v)
            if len(buf) == n:
                s = float(np.mean(buf)); out[i] = s
        else:
            s = a * v + (1 - a) * s; out[i] = s
    return out


def pivots(x, L, R, high=True):
    """Level confirmed at bar i (pivot at i-R), else nan."""
    out = np.full(len(x), np.nan)
    s = pd.Series(x)
    lmax = s.shift(1).rolling(L).max().values if high else s.shift(1).rolling(L).min().values
    rmax = s[::-1].shift(1).rolling(R).max().values[::-1] if high else s[::-1].shift(1).rolling(R).min().values[::-1]
    for c in range(L, len(x) - R):
        v = x[c]
        if high and v > lmax[c] and v > rmax[c]:
            out[c + R] = v
        if not high and v < lmax[c] and v < rmax[c]:
            out[c + R] = v
    return out


def htf_slope(df, rule_or_n, p):
    """Last CLOSED htf bar's EMA slope (ATR per 5 htf bars), mapped to chart bars."""
    g = np.arange(len(df)) // rule_or_n if isinstance(rule_or_n, int) else df.index.floor(rule_or_n)
    grp = df.groupby(g, sort=True)
    h = grp["High"].max().values; l = grp["Low"].min().values; c = grp["Close"].last().values
    e = ema(c, p["htfLen"]); a = rma(true_range(h, l, c), 14)
    sl = np.where(a > 0, (e - np.r_[np.full(5, np.nan), e[:-5]]) / a, 0.0)
    pos = pd.Index(sorted(pd.unique(g))).get_indexer(g)
    return np.where(pos >= 1, sl[np.maximum(pos - 1, 0)], np.nan)


def z_log(x, n, index, intraday, p):
    """Effort z-score of log(x): time-of-day baseline intraday, rolling otherwise."""
    lx = np.log(x + 1)
    s = pd.Series(lx)
    m = s.rolling(n).mean().shift(1).values
    sd = s.rolling(n).std(ddof=0).shift(1).values
    z = np.nan_to_num((lx - m) / np.maximum(np.nan_to_num(sd), 0.15))
    if intraday:
        a = 2 / (p["todLen"] + 1); mean = {}; var = {}; cnt = {}
        slots = index.hour * 60 + index.minute
        for i in range(len(lx)):
            k = slots[i]; c = cnt.get(k, 0)
            if c >= p["todMin"]:
                z[i] = (lx[i] - mean[k]) / max(math.sqrt(var[k]), 0.15)
            if c == 0:
                mean[k] = lx[i]; var[k] = 0.0
            else:
                d = lx[i] - mean[k]; mean[k] += a * d
                var[k] = (1 - a) * (var[k] + a * d * d)
            cnt[k] = c + 1
    return z


# ---------------------------------------------------------------- scoring
def resolve(i, book, o, h, l, c, horizon, sink):
    keep = []
    for tr in book:
        e, s, t, d, b, k = tr
        risk = abs(e - s); r = None; won = False
        if d > 0:
            if o[i] <= s: r = (o[i] - e) / risk
            elif l[i] <= s: r = -1.0
            elif h[i] >= t: r = (t - e) / risk; won = True
        else:
            if o[i] >= s: r = (e - o[i]) / risk
            elif h[i] >= s: r = -1.0
            elif l[i] <= t: r = (e - t) / risk; won = True
        if r is None and i - b >= horizon:
            r = d * (c[i] - e) / risk
        if r is None:
            keep.append(tr)
        else:
            sink(tr, won, r)
    return keep


def baseline(df, p):
    """Random long + short on every bar after warm-up, identical rules. Returns list of (bar, dir, won, R)."""
    o, h, l, c = (df[k].values.astype(float) for k in ("Open", "High", "Low", "Close"))
    atr = rma(true_range(h, l, c), p["atrLen"])
    book = []; out = []
    sink = lambda tr, won, r: out.append((tr[4], tr[3], won, r))
    for i in range(len(c)):
        book = resolve(i, book, o, h, l, c, p["horizon"], sink)
        a = atr[i]
        if i >= p["warmup"] and a > 0:
            risk = p["stopATR"] * a
            for d in (1, -1):
                book.append((c[i], c[i] - d * risk, c[i] + d * p["tgtR"] * risk, d, i, 0))
    return out


# ---------------------------------------------------------------- engine
def run(df, intraday, htf_rule, p=P):
    """Returns list of signal trades (bar, dir, type, won, R, conviction)."""
    o, h, l, c = (df[k].values.astype(float) for k in ("Open", "High", "Low", "Close"))
    v = np.nan_to_num(df["Volume"].values.astype(float))
    n = len(df)
    tr = true_range(h, l, c)
    atr = rma(tr, p["atrLen"])
    rng = h - l; body = abs(c - o)
    clv = np.where(rng > 0, ((c - l) - (h - c)) / np.where(rng > 0, rng, 1), 0.0)
    volOk = np.nan_to_num(pd.Series(v).rolling(20).mean().values) > 0

    vz = z_log(v, p["volLen"], df.index, intraday, p)
    if p["rangeProxy"]:
        # No volume feed: range expansion is the only effort evidence left.
        # True range in basis points of price, so the log is scale-free.
        rz = z_log(tr / c * 1e4, p["volLen"], df.index, intraday, p)
        vz = np.where(volOk, vz, rz)
        effOk = np.ones(n, bool)
    else:
        vz = np.where(volOk, vz, 0.0)
        effOk = volOk

    delta = clv * v
    sd = pd.Series(delta).rolling(p["flowLen"]).sum().values
    sv = pd.Series(v).rolling(p["flowLen"]).sum().values
    ndf = np.where(np.nan_to_num(sv) > 0, np.nan_to_num(sd) / np.where(np.nan_to_num(sv) > 0, sv, 1), 0.0)
    hlc3 = (h + l + c) / 3
    vs = pd.Series(v).rolling(p["vwLen"]).sum().values
    rv = np.where(volOk & (np.nan_to_num(vs) > 0),
                  pd.Series(hlc3 * v).rolling(p["vwLen"]).sum().values / np.where(np.nan_to_num(vs) > 0, vs, 1),
                  pd.Series(hlc3).rolling(p["vwLen"]).mean().values)
    sHtf = np.clip(np.nan_to_num(htf_slope(df, htf_rule, p)) / p["htfFull"], -1, 1)
    ph = pivots(h, p["liqLeft"], p["liqRight"], True)
    pl = pivots(l, p["liqLeft"], p["liqRight"], False)
    llPrev = pd.Series(l).rolling(p["locLen"]).min().shift(1).values
    hhPrev = pd.Series(h).rolling(p["locLen"]).max().shift(1).values

    bsl = []; ssl = []
    lastBull = lastBear = -10**9
    fL = fS = pL = pS = None
    lastSig = -10**9
    book = []; shadow = []; trades = []
    hist = {k: deque(maxlen=p["adWin"]) for k in (0, 1, 2)}
    cnt = {k: 0 for k in (0, 1, 2)}

    def conv(i, d, evz, reversal):
        wA = (p["wEff"] if effOk[i] else 0) + (p["wFlow"] if volOk[i] else 0) + p["wHtf"] + p["wLoc"] + p["wLiq"]
        pts = 0.0
        if effOk[i]:
            pts += p["wEff"] * min(max(evz / p["zWhale"], 0), 1)
        if volOk[i]:
            pts += p["wFlow"] * min(max(d * ndf[i] / p["flowFull"], 0), 1)
        pts += p["wHtf"] * min(max(d * sHtf[i], 0), 1)
        below = c[i] < rv[i] if not np.isnan(rv[i]) else False
        loc = (below if d > 0 else not below) if reversal else ((not below) if d > 0 else below)
        pts += p["wLoc"] * loc
        pts += p["wLiq"] * (((i - lastBull) if d > 0 else (i - lastBear)) <= p["liqCtx"])
        return 100 * pts / wA if wA > 0 else 0

    def filters_ok(i, d, k):
        gated = p["htfGate"] == "All setups" or (p["htfGate"] == "Continuation setups only" and k == 2)
        return not gated or d * sHtf[i] > 0

    def adaptive_ok(k):
        if not p["adaptive"] or cnt[k] < p["adMin"]:
            return True
        return sum(hist[k]) > 0

    def sig_sink(t, won, r):
        trades.append((t[4], t[3], t[5][0], won, r, t[5][1]))

    def shadow_sink(t, won, r):
        hist[t[5]].append(r); cnt[t[5]] += 1

    for i in range(n):
        a = atr[i]
        if not np.isnan(ph[i]):
            bsl.append((ph[i], i - p["liqRight"])); bsl = bsl[-p["liqMax"]:]
        if not np.isnan(pl[i]):
            ssl.append((pl[i], i - p["liqRight"])); ssl = ssl[-p["liqMax"]:]
        sweptB = sweptS = None; keep = []
        for lvl, b in bsl:
            if h[i] > lvl or i - b > p["liqAge"]:
                if h[i] > lvl and c[i] < lvl:
                    sweptB = lvl if sweptB is None else max(sweptB, lvl)
            else:
                keep.append((lvl, b))
        bsl = keep; keep = []
        for lvl, b in ssl:
            if l[i] < lvl or i - b > p["liqAge"]:
                if l[i] < lvl and c[i] > lvl:
                    sweptS = lvl if sweptS is None else min(sweptS, lvl)
            else:
                keep.append((lvl, b))
        ssl = keep
        okA = not np.isnan(a) and a > 0
        rawBull = sweptS is not None and clv[i] >= 0
        rawBear = sweptB is not None and clv[i] <= 0
        if rawBull: lastBull = i
        if rawBear: lastBear = i
        spread = rng[i] / a if okA else 0
        absorbing = volOk[i] and vz[i] >= p["absZ"] and spread <= p["absSpread"] and okA
        absBull = p["useAbs"] and absorbing and l[i] <= llPrev[i] + 0.25 * a and clv[i] >= 0
        absBear = p["useAbs"] and absorbing and h[i] >= hhPrev[i] - 0.25 * a and clv[i] <= 0

        retL = retS = None
        newL = newS = False
        if i >= 2 and not np.isnan(atr[i - 1]):
            big = rng[i-1] >= p["dispATR"] * atr[i-1] and body[i-1] >= p["dispBody"] * rng[i-1]
            newL = p["useFvg"] and big and c[i-1] > o[i-1] and l[i] > h[i-2] and (l[i] - h[i-2]) >= p["fvgMinATR"] * atr[i-1]
            newS = p["useFvg"] and big and c[i-1] < o[i-1] and h[i] < l[i-2] and (l[i-2] - h[i]) >= p["fvgMinATR"] * atr[i-1]
        if fL is not None:
            if c[i] < fL["bot"] or i - fL["bar"] > p["fvgAge"]: fL = None
            else:
                if l[i] <= fL["top"]: fL["hit"] = True
                if fL["hit"] and c[i] > fL["top"] and c[i] > o[i]: retL = fL["vz"]; fL = None
        if fS is not None:
            if c[i] > fS["top"] or i - fS["bar"] > p["fvgAge"]: fS = None
            else:
                if h[i] >= fS["bot"]: fS["hit"] = True
                if fS["hit"] and c[i] < fS["bot"] and c[i] < o[i]: retS = fS["vz"]; fS = None
        if newL: fL = dict(top=l[i], bot=h[i-2], bar=i, vz=vz[i-1], hit=False)
        if newS: fS = dict(top=l[i-2], bot=h[i], bar=i, vz=vz[i-1], hit=False)

        tL = tS = None
        if pL is not None:
            if c[i] > pL["trig"]: tL = (pL["type"], pL["vz"], pL["inv"]); pL = None
            elif c[i] < pL["inv"] or i - pL["bar"] >= p["confirmN"]: pL = None
        if pS is not None:
            if c[i] < pS["trig"]: tS = (pS["type"], pS["vz"], pS["inv"]); pS = None
            elif c[i] > pS["inv"] or i - pS["bar"] >= p["confirmN"]: pS = None
        eL = 0 if (p["useSweep"] and rawBull) else 1 if absBull else -1
        eS = 0 if (p["useSweep"] and rawBear) else 1 if absBear else -1
        if eL >= 0:
            if p["confirmN"] == 0:
                if tL is None: tL = (eL, vz[i], l[i])
            else: pL = dict(type=eL, trig=h[i], inv=l[i], bar=i, vz=vz[i])
        if eS >= 0:
            if p["confirmN"] == 0:
                if tS is None: tS = (eS, vz[i], h[i])
            else: pS = dict(type=eS, trig=l[i], inv=h[i], bar=i, vz=vz[i])
        if tL is None and retL is not None: tL = (2, retL, None)
        if tS is None and retS is not None: tS = (2, retS, None)

        ok = i >= p["warmup"] and okA
        cL = conv(i, 1, tL[1], tL[0] != 2) if tL else 0
        cS = conv(i, -1, tS[1], tS[0] != 2) if tS else 0
        qL = ok and tL is not None and cL >= p["minConv"] and filters_ok(i, 1, tL[0])
        qS = ok and tS is not None and cS >= p["minConv"] and filters_ok(i, -1, tS[0])

        book = resolve(i, book, o, h, l, c, p["horizon"], sig_sink)
        shadow = resolve(i, shadow, o, h, l, c, p["horizon"], shadow_sink)
        risk = p["stopATR"] * a if okA else 0
        # Shadow book: every qualified candidate, used only by the adaptive gate.
        if qL and not qS:
            shadow.append((c[i], c[i] - risk, c[i] + p["tgtR"] * risk, 1, i, tL[0]))
        if qS and not qL:
            shadow.append((c[i], c[i] + risk, c[i] - p["tgtR"] * risk, -1, i, tS[0]))

        candL = qL and adaptive_ok(tL[0])
        candS = qS and adaptive_ok(tS[0])
        cooled = i - lastSig > p["cooldown"]
        longSig = candL and not candS and cooled
        shortSig = candS and not candL and cooled
        if longSig or shortSig:
            lastSig = i
            d = 1 if longSig else -1
            k, cv = (tL[0], cL) if longSig else (tS[0], cS)
            book.append((c[i], c[i] - d * risk, c[i] + d * p["tgtR"] * risk, d, i, (k, cv)))
    return trades


# ---------------------------------------------------------------- reporting
def summarize(trades, base, lo, hi):
    """Pooled stats for trades whose entry bar is in [lo, hi)."""
    t = [x for x in trades if lo <= x[0] < hi]
    b = [x for x in base if lo <= x[0] < hi]
    res = {"n": len(t)}
    if not t:
        return res
    res["win"] = np.mean([x[3] for x in t])
    res["R"] = np.mean([x[4] for x in t])
    # Baseline matched to the signals' side mix.
    bw = {d: np.mean([x[2] for x in b if x[1] == d]) for d in (1, -1)}
    bR = {d: np.mean([x[3] for x in b if x[1] == d]) for d in (1, -1)}
    res["bwin"] = np.mean([bw[x[1]] for x in t])
    res["bR"] = np.mean([bR[x[1]] for x in t])
    p0 = res["bwin"]
    res["z"] = (res["win"] - p0) / math.sqrt(p0 * (1 - p0) / len(t)) if 0 < p0 < 1 else float("nan")
    return res


if __name__ == "__main__":
    from datasets import load_all
    data = load_all()
    print(f"{'dataset':<22}{'bars':>7} | {'IS n':>5}{'win':>7}{'rand':>7}{'R':>7}{'randR':>7} | "
          f"{'OOS n':>5}{'win':>7}{'rand':>7}{'R':>7}{'randR':>7}{'z':>6}")
    for name, (df, intraday, htf) in data.items():
        tr = run(df, intraday, htf); bs = baseline(df, P)
        cut = int(len(df) * 0.6)
        a = summarize(tr, bs, 0, cut); b = summarize(tr, bs, cut, len(df))
        f = lambda s: (f"{s['n']:>5}{100*s['win']:>6.1f}%{100*s['bwin']:>6.1f}%{s['R']:>+7.2f}{s['bR']:>+7.2f}"
                       if s["n"] else f"{0:>5}{'—':>7}{'—':>7}{'—':>7}{'—':>7}")
        print(f"{name:<22}{len(df):>7} | {f(a)} | {f(b)}{b.get('z', float('nan')):>+6.1f}")
