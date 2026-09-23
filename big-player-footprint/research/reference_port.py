"""Bar-by-bar Python port of indicators/Big_Player_Footprint.pine.

Used to sanity-check the signal logic and the scoreboard outside TradingView on
real OHLCV bundled with the `backtesting` package (GOOG daily 2004-2013,
EURUSD 1h 2017-2018). Mirrors the Pine defaults.

Known differences from TradingView: the higher timeframe is approximated by
grouping chart bars (4 bars on GOOG, 4h buckets on EURUSD), pivots use strict
inequalities on both sides, and the delta source is always the bar
approximation.

    pip install backtesting pandas numpy
    python3 reference_port.py
"""
import math
import numpy as np
import pandas as pd
from backtesting import test

P = dict(volLen=50, todLen=20, todMin=10, zWhale=2.0, flowLen=20, flowFull=0.20,
         vwLen=50, atrLen=14, liqLeft=10, liqRight=3, liqMax=10, liqAge=300,
         useSweep=True, useAbs=True, useFvg=True, absZ=1.5, absSpread=0.9, locLen=20,
         dispATR=1.5, dispBody=0.6, fvgMinATR=0.1, fvgAge=30, confirmN=3,
         wEff=30, wFlow=20, wHtf=20, wLoc=15, wLiq=15, minConv=60, liqCtx=20,
         htfMult=4, htfLen=50, htfFull=0.5, cooldown=5,
         stopATR=1.5, tgtR=1.5, horizon=30, warmup=100)


def rma(x, n):
    out = np.full(len(x), np.nan); s = None; cnt = 0; acc = 0.0
    for i, v in enumerate(x):
        if np.isnan(v):
            continue
        if s is None:
            acc += v; cnt += 1
            if cnt == n:
                s = acc / n; out[i] = s
        else:
            s = s + (v - s) / n; out[i] = s
    return out


def atr_of(h, l, c, n):
    pc = np.r_[np.nan, c[:-1]]
    tr = np.where(np.isnan(pc), h - l, np.maximum(h - l, np.maximum(abs(h - pc), abs(l - pc))))
    return rma(tr, n)


def ema(x, n):
    out = np.full(len(x), np.nan); a = 2 / (n + 1); s = None; buf = []
    for i, v in enumerate(x):
        if s is None:
            buf.append(v)
            if len(buf) == n:
                s = np.mean(buf); out[i] = s
        else:
            s = a * v + (1 - a) * s; out[i] = s
    return out


def pivots(x, L, R, high=True):
    """value confirmed at bar i (pivot at i-R), else nan"""
    out = np.full(len(x), np.nan)
    for i in range(L + R, len(x)):
        c = i - R; v = x[c]
        left = x[c - L:c]; right = x[c + 1:i + 1]
        if high and v > left.max() and v > right.max():
            out[i] = v
        if not high and v < left.min() and v < right.min():
            out[i] = v
    return out


def htf_slope(df, rule_or_n, p):
    """last CLOSED htf bar's EMA slope (ATR per 5 htf bars), mapped to chart bars"""
    if isinstance(rule_or_n, int):
        g = np.arange(len(df)) // rule_or_n
    else:
        g = df.index.floor(rule_or_n)
    grp = df.groupby(g)
    h = grp['High'].max().values; l = grp['Low'].min().values; c = grp['Close'].last().values
    e = ema(c, p['htfLen']); a = atr_of(h, l, c, 14)
    sl = np.where(a > 0, (e - np.r_[np.full(5, np.nan), e[:-5]]) / a, 0.0)
    keys = pd.Index(pd.unique(g))
    pos = keys.get_indexer(g)            # which htf bar each chart bar belongs to
    prev = np.where(pos >= 1, sl[np.maximum(pos - 1, 0)], np.nan)  # previous CLOSED htf bar
    return prev


