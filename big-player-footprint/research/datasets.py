"""Real OHLCV test bed for the reference port, pulled from public GitHub repos
(and the `backtesting` PyPI package) and cached under ./data.

Covers every market type the indicator is meant for: US equities daily and
hourly, FX hourly with and without a volume feed, gold (no volume), crypto
daily, and crypto 5-minute and 1-minute bars.
"""
import io, json, os, zipfile, urllib.request
import pandas as pd

RAW = "https://raw.githubusercontent.com/"
LEAN = RAW + "QuantConnect/Lean/master/Data/"
BT = RAW + "mementum/backtrader/master/datas/"
FT = RAW + "freqtrade/freqtrade/develop/tests/testdata/"
HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "data")


def _get(url):
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, url.replace(RAW, "").replace("/", "_"))
    if not os.path.exists(path):
        with urllib.request.urlopen(url, timeout=60) as r, open(path, "wb") as f:
            f.write(r.read())
    return path


def _lean(url, scale=1.0, quote=False):
    with zipfile.ZipFile(_get(url)) as z:
        raw = z.read(z.namelist()[0]).decode()
    df = pd.read_csv(io.StringIO(raw), header=None)
    df.index = pd.to_datetime(df[0], format="%Y%m%d %H:%M")
    cols = [1, 2, 3, 4] if quote else [1, 2, 3, 4, 5]
    out = df[cols].astype(float)
    out.columns = ["Open", "High", "Low", "Close", "Volume"][:len(cols)]
    out[["Open", "High", "Low", "Close"]] /= scale
    if quote:
        out["Volume"] = 0.0          # OANDA quote bars carry no volume
    return out


def _bt(name):
    df = pd.read_csv(_get(BT + name), parse_dates=["Date"], index_col="Date")
    return df[["Open", "High", "Low", "Close", "Volume"]].astype(float)


def _ft_feather(name):
    df = pd.read_feather(_get(FT + name))
    df.index = pd.to_datetime(df["date"]).dt.tz_localize(None)
    df = df[["open", "high", "low", "close", "volume"]].astype(float)
    df.columns = ["Open", "High", "Low", "Close", "Volume"]
    return df


def _ft_json(name):
    rows = json.load(open(_get(FT + name)))
    df = pd.DataFrame(rows, columns=["t", "Open", "High", "Low", "Close", "Volume"])
    df.index = pd.to_datetime(df.pop("t"), unit="ms")
    return df.astype(float)


# name -> (loader, intraday?, HTF grouping: int = N chart bars, str = clock rule)
DATASETS = {
    "SPY 1D":            (lambda: _lean(LEAN + "equity/usa/daily/spy.zip", 1e4), False, 4),
    "AAPL 1D":           (lambda: _lean(LEAN + "equity/usa/daily/aapl.zip", 1e4), False, 4),
    "IBM 1D":            (lambda: _lean(LEAN + "equity/usa/daily/ibm.zip", 1e4), False, 4),
    "NVDA 1D":           (lambda: _bt("nvda-1999-2014.txt"), False, 4),
    "ORCL 1D":           (lambda: _bt("orcl-1995-2014.txt"), False, 4),
    "YHOO 1D":           (lambda: _bt("yhoo-1996-2014.txt"), False, 4),
    "SPY 1h":            (lambda: _lean(LEAN + "equity/usa/hour/spy.zip", 1e4), True, "4h"),
    "AAPL 1h":           (lambda: _lean(LEAN + "equity/usa/hour/aapl.zip", 1e4), True, "4h"),
    "EURUSD 1h (no vol)": (lambda: _lean(LEAN + "forex/oanda/hour/eurusd.zip", quote=True), True, "4h"),
    "XAUUSD 1D (no vol)": (lambda: _lean(LEAN + "cfd/oanda/daily/xauusd.zip", quote=True), False, 4),
    "BTCUSD 1D":         (lambda: _lean(LEAN + "crypto/coinbase/daily/btcusd_trade.zip"), False, 4),
    "ETHBTC 5m":         (lambda: _ft_feather("UNITTEST_BTC-5m.feather"), True, "20min"),
    "ALTBTC 1m":         (lambda: _ft_json("UNITTEST_BTC-1m.json"), True, "4min"),
}


def extra():
    """EURUSD 1h with tick volume and GOOG 1D, from the backtesting package."""
    from backtesting import test
    return {"EURUSD 1h (tick vol)": (lambda: test.EURUSD.copy(), True, "4h"),
            "GOOG 1D (bt)": (lambda: test.GOOG.copy(), False, 4)}


def load_all(include_extra=True):
    sets = dict(DATASETS)
    if include_extra:
        try:
            sets.update(extra())
        except ImportError:
            pass
    out = {}
    for name, (fn, intraday, htf) in sets.items():
        df = fn()
        df = df[(df["High"] >= df["Low"]) & (df["Close"] > 0)]
        out[name] = (df[~df.index.duplicated()].sort_index(), intraday, htf)
    return out
