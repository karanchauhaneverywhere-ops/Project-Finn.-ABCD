"""Compare indicator configurations across every dataset in datasets.py.

Each dataset is split by time: the first 60% ("IS") is where features were
chosen, the last 40% ("OOS") is the check. Edges are measured against the
random-entry baseline matched to each configuration's long/short mix:

    winΔpp  signal win rate − random win rate, pooled over all signals
    RΔ      signal avg R − random avg R, pooled over all signals
    eqRΔ    the same, averaged per dataset (datasets with ≥ 5 signals)
    pos     datasets where RΔ > 0

    python3 experiments.py                 # all configurations
    python3 experiments.py v1 v2           # a subset
"""
import sys
from multiprocessing import Pool
import numpy as np
import reference_port as rp
from datasets import load_all

DATA = load_all()

CONFIGS = {
    "v1 defaults": dict(adaptive=False, rangeProxy=False),
    "v2 defaults": {},
    "v2 no gate": dict(adaptive=False),
    "v2 no range": dict(rangeProxy=False),
    "v2 htf cont": dict(htfGate="Continuation setups only"),
    "v2 htf all": dict(htfGate="All setups"),
    "v2 conv 70": dict(minConv=70),
    "v2 confirm 0": dict(confirmN=0),
}


def _base(name):
    return name, rp.baseline(DATA[name][0], rp.P)


def _job(args):
    cfg, name = args
    df, intraday, htf = DATA[name]
    return cfg, name, rp.run(df, intraday, htf, dict(rp.P, **CONFIGS[cfg]))


def agg(results, bases, lo_frac, hi_frac):
    per, pooled = [], []
    for name, tr in results.items():
        n = len(DATA[name][0])
        s = rp.summarize(tr, bases[name], int(n * lo_frac), int(n * hi_frac))
        if s["n"]:
            per.append(s)
            pooled.append((s["n"], s["win"] - s["bwin"], s["R"] - s["bR"]))
    N = sum(x[0] for x in pooled)
    if not N:
        return None
    eq = [s["R"] - s["bR"] for s in per if s["n"] >= 5]
    return dict(N=N, win=sum(x[0] * x[1] for x in pooled) / N, R=sum(x[0] * x[2] for x in pooled) / N,
                eq=float(np.mean(eq)) if eq else float("nan"), pos=f"{sum(e > 0 for e in eq)}/{len(eq)}")


if __name__ == "__main__":
    sel = sys.argv[1:] or list(CONFIGS)
    with Pool() as pool:
        bases = dict(pool.map(_base, list(DATA)))
        out = {}
        for cfg, name, tr in pool.imap_unordered(_job, [(c, nm) for c in sel for nm in DATA]):
            out.setdefault(cfg, {})[name] = tr
    f = lambda s: f"{s['N']:>5}{100*s['win']:>+8.1f}{s['R']:>+7.3f}{s['eq']:>+7.3f}{s['pos']:>6}" if s else "  none"
    print(f"{'config':<14}| {'IS N':>5}{'winΔpp':>8}{'RΔ':>7}{'eqRΔ':>7}{'pos':>6} | {'OOS N':>5}{'winΔpp':>8}{'RΔ':>7}{'eqRΔ':>7}{'pos':>6}")
    for c in sel:
        print(f"{c:<14}| {f(agg(out[c], bases, 0, 0.6))} | {f(agg(out[c], bases, 0.6, 1.0))}")