def run(df, intraday, htf_rule, p=P):
    o, h, l, c = (df[k].values.astype(float) for k in ('Open', 'High', 'Low', 'Close'))
    v = df['Volume'].values.astype(float)
    n = len(df)
    atr = atr_of(h, l, c, p['atrLen'])
    rng = h - l; body = abs(c - o)
    clv = np.where(rng > 0, ((c - l) - (h - c)) / np.where(rng > 0, rng, 1), 0.0)
    lv = np.log(v + 1)
    s_lv = pd.Series(lv)
    lvM = s_lv.rolling(p['volLen']).mean().values
    lvS = s_lv.rolling(p['volLen']).std(ddof=0).values
    zRoll = np.nan_to_num((lv - np.r_[np.nan, lvM[:-1]]) / np.maximum(np.nan_to_num(np.r_[np.nan, lvS[:-1]]), 0.15))
    # time-of-day
    vz = zRoll.copy(); todA = 2 / (p['todLen'] + 1)
    if intraday:
        mean = {}; var = {}; cnt = {}
        for i in range(n):
            slot = df.index[i].hour * 60 + df.index[i].minute
            k = cnt.get(slot, 0)
            if k >= p['todMin']:
                vz[i] = (lv[i] - mean[slot]) / max(math.sqrt(var[slot]), 0.15)
            if k == 0:
                mean[slot] = lv[i]; var[slot] = 0.0
            else:
                d = lv[i] - mean[slot]; mean[slot] += todA * d
                var[slot] = (1 - todA) * (var[slot] + todA * d * d)
            cnt[slot] = k + 1
    delta = clv * v
    sd = pd.Series(delta).rolling(p['flowLen']).sum().values
    sv = pd.Series(v).rolling(p['flowLen']).sum().values
    ndf = np.where(np.nan_to_num(sv) > 0, np.nan_to_num(sd) / np.where(np.nan_to_num(sv) > 0, sv, 1), 0.0)
    hlc3 = (h + l + c) / 3
    rv = (pd.Series(hlc3 * v).rolling(p['vwLen']).sum() / pd.Series(v).rolling(p['vwLen']).sum()).values
    sHtf = np.clip(np.nan_to_num(htf_slope(df, htf_rule, p)) / p['htfFull'], -1, 1)
    ph = pivots(h, p['liqLeft'], p['liqRight'], True)
    pl = pivots(l, p['liqLeft'], p['liqRight'], False)
    llPrev = np.r_[np.nan, pd.Series(l).rolling(p['locLen']).min().values[:-1]]
    hhPrev = np.r_[np.nan, pd.Series(h).rolling(p['locLen']).max().values[:-1]]

    bsl = []; ssl = []   # (level, bar)
    lastBull = lastBear = -10**9
    fL = None; fS = None
    pL = None; pS = None
    lastSig = -10**9
    sig_open = []; base_open = []
    stats = {}; base = {1: [0, 0, 0.0], -1: [0, 0, 0.0]}
    signals = []
    wAvail = p['wEff'] + p['wFlow'] + p['wHtf'] + p['wLoc'] + p['wLiq']

    def conv(i, d, evz, reversal):
        pts = p['wEff'] * min(max(evz / p['zWhale'], 0), 1)
        pts += p['wFlow'] * min(max(d * ndf[i] / p['flowFull'], 0), 1)
        pts += p['wHtf'] * min(max(d * sHtf[i], 0), 1)
        below = c[i] < rv[i] if not np.isnan(rv[i]) else False
        loc = (below if d > 0 else not below) if reversal else ((not below) if d > 0 else below)
        pts += p['wLoc'] * loc
        liq = (i - lastBull if d > 0 else i - lastBear) <= p['liqCtx']
        pts += p['wLiq'] * liq
        return 100 * pts / wAvail

    def resolve(i, book, sink):
        keep = []
        for (e, s, t, d, b, k) in book:
            risk = abs(e - s); r = None; won = False
            if d > 0:
                if o[i] <= s: r = (o[i] - e) / risk
                elif l[i] <= s: r = -1.0
                elif h[i] >= t: r = (t - e) / risk; won = True
            else:
                if o[i] >= s: r = (e - o[i]) / risk
                elif h[i] >= s: r = -1.0
                elif l[i] <= t: r = (e - t) / risk; won = True
            if r is None and i - b >= p['horizon']:
                r = d * (c[i] - e) / risk
            if r is None:
                keep.append((e, s, t, d, b, k))
            else:
                sink(k, d, won, r)
        return keep

    def sig_sink(k, d, won, r):
        st = stats.setdefault((k, d), [0, 0, 0.0]); st[0] += 1; st[1] += won; st[2] += r

    def base_sink(k, d, won, r):
        st = base[d]; st[0] += 1; st[1] += won; st[2] += r

    for i in range(n):
        a = atr[i]
        if not np.isnan(ph[i]):
            bsl.append((ph[i], i - p['liqRight'])); bsl = bsl[-p['liqMax']:]
        if not np.isnan(pl[i]):
            ssl.append((pl[i], i - p['liqRight'])); ssl = ssl[-p['liqMax']:]
        sweptB = None; sweptS = None; nb = []
        for (lvl, b) in bsl:
            taken = h[i] > lvl; exp = i - b > p['liqAge']
            if taken or exp:
                if taken and c[i] < lvl: sweptB = lvl if sweptB is None else max(sweptB, lvl)
            else: nb.append((lvl, b))
        bsl = nb; ns = []
        for (lvl, b) in ssl:
            taken = l[i] < lvl; exp = i - b > p['liqAge']
            if taken or exp:
                if taken and c[i] > lvl: sweptS = lvl if sweptS is None else min(sweptS, lvl)
            else: ns.append((lvl, b))
        ssl = ns
        rawBull = sweptS is not None and clv[i] >= 0
        rawBear = sweptB is not None and clv[i] <= 0
        if rawBull: lastBull = i
        if rawBear: lastBear = i
        sweepBull = p['useSweep'] and rawBull; sweepBear = p['useSweep'] and rawBear
        spread = rng[i] / a if a > 0 else 0
        absorbing = vz[i] >= p['absZ'] and spread <= p['absSpread'] and not np.isnan(a)
        absBull = p['useAbs'] and absorbing and l[i] <= llPrev[i] + 0.25 * a and clv[i] >= 0
        absBear = p['useAbs'] and absorbing and h[i] >= hhPrev[i] - 0.25 * a and clv[i] <= 0
        # FVG
        retL = retS = False
        if i >= 2 and not np.isnan(atr[i - 1]):
            dB = rng[i-1] >= p['dispATR'] * atr[i-1] and c[i-1] > o[i-1] and body[i-1] >= p['dispBody'] * rng[i-1]
            dS = rng[i-1] >= p['dispATR'] * atr[i-1] and c[i-1] < o[i-1] and body[i-1] >= p['dispBody'] * rng[i-1]
            newL = p['useFvg'] and dB and l[i] > h[i-2] and (l[i] - h[i-2]) >= p['fvgMinATR'] * atr[i-1]
            newS = p['useFvg'] and dS and h[i] < l[i-2] and (l[i-2] - h[i]) >= p['fvgMinATR'] * atr[i-1]
        else:
            newL = newS = False
        if fL is not None:
            if c[i] < fL['bot'] or i - fL['bar'] > p['fvgAge']: fL = None
            else:
                if l[i] <= fL['top']: fL['hit'] = True
                if fL['hit'] and c[i] > fL['top'] and c[i] > o[i]: retL = fL['vz']; fL = None
        if fS is not None:
            if c[i] > fS['top'] or i - fS['bar'] > p['fvgAge']: fS = None
            else:
                if h[i] >= fS['bot']: fS['hit'] = True
                if fS['hit'] and c[i] < fS['bot'] and c[i] < o[i]: retS = fS['vz']; fS = None
        if newL: fL = dict(top=l[i], bot=h[i-2], bar=i, vz=vz[i-1], hit=False)
        if newS: fS = dict(top=l[i-2], bot=h[i], bar=i, vz=vz[i-1], hit=False)
        # confirmation
        tL = tS = None
        if pL is not None:
            if c[i] > pL['trig']: tL = (pL['type'], pL['vz']); pL = None
            elif c[i] < pL['inv'] or i - pL['bar'] >= p['confirmN']: pL = None
        if pS is not None:
            if c[i] < pS['trig']: tS = (pS['type'], pS['vz']); pS = None
            elif c[i] > pS['inv'] or i - pS['bar'] >= p['confirmN']: pS = None
        eL = 0 if sweepBull else 1 if absBull else -1
        eS = 0 if sweepBear else 1 if absBear else -1
        if eL >= 0:
            if p['confirmN'] == 0:
                if tL is None: tL = (eL, vz[i])
            else: pL = dict(type=eL, trig=h[i], inv=l[i], bar=i, vz=vz[i])
        if eS >= 0:
            if p['confirmN'] == 0:
                if tS is None: tS = (eS, vz[i])
            else: pS = dict(type=eS, trig=l[i], inv=h[i], bar=i, vz=vz[i])
        if tL is None and retL is not False: tL = (2, retL)
        if tS is None and retS is not False: tS = (2, retS)
        cL = conv(i, 1, tL[1], tL[0] != 2) if tL else 0
        cS = conv(i, -1, tS[1], tS[0] != 2) if tS else 0
        ok = i >= p['warmup'] and not np.isnan(a) and a > 0
        candL = ok and tL is not None and cL >= p['minConv']
        candS = ok and tS is not None and cS >= p['minConv']
        cooled = i - lastSig > p['cooldown']
        longSig = candL and not candS and cooled
        shortSig = candS and not candL and cooled
        if longSig or shortSig: lastSig = i
        # scoreboard
        sig_open = resolve(i, sig_open, sig_sink)
        base_open = resolve(i, base_open, base_sink)
        if ok:
            risk = p['stopATR'] * a
            if longSig or shortSig:
                d = 1 if longSig else -1; k = tL[0] if longSig else tS[0]
                sig_open.append((c[i], c[i] - d * risk, c[i] + d * p['tgtR'] * risk, d, i, k))
                signals.append((df.index[i], d, k, cL if longSig else cS))
            for d in (1, -1):
                base_open.append((c[i], c[i] - d * risk, c[i] + d * p['tgtR'] * risk, d, i, 0))
    return stats, base, signals


