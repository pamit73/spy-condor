# SPY weekly iron condor — 52 weeks on real option prices

Backtest of the documented SPY strategy (Δ0.16 put / Δ0.21 call, $6 wings, Monday
10:00 ET entry, Friday 15:00 ET close, $1.00 credit floor) across **52 weekly
cycles**, 2025-09-22 → 2026-09-18.

**Prices are real.** 208 expired SPY contracts pulled from Robinhood at hourly
granularity — 8,568 bars — not modelled. Entry is the 10:00 ET bar's open, exits
are actual marks. This is the key difference from the QQQ study, where no chain
history existed and credits had to be modelled.

Scripts: `eval_all.py` (engine), `sens.py` (one knob at a time), `grid.py` (full grid).

---

## Headline: yes, there is a winning formula — and it is not the current spec

| Config | Total | Avg/wk | Max DD | t | Return/DD |
|---|---|---|---|---|---|
| **Spec as written** (hold, 2.0× stop) | $1,993 | $49 | −$1,405 | 1.64 | 1.4 |
| hold, 2.5× stop | $2,086 | $51 | −$1,298 | 1.56 | 1.6 |
| **30% PT + 2.0× stop** | **$2,342** | $57 | **−$215** | **4.55** | **10.9** |
| 35% PT + 2.5× stop | $2,270 | $55 | −$450 | 2.81 | 5.0 |
| 75% PT + 2.5× stop | **$3,201** | $78 | −$610 | 3.07 | 5.2 |

41 of 52 weeks traded (11 skipped on the $1.00 credit floor). Average credit $187,
average max risk $413.

---

## The spec's "no take-profit" rule is the single biggest thing costing money

The spec states: *"No take-profit order. (A 30% take-profit was the worst-performing
rule tested; even 50–65% take-profits underperformed holding.)"*

On 52 weeks of real prices, **every** profit target beats holding — but only when
paired with a stop. That interaction is almost certainly why the earlier 36-week
test reached the opposite conclusion.

| PT | no stop | | 2.0× stop | | 2.5× stop | |
|---|---|---|---|---|---|---|
| | total | t | total | t | total | t |
| hold | $1,685 | 1.15 | $1,993 | 1.64 | $2,086 | 1.56 |
| 25% | $1,411 | 1.57 | $2,036 | **4.07** | $1,822 | 2.67 |
| **30%** | $1,717 | 1.89 | **$2,342** | **4.55** | $2,128 | 3.06 |
| 35% | $1,723 | 1.63 | $2,567 | 4.16 | $2,270 | 2.81 |
| 50% | $1,914 | 1.68 | $2,292 | 2.73 | $2,461 | 2.69 |
| 65% | $2,333 | 1.92 | $2,629 | 2.76 | $2,880 | 2.89 |
| 75% | $2,654 | 2.11 | $2,936 | 2.93 | $3,201 | 3.07 |

Read the columns, not the rows: a profit target **alone** is worth little (t 1.1–2.1).
A stop **alone** is worth little (t 1.56–1.64). Together they produce t of 2.7–4.6.
Tested without a stop, a 30% target does look mediocre — which matches the spec's note.

A 30% target fires in 37 of 41 weeks. Average win $94, average loss −$303, worst
−$373. It converts a fat-tailed payoff into a boring one, and cuts max drawdown
from −$1,405 to **−$215**.

---

## Every other parameter

**Stop level** (no PT, $1.00 floor, Friday close) — 1.5× is destructive:

| Stop | Win% | Total | Max DD |
|---|---|---|---|
| none | 70.7% | $1,685 | −$1,657 |
| **1.5×** | **46.3%** | **$362** | −$1,658 |
| 2.0× | 65.9% | $1,993 | −$1,405 |
| 2.5× | 70.7% | $2,086 | −$1,298 |
| 3.0× | 70.7% | $2,029 | −$1,470 |

