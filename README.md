# spy-condor

Backtest of a weekly SPY iron condor on **real** Robinhood option prices —
208 expired contracts, 8,568 hourly bars, 52 weekly cycles from 2025-09-22 to
2026-09-18. Credits and exits are actual marks, not a Black-Scholes model.

Strategy under test: short put ~Δ0.16, short call ~Δ0.21, $6 wings, 1 contract,
entered Monday 10:00 ET, closed Friday 15:00 ET, $1.00 minimum credit.
Full rules in [`spy-iron-condor-strategy.md`](spy-iron-condor-strategy.md).

## Layout

| File | Purpose |
|---|---|
| `data.py` | Strike planner and parsers; rebuilds `data/` from raw Robinhood JSON. Documents the MCP fetch sequence (`--show-fetch-plan`). |
| `eval_all.py` | The engine. Runs all 52 weeks and prints per-week detail. Imported by the other two. |
| `sens.py` | One knob at a time: stop level, profit target, credit floor, exit timing, slippage, sub-window reconciliation. |
| `grid.py` | 300-cell parameter grid plus a chance baseline and an out-of-sample split. |
| `data/` | `spy_daily.csv`, `opt_bars.csv` (real hourly option bars), `weeks.json` (the 52-week plan), `ids_raw.txt` (contract UUIDs). |

No dependencies beyond the standard library.

```
python3 eval_all.py              # spec config, week by week
python3 eval_all.py --pt 0.30    # with a 30% profit target
python3 sens.py
python3 grid.py
```

## Result

Spec as written (hold, 2.0× stop, $1.00 floor, Friday 3pm close):

| | |
|---|---|
| Weeks traded | 41 of 52 (11 skipped on the credit floor) |
| Win rate | 65.9% |
| Total P&L | **+$1,993** — $49/week, sd $190, t = 1.64 |
| Worst week | −$323 |
| Max drawdown | −$1,405 |
| Avg credit | $187 on $6 wings; avg max risk $413 |

### The finding: the no-take-profit rule is what costs money

Every profit target beats holding — but **only when paired with a stop**. That
interaction is almost certainly why the earlier 36-week run concluded the
opposite.

| PT | no stop | 2.0× stop | 2.5× stop |
|---|---|---|---|
| hold | $1,685 (t 1.15) | $1,993 (t 1.64) | $2,086 (t 1.56) |
| **30%** | $1,717 (t 1.89) | **$2,342 (t 4.55)** | $2,128 (t 3.06) |
| 75% | $2,654 (t 2.11) | $2,936 (t 2.93) | $3,201 (t 3.07) |

Read the columns. A target alone is weak; a stop alone is weak; together t
reaches 2.7–4.6. **30% PT + 2.0× stop** cuts max drawdown from −$1,405 to
−$215 while improving return.

Also: a 1.5× stop is destructive (win rate falls to 46.3%). The credit floor
adds no return — keep it as the $500 max-loss cap, not as an edge. The Friday
3pm close costs ~$8/week versus holding to settlement, not the ~$2 originally
estimated.

## Honest accounting

- 300 cells searched. Per-week sd is $190, so a zero-edge 41-week total has
  sd $1,218 and the best of 300 correlated cells should reach +$2,436 to
  +$3,045 on luck alone. The top cell ($3,283) sits just above that.
- **But 300/300 cells are profitable** and 188 reach t > 2. Noise centres on
  zero; this does not.
- Out-of-sample is mixed: fitting on the first half returns +$106 out of
  sample, on the second half +$2,286.
- The profit-target claim is not one lucky cell — it holds across all six PT
  levels and both stop levels.

## Known limitations

- **Wing width is not swept.** Every alternative width needs different
  contracts (~200 more lookups, 26 more price pulls). Only $6 wings have real
  prices here. This is the largest open parameter.
- Strikes are solved from a Black-Scholes delta proxy calibrated to the
  2026-09-21 chain, not from live historical deltas. They sit closer to the
  money than the live trade: average credit is 31% of width against 17% on the
  actual 2026-09-25 position. This likely explains most of the gap against the
  original 36-week numbers (83% win rate there, 65.5% here on the same window).
- The stop is evaluated on hourly closes; a real alert-driven stop would be slower.
- No macro-event filter is applied, though the spec calls for one.
- t-statistics treat weeks as independent. Volatility clusters, so true
  confidence intervals are wider than reported.

Not investment advice. Past results, especially parameter-searched ones, are a
poor guide to forward performance.