def report(name, stats, base):
    names = {0: 'A Sweep', 1: 'B Absorb', 2: 'C FVG'}
    print(f"\n=== {name} ===")
    print(f"{'setup':<10}{'side':>5}{'n':>6}{'win%':>8}{'avgR':>8}")
    tot = {1: [0, 0, 0.0], -1: [0, 0, 0.0]}
    for (k, d), (nn, w, r) in sorted(stats.items()):
        print(f"{names[k]:<10}{'L' if d > 0 else 'S':>5}{nn:>6}{100*w/nn:>8.1f}{r/nn:>8.2f}")
        tot[d][0] += nn; tot[d][1] += w; tot[d][2] += r
    for d in (1, -1):
        nn, w, r = tot[d]; bn, bw, br = base[d]
        p0 = bw / bn if bn else float('nan')
        wr = w / nn if nn else float('nan')
        z = (wr - p0) / math.sqrt(p0 * (1 - p0) / nn) if nn else float('nan')
        print(f"ALL {'L' if d > 0 else 'S'}: n={nn} win={100*wr:.1f}% avgR={r/nn if nn else float('nan'):+.3f} | "
              f"random n={bn} win={100*p0:.1f}% avgR={br/bn:+.3f} | z={z:+.2f}")


if __name__ == '__main__':
    goog = test.GOOG.copy(); eur = test.EURUSD.copy()
    variants = [('defaults', {})] + [(f'minConv={m}', {'minConv': m}) for m in (0, 40, 75)]
    for nm, ov in variants:
        p = dict(P, **ov)
        s, b, _ = run(goog, False, 4, p); report(f'GOOG 1D  [{nm}]', s, b)
        s, b, _ = run(eur, True, '4h', p); report(f'EURUSD 1h [{nm}]', s, b)