A 1.5× stop cuts the win rate almost in half. 2.0–2.5× is the usable band — the same
result the QQQ study produced independently.

**Minimum credit floor** — no P&L benefit:

| Floor | Weeks | Total |
|---|---|---|
| $0.00 | 52 | $2,007 |
| $1.00 | 41 | $1,993 |
| $1.50 | 29 | $1,342 |
| $1.75 | 21 | $924 |

The floor is defensible as a max-loss cap ($500), but it is not adding return — it
removes weeks at roughly the average edge. Raising it above $1.00 clearly hurts.

**Friday 3 PM close** costs $326 over 41 weeks (~$8/week) versus holding to
settlement ($1,993 vs $2,319). The spec estimated ~$2/week. Still cheap insurance
against a pin, but price it honestly at ~$8.

**Slippage** (35% PT + 2.5× stop): the edge survives a $0.15–0.20 per-condor haircut
(t 2.3) and degrades to t 1.78 at $0.30. Given the live SPY entry needed three
price-walks to fill, $0.10–0.20 is the realistic planning range.

---

## How much of this is data mining?

Honest accounting, and it cuts both ways.

- **300 combinations searched.** Per-week sd is $190, so a zero-edge strategy over 41
  weeks has a total with sd $1,218, and the best of 300 correlated variants should
  reach **+$2,436 to +$3,045** on luck alone. The top cell ($3,283) is barely above that.
- **But the whole distribution is positive.** 300/300 cells profitable, 188/300 reach
  t > 2. Noise produces a distribution centred on zero, not one where every cell wins.
  This is the opposite of the QQQ result (8% of cells profitable).
- **Out-of-sample is mixed.** Fit on the 1st half → +$106 out-of-sample. Fit on the 2nd
  half → +$2,286. No clean inversion like QQQ, but no clean confirmation either.
- **The strongest single claim** — that a profit target plus a stop beats holding — is
  not a lone grid cell. It holds across all six PT levels and both stop levels, 12
  cells, all pointing the same way. That is a pattern, not a pick.

---

## Reconciliation with the spec's own 36-week backtest

| Window | Weeks | Win% | Total |
|---|---|---|---|
| Jan–Sep 2026 (the spec's window) | 29 | 65.5% | $1,405 |
| Sep–Dec 2025 (added here) | 12 | 66.7% | $589 |
| Full 52 weeks | 41 | 65.9% | $1,993 |

The spec reports 36 weeks, 83% wins, +$2,677. I get 29 traded weeks and 65.5% over
the same calendar window. The gap is most likely strike selection: the spec's deltas
came from live chains, mine are solved from a Black-Scholes proxy calibrated to the
2026-09-21 chain, so my strikes sit slightly closer to the money — more credit
($187 average), more frequent tests. Directionally the two agree; the levels differ.

The best config holds up on both sub-periods: 30% PT + 2.0× stop returns $1,924
(t 4.84) on Jan–Sep 2026 and $419 (t 1.28) on the shorter Sep–Dec 2025 stub.

---

## Not tested

**Wing width was not swept.** Every alternative width needs different contracts —
roughly 200 more instrument lookups and another 26 price pulls. The $6 wing is the
only one with real prices here. This is the one parameter from the request still open.

Other limits: strikes are model-selected rather than live-delta-selected; the stop is
checked on hourly closes (a real alert-driven stop would be slower); no macro-event
filter is applied; and weekly returns are treated as independent for the t-statistics,
which overstates significance because volatility clusters.

---

## Recommendation

Change one thing: **add a 30% profit target on top of the existing 2.0× stop.** Same
entry, same strikes, same wings, same Friday close. It roughly matches the current
configuration on total return while cutting max drawdown from −$1,405 to −$215 on a
$4,911 account, and it is the only change in this study supported by a consistent
12-cell pattern rather than a single grid winner.

Leave the credit floor at $1.00 for the max-loss cap, not for return. Do not tighten
the stop below 2.0×.
