"""
SPY weekly iron condor — evaluate all 52 weeks on real option prices.

Entry  Monday 10:00 ET, at that hourly bar's OPEN.
Exit   Friday 15:00 ET at that bar's OPEN, or earlier on a stop / profit target.
Marks  the package is monitored on each hourly CLOSE, which models the
       alert-driven polling the strategy actually relies on (Robinhood has no
       broker-side stop for multi-leg spreads).

Importable: grid.py and sens.py use run() and stats() from here.

    python3 eval_all.py                 # spec config, per-week detail
    python3 eval_all.py --pt 0.30       # with a 30% profit target
"""
import argparse, csv, json, os, datetime as dt, statistics as st
from collections import defaultdict

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
FEES = 0.36          # per condor round trip, all four legs, Robinhood pass-throughs

BARS = defaultdict(dict)
for _r in csv.reader(open(os.path.join(DATA, "opt_bars.csv"))):
    _iid, _occ, _ts, _o, _h, _l, _c = _r
    BARS[_iid][_ts] = (float(_o), float(_h), float(_l), float(_c))

SPY_CLOSE = {r["date"]: float(r["close"])
             for r in csv.DictReader(open(os.path.join(DATA, "spy_daily.csv")))}

WEEKS = json.load(open(os.path.join(DATA, "weeks.json")))


def _session(iid, day):
    p = day.isoformat()
    return sorted((t, v) for t, v in BARS[iid].items() if t.startswith(p))


def timeline(w):
    """[(ts, date, [lp,sp,sc,lc] OHLC tuples)] hourly across the week."""
    e = dt.date.fromisoformat(w["entry"]); x = dt.date.fromisoformat(w["expiry"])
    days, d = [], e
    while d <= x:
        if any(_session(i, d) for i in w["ids"]): days.append(d)
        d += dt.timedelta(1)
    out = []
    for d in days:
        for t in sorted({t for i in w["ids"] for t, _ in _session(i, d)}):
            out.append((t, d, [BARS[i].get(t) for i in w["ids"]]))
    return out


def package(px, field=3):
    """Cost to close = (short put + short call) - (long put + long call)."""
    if any(v is None for v in px): return None
    lp, sp, sc, lc = px
    return (sp[field] + sc[field]) - (lp[field] + lc[field])


def settle(w):
    """Intrinsic cost to close at Friday settlement, from SPY's close."""
    S = SPY_CLOSE[w["expiry"]]
    kpl, kp, kc, kcl = w["strikes"]
    return min(kp - kpl, max(0.0, kp - S)) + min(kcl - kc, max(0.0, S - kc))


def run(pt=None, stop=2.0, min_credit=1.00, friday_close=True, slip=0.0, weeks=None):
    """One dict per candidate week. pt/stop are fractions/multiples of the credit."""
    out = []
    for w in (weeks if weeks is not None else WEEKS):
        tl = timeline(w)
        if not tl: continue
        cr = package(tl[0][2], field=0)          # entry fills at the 10:00 bar's open
        if cr is None: continue
        cr -= slip
        if cr < min_credit:
            out.append(dict(week=w["entry"], skipped=True, credit=cr, pnl=0.0)); continue
        width = w["strikes"][1] - w["strikes"][0]
        exitv, why = None, None
        for t, d, px in tl[1:]:
            v = package(px, field=3)
            if v is None: continue
            if pt is not None and v <= cr * (1 - pt): exitv, why = v, "profit_target"; break
            if stop is not None and v >= cr * stop: exitv, why = min(v, width), "stop"; break
        if exitv is None:
            if friday_close:
                exitv = package(tl[-1][2], field=0)   # last bar's open = 15:00 ET
                if exitv is None: exitv = settle(w)
                why = "friday_3pm"
            else:
                exitv, why = settle(w), "expiry"
        out.append(dict(week=w["entry"], expiry=w["expiry"], skipped=False, credit=cr,
                        exitv=exitv, pnl=(cr - exitv) * 100 - FEES, why=why,
                        width=width, strikes=w["strikes"], maxloss=(width - cr) * 100))
    return out


def stats(res):
    t = [r for r in res if not r["skipped"]]
    if not t: return None
    p = [r["pnl"] for r in t]
    eq = pk = dd = 0.0
    for v in p:
        eq += v; pk = max(pk, eq); dd = min(dd, eq - pk)
    n = len(p); m = st.mean(p); sd = st.stdev(p) if n > 1 else 0.0
    return dict(n=n, skipped=len(res) - n, total=sum(p), avg=m, sd=sd,
                win=sum(1 for v in p if v > 0) / n * 100, dd=dd, worst=min(p),
                t=(m / (sd / n ** 0.5) if sd > 0 else 0.0),
                avgcr=st.mean([r["credit"] for r in t]),
                avgrisk=st.mean([r["maxloss"] for r in t]))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pt", type=float, default=None, help="profit target, e.g. 0.30")
    ap.add_argument("--stop", type=float, default=2.0, help="stop as a multiple of credit")
    ap.add_argument("--min-credit", type=float, default=1.00)
    ap.add_argument("--expiry", action="store_true", help="hold to settlement, not Friday 3pm")
    ap.add_argument("--slip", type=float, default=0.0)
    a = ap.parse_args()

    res = run(pt=a.pt, stop=a.stop, min_credit=a.min_credit,
              friday_close=not a.expiry, slip=a.slip)
    s = stats(res)
    print(f"PT {'hold' if a.pt is None else f'{a.pt:.0%}'} | "
          f"stop {'none' if a.stop is None else f'{a.stop}x'} | "
          f"min credit ${a.min_credit:.2f} | "
          f"{'settlement' if a.expiry else 'Friday 3pm'} | slip ${a.slip:.2f}")
    print(f"\n{'entry':<12}{'expiry':<12}{'cr':>6}{'exit':>7}{'P&L':>9}  why")
    print("-" * 60)
    for r in res:
        if r["skipped"]:
            print(f"{r['week']:<12}{'-':<12}{r['credit']:>6.2f}{'':>7}{'SKIP':>9}  below credit floor")
        else:
            print(f"{r['week']:<12}{r['expiry']:<12}{r['credit']:>6.2f}"
                  f"{r['exitv']:>7.2f}{r['pnl']:>9.0f}  {r['why']}")
    print("-" * 60)
    print(f"weeks traded   {s['n']}   (skipped {s['skipped']})")
    print(f"win rate       {s['win']:.1f}%")
    print(f"total P&L      ${s['total']:,.0f}")
    print(f"avg / week     ${s['avg']:,.0f}   sd ${s['sd']:,.0f}   t = {s['t']:.2f}")
    print(f"worst week     ${s['worst']:,.0f}")
    print(f"max drawdown   ${s['dd']:,.0f}")
    print(f"avg credit     ${s['avgcr']*100:,.0f}   avg max risk ${s['avgrisk']:,.0f}")
