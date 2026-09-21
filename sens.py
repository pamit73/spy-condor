"""
One-parameter-at-a-time sensitivity for the SPY weekly iron condor.

Each block moves a single knob with everything else held at the documented spec
(no profit target, 2.0x credit stop, $1.00 credit floor, Friday 15:00 ET close),
so the effects are readable in isolation rather than confounded in a grid.

    python3 sens.py
"""
from eval_all import run, stats, WEEKS
from collections import Counter
import statistics as st

SPEC = dict(pt=None, stop=2.0, min_credit=1.00, friday_close=True)
H = f"{'':<22}{'wks':>5}{'win%':>7}{'total$':>9}{'maxDD$':>9}{'t':>6}"


def line(label, **kw):
    s = stats(run(**{**SPEC, **kw}))
    print(f"{label:<22}{s['n']:>5}{s['win']:>6.1f}%{s['total']:>9,.0f}{s['dd']:>9,.0f}{s['t']:>6.2f}")


print("STOP LEVEL")
print(H); print("-" * 58)
for stop in [None, 1.5, 2.0, 2.5, 3.0]:
    line("none" if stop is None else f"{stop:.1f}x credit", stop=stop)

print("\nPROFIT TARGET")
print(H); print("-" * 58)
for pt in [None, 0.25, 0.30, 0.35, 0.50, 0.65, 0.75]:
    line("none (hold)" if pt is None else f"{pt:.0%}", pt=pt)

print("\nMINIMUM CREDIT FLOOR")
print(H); print("-" * 58)
for mc in [0.00, 0.75, 1.00, 1.25, 1.50, 1.75]:
    line(f"${mc:.2f}", min_credit=mc)

print("\nEXIT TIMING")
print(H); print("-" * 58)
for fri in [True, False]:
    line("Friday 3pm" if fri else "hold to settlement", friday_close=fri)

print("\n\nPROFIT TARGET x STOP  (the interaction that matters)")
print(f"{'PT':<10}" + "".join(f"{lab:>20}" for lab in ["no stop", "2.0x stop", "2.5x stop"]))
print(f"{'':<10}" + "".join(f"{'total$':>11}{'t':>9}" for _ in range(3)))
print("-" * 70)
for pt in [None, 0.25, 0.30, 0.35, 0.50, 0.65, 0.75]:
    row = f"{('hold' if pt is None else f'{pt:.0%}'):<10}"
    for stop in [None, 2.0, 2.5]:
        s = stats(run(**{**SPEC, "pt": pt, "stop": stop}))
        row += f"{s['total']:>11,.0f}{s['t']:>9.2f}"
    print(row)
print("\nRead the columns: a profit target alone and a stop alone are both weak.")
print("Paired, t rises to 2.7-4.6. Testing a 30% target without a stop active")
print("reproduces the spec's conclusion that it is the worst rule.")

print("\n\nSLIPPAGE (30% PT + 2.0x stop) — credit haircut per condor")
print(f"{'slippage':<12}{'wks':>5}{'total$':>9}{'avg$':>8}{'t':>7}")
print("-" * 41)
for sl in [0.00, 0.05, 0.10, 0.15, 0.20, 0.30]:
    s = stats(run(**{**SPEC, "pt": 0.30, "slip": sl}))
    print(f"${sl:.2f}{'':<7}{s['n']:>5}{s['total']:>9,.0f}{s['avg']:>8,.0f}{s['t']:>7.2f}")

print("\n\nEXIT-REASON MIX")
for pt in [None, 0.30]:
    res = [r for r in run(**{**SPEC, "pt": pt}) if not r["skipped"]]
    wins = [r["pnl"] for r in res if r["pnl"] > 0]
    loss = [r["pnl"] for r in res if r["pnl"] <= 0]
    print(f"  PT {'hold' if pt is None else f'{pt:.0%}':<5} {dict(Counter(r['why'] for r in res))}")
    print(f"           avg win ${st.mean(wins):,.0f}   avg loss ${st.mean(loss):,.0f}"
          f"   worst ${min(r['pnl'] for r in res):,.0f}")

print("\n\nSUB-WINDOW RECONCILIATION")
w26 = [w for w in WEEKS if w["entry"] >= "2026-01-01"]
w25 = [w for w in WEEKS if w["entry"] < "2026-01-01"]
print(f"{'window':<30}{'wks':>5}{'win%':>7}{'total$':>9}{'worst$':>9}")
print("-" * 60)
for name, ws in [("Jan-Sep 2026", w26), ("Sep-Dec 2025", w25), ("full 52 weeks", None)]:
    s = stats(run(**SPEC, weeks=ws))
    print(f"{name:<30}{s['n']:>5}{s['win']:>6.1f}%{s['total']:>9,.0f}{s['worst']:>9,.0f}")
print("\nThe strategy spec reports 36 weeks, 30/36 wins (83%), +$2,677, worst -$370")
print("over the Jan-Sep 2026 window. The gap is most likely strike selection:")
print("strikes here are solved from a Black-Scholes proxy, not live historical")
print("deltas, and sit closer to the money — average credit is 31% of the $6")
print("width against 17% on the actual 2026-09-25 trade.")
