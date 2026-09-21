# SPY Weekly Iron Condor Strategy — Spec for Automation

> Account identifiers are redacted as `<AGENTIC_ACCOUNT>` and `<SECONDARY_ACCOUNT>`.
> Substitute real values from a local untracked config; do not commit them.

## Account

* Robinhood account: `<AGENTIC_ACCOUNT>` ("Agentic"), limited margin, option level 3, agentic-trading enabled.
* Account size: ~$5,000 cash / buying power.
* Underlying: SPY only (not SPX — index-option fees on Robinhood run ~$1.05–1.13/contract vs. ~$0.04–0.06 for SPY, which eats ~22% of a typical win at this size).
* Second account `<SECONDARY_ACCOUNT>` is NOT agentic-accessible; do not use.

## Instrument

* Weekly SPY iron condor, 1 contract per leg (4 legs total), Friday expiry.
* Chain ID: `c277b118-58d9-4060-8dc5-a3b5898955cb` (reconfirm each session; may change).

## Entry rules

* **When:** Monday 10:00 AM ET (or Tuesday 10:00 AM ET if Monday is a holiday), after the first 30 minutes of trading.
* **Strikes:** short put at ~Δ0.16, short call at ~Δ0.21 (call side skewed wider because SPY's call-side IV typically runs ~2–4 vol points below put-side IV — this asymmetry should be re-checked live, not assumed).
* **Wings:** $6 wide on both sides (long put = short put − 6; long call = short call + 6).
* **Re-centering:** if SPY has moved more than ~$2 from the price the plan was built on, rebuild strikes from live deltas rather than using stale strikes.
* **Minimum credit floor:** net credit must be ≥ $1.00 (on $6 wings) or skip the week. This caps max loss at ≤ $500.
* **Macro filter:** skip or reduce size in weeks with major scheduled catalysts (FOMC, CPI, NFP/jobs report, GDP, PCE). Check the economic calendar before entering.
* **Vol filter (soft):** favor weeks where implied vol (VIX or SPY option IV) is clearly above recent realized vol; the edge disappears/reverses when realized vol exceeds implied.

## Order execution

* **Preferred:** single 4-leg net-credit limit order at the package mid, submitted via Robinhood's order review first (no live orders without reviewing: fees, collateral, alerts).
* **Fallback** if 4-leg orders aren't supported by the trading interface: execute one leg at a time, in this order:
   1. Buy long put (limit at ask)
   2. Buy long call (limit at ask)
   3. Sell short put (limit at bid)
   4. Sell short call (limit at bid)
   * Longs first, shorts last — never sell a short leg before its corresponding long is filled (avoids naked/undefined risk).
   * Buy legs: limit at or above the ask for immediate fill. Sell legs: limit at or below the bid for immediate fill. (Do not set a sell limit above the ask expecting a fast fill — it won't fill until the market comes to it.)
   * Confirm each leg's fill via order status before placing the next.
   * Recompute net credit after all 4 legs fill; if it has drifted below the $1.00 floor, that's a judgment call (proceed if only marginally under, otherwise flag it).

## Exit rules

> **Addendum (added with this repo, not part of the original spec).** A 52-week
> backtest on real option prices contradicts the no-take-profit rule below. Every
> profit target tested beats holding *when paired with a stop*; a 30% target plus
> the existing 2× stop returns $2,342 against $1,993 and cuts max drawdown from
> −$1,405 to −$215 (t = 4.55 vs 1.64). Tested *without* a stop active, a 30%
> target does look poor, which likely explains the original 36-week conclusion.
> See `README.md` and run `python3 sens.py`. The original text stands below.

* No take-profit order. (A 30% take-profit was the worst-performing rule tested; even 50–65% take-profits underperformed holding.)
* **Stop-loss:** close the position if the loss reaches 2× the credit received.
   * Concretely: if credit = C, close when cost-to-close ("package mark," i.e. cost to buy back shorts minus proceeds from selling longs) reaches C + 2C = 3C.
   * This must be monitored manually / via price alerts — Robinhood's multi-leg orders are limit-only, no stop-loss order type exists for multi-leg positions.
   * Practical proxy: set price alerts on SPY at the two short strikes (not the exact stop price, which shifts daily with theta decay). When an alert fires, pull live option marks and check actual loss against the 2C threshold before deciding to close.
   * Expect actual stop fills to land worse than exactly 2C on overnight gaps (backtest saw $240–370 realized losses against credits of ~$100–180, i.e. roughly 2–2.5× in practice due to gap risk).
* **Close everything by 3:00 PM ET Friday**, regardless of P&L, even though SPY options technically trade until ~4:15 PM ET. This eliminates pin risk / weekend assignment risk (a short strike settling within pennies of the money can trigger after-hours assignment with no protective long wing exercised against it, leaving ~$76k of stock exposure on a $5k account). The extra 75 minutes of trading availability doesn't reduce this risk — it's about proximity to strikes at settlement, not exchange hours.

## Assignment / pin risk notes

* SPY options are American-style; early assignment is rare but possible on deep-ITM short puts with no time value, or short calls the day before an ex-dividend date if remaining time value < the dividend (SPY ex-div ~mid-March/June/Sept/Dec).
* The Friday 3 PM close rule is the primary mitigation. Cost of this rule in the original backtest: ~$2/week average. *(The 52-week study puts it nearer $8/week — still cheap insurance, but price it honestly.)*

## Fees (Robinhood, SPY/ETF options)

* No per-contract commission.
* Pass-through: ~$0.04/contract (OCC+ORF, both sides) + ~$0.003/contract TAF (sells only) + SEC fee (sells only, negligible at this size).
* Full 4-leg condor round trip: ~$0.36 total. Immaterial next to slippage.

## Backtest summary (original 36-week run; for context, not a forward-looking guarantee)

* 36 weeks tested (Jan–Sep 2026) using real historical Robinhood option prices.
* Hold-to-expiry + 2× stop + Friday close: +$2,677 total, 30/36 winning weeks, worst single week −$370.
* 30% take-profit (the original naive rule): −$439 without a stop; this rule is retired.
* Losses came from sustained directional trends (SPY rallying/breaking through the call side), not from volatility spikes — the strategy survived a VIX 25–35 stretch in March without a loss.
* Caveat: exit-rule parameters (2× stop level, Friday-close timing) were selected by testing many variants on this same 36-week sample — expect real forward performance to run meaningfully below the backtest, plausibly 35–40% lower.

## Open items / not yet automated

* No standing stop-loss order exists on Robinhood for multi-leg spreads — any automation needs to poll option marks and act, not rely on a broker-side stop.
* Multi-leg order placement via the Robinhood Agent MCP tool returned "not supported yet" — single-leg sequential execution was used as a workaround. Automation should handle both paths (try multi-leg, fall back to sequential) and re-verify each time, since it may change.
* Delta targets (Δ0.16 put / Δ0.21 call) and the $6 wing width are the tuned defaults; **no systematic optimization of wing width has been performed** — this remains the largest untested parameter.
