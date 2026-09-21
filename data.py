"""
Dataset construction for the SPY weekly iron condor backtest.

Three stages. Stage 1 needs live Robinhood MCP access and is therefore
documented rather than executed here; stages 2 and 3 are pure functions that
rebuild everything in data/ from the raw JSON those calls return.

  1. FETCH   (needs MCP)   see fetch_plan() for the exact call sequence
  2. PARSE   parse_equity_historicals() / parse_option_historicals()
  3. PLAN    build_week_plan() picks the 4 strikes per week by target delta

Running this file with a directory of raw Robinhood JSON responses rebuilds
data/spy_daily.csv and data/opt_bars.csv:

    python3 data.py --raw-dir /path/to/raw-json
"""
import argparse, csv, glob, json, math, os, datetime as dt
from collections import defaultdict

CHAIN_ID = "c277b118-58d9-4060-8dc5-a3b5898955cb"   # SPY; reconfirm per session
DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

# --------------------------------------------------------------------------
# 1. FETCH — the MCP call sequence that produced data/
# --------------------------------------------------------------------------
def fetch_plan():
    """The exact sequence used. Reproduce with the Robinhood MCP server."""
    return """
    a) get_equity_historicals(symbols=['SPY'], interval='day',
           start_time=<52wk + 20 session warm-up>)
       -> data/spy_daily.csv via parse_equity_historicals()

    b) build_week_plan() on that series -> the 4 strikes for each of 52 weeks

    c) get_option_instruments(chain_id=CHAIN_ID, state='expired', type=<c|p>,
           expiration_dates=<comma-separated>, strike_price='<K>.0000')
       Group by (type, strike) and batch the expirations: 134 calls cover all
       208 legs. -> data/ids_raw.txt  ("<type> <strike> <expiry> <uuid>")

    d) get_option_historicals(instrument_ids=[...8 ids...], interval='hour',
           start_time=<entry Monday>, end_time=<expiry Friday of the 2nd week>)
       Two weeks (8 legs) per call = 26 calls. -> data/opt_bars.csv

    Note: genuine SPY *hourly* equity history only reaches back ~9 months;
    earlier bars come back with interpolated=true and must be dropped. Option
    hourly history reaches back at least 52 weeks. Both parsers filter on it.
    """

# --------------------------------------------------------------------------
# 2. PARSE
# --------------------------------------------------------------------------
def _bars(blob):
    for res in blob.get("data", {}).get("results", []):
        for b in res.get("bars", []):
            if b.get("interpolated") is True:       # synthesized gap-fill
                continue
            yield res, b

def parse_equity_historicals(paths, out=None):
    """Robinhood equity historicals JSON -> date,open,high,low,close CSV."""
    rows = {}
    for p in paths:
        for _, b in _bars(json.load(open(p))):
            d = b["begins_at"].split("T")[0]
            rows[d] = (b["open_price"], b["high_price"], b["low_price"], b["close_price"])
    out = out or os.path.join(DATA, "spy_daily.csv")
    with open(out, "w", newline="") as f:
        w = csv.writer(f); w.writerow(["date", "open", "high", "low", "close"])
        for d in sorted(rows): w.writerow([d, *rows[d]])
    return len(rows)

def parse_option_historicals(paths, out=None):
    """Robinhood option historicals JSON -> instrument,occ,ts,o,h,l,c CSV."""
    seen = set()
    for p in paths:
        for res, b in _bars(json.load(open(p))):
            seen.add((res["instrument_id"], res.get("occ_symbol", ""), b["begins_at"],
                      b["open_price"], b["high_price"], b["low_price"], b["close_price"]))
    out = out or os.path.join(DATA, "opt_bars.csv")
    with open(out, "w", newline="") as f:
        csv.writer(f).writerows(sorted(seen))
    return len(seen)

# --------------------------------------------------------------------------
# 3. PLAN — strike selection
# --------------------------------------------------------------------------
def ncdf(x): return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

def ninv(p):
    """Acklam's inverse normal CDF."""
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    lo, hi = 0.02425, 1 - 0.02425
    if p < lo:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p > hi:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    q = p - 0.5; r = q * q
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)

def strike_for_delta(S, sig, T, target, kind):
    """Invert Black-Scholes delta for a strike, r=0. Rounds to SPY's $1 grid."""
    d1 = ninv(target) if kind == "c" else ninv(1.0 - target)
    return round(S * math.exp(0.5 * sig * sig * T - d1 * sig * math.sqrt(T)))

def realised_vol(closes, i, n=20):
    """Annualised close-to-close vol over the n sessions ending at index i."""
    if i < n: return None
    r = [math.log(closes[j] / closes[j-1]) for j in range(i - n + 1, i + 1)]
    m = sum(r) / len(r)
    return math.sqrt(sum((x - m) ** 2 for x in r) / (len(r) - 1) * 252)

# IV proxy: trailing RV scaled by the IV/RV ratio seen on the live 2026-09-21
# chain, separately per wing so the put skew survives. SPY RV20 was 9.16% that
# day against ~10.96% IV at the D0.21 call and ~13.50% at the D0.16 put.
K_CALL, K_PUT = 0.1096 / 0.0916, 0.1350 / 0.0916

def build_week_plan(daily_csv=None, delta_call=0.21, delta_put=0.16, wing=6, weeks=52):
    """-> [{entry, expiry, S0, rv, strikes:[lp,sp,sc,lc]}] newest `weeks` cycles."""
    rows = []
    with open(daily_csv or os.path.join(DATA, "spy_daily.csv")) as f:
        for r in csv.DictReader(f):
            rows.append((dt.date.fromisoformat(r["date"]), float(r["open"]), float(r["close"])))
    rows.sort()
    closes = [r[2] for r in rows]
    byweek = defaultdict(list)
    for i, r in enumerate(rows): byweek[r[0].isocalendar()[:2]].append(i)
    out = []
    for _, idx in sorted(byweek.items()):
        e, x = idx[0], idx[-1]
        if rows[e][0].weekday() > 2 or len(idx) < 3: continue   # partial stub week
        sig = realised_vol(closes, e - 1)
        if sig is None: continue
        S0 = rows[e][1]                                         # Monday's open
        T = (rows[x][0] - rows[e][0]).days / 365.0
        kc = strike_for_delta(S0, K_CALL * sig, T, delta_call, "c")
        kp = strike_for_delta(S0, K_PUT * sig, T, delta_put, "p")
        out.append(dict(entry=str(rows[e][0]), expiry=str(rows[x][0]), S0=S0, rv=sig,
                        strikes=[kp - wing, kp, kc, kc + wing]))
    return out[-weeks:]

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raw-dir", help="directory of raw Robinhood JSON responses")
    ap.add_argument("--show-fetch-plan", action="store_true")
    a = ap.parse_args()
    if a.show_fetch_plan:
        print(fetch_plan())
    elif a.raw_dir:
        eq = sorted(glob.glob(os.path.join(a.raw_dir, "*equity_historicals*")))
        op = sorted(glob.glob(os.path.join(a.raw_dir, "*option_historicals*")))
        if eq: print(f"spy_daily.csv : {parse_equity_historicals(eq)} sessions")
        if op: print(f"opt_bars.csv  : {parse_option_historicals(op)} bars")
    else:
        plan = build_week_plan()
        print(f"{len(plan)} weeks  {plan[0]['entry']} .. {plan[-1]['expiry']}")
        print(f"{'entry':<12}{'expiry':<12}{'S0':>9}{'RV20':>7}   lp/sp/sc/lc")
        for p in plan[:3] + plan[-3:]:
            print(f"{p['entry']:<12}{p['expiry']:<12}{p['S0']:>9.2f}{p['rv']*100:>6.1f}%"
                  f"   {'/'.join(str(s) for s in p['strikes'])}")
