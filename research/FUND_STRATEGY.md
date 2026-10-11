# FUND STRATEGY — Delta-Neutral Funding Harvest

**Status: RESEARCH COMPLETE — edge not found. Do not deploy.**

This document is the honest record of a fund-grade strategy research program:
what was built, what was tested, what the data said, and what would need to
change for this to become deployable.

---

## 1. The strategy (as designed)

A delta-neutral funding-rate arbitrage fund:

| Component | Design |
|---|---|
| Universe | 12 high-dislocation alt perps (Hyperliquid) with liquid spot |
| Capital | $500,000 |
| Position | $25,000 notional (5% of fund), max 8 concurrent |
| Entry | `|funding|` annualized ≥ 30–50% |
| Hedge | funding > 0 → SHORT perp + LONG spot; funding < 0 → LONG perp + SHORT spot |
| Exit | `|funding|` < 10% or 72h max hold |
| Costs | Maker-biased: 1bps perp, 8bps spot, 3bps slippage per fill |

The infrastructure is production-grade: portfolio-level position management,
hourly NAV tracking, Sharpe/max-drawdown/win-rate reporting, P&L decomposition
(funding vs borrow vs costs vs basis), re-entry cooldowns, liquidity filters.

Code: `research/fund_backtest.py`, `research/fund_fetch.py`, `research/spike_analyzer.py`
Data: `research/data/fund/` (21 days, 12 coins, hourly funding + perp + spot)

## 2. What the data said

**Backtest (21 days, $500k fund):**

| Entry threshold | Trades | Net P&L | Ann. return | Win rate | Sharpe |
|---|---|---|---|---|---|
| 50% | 47 | **-$1,469** | -5.2% | 43% | -3.54 |
| 30% | 62 | **-$3,677** | -12.9% | 34% | -5.74 |
| 20% | 69 | **-$3,861** | -13.6% | 30% | -5.98 |

**Spike lifecycle analysis (162 spikes ≥50%):**

| Metric | Median | p75 | Max |
|---|---|---|---|
| Duration above 20% | 4h | 8h | 61h |
| Harvestable funding ($25k) | $6 | $18 | $157 |
| Spikes covering $75 round-trip | — | — | **7/162 (4%)** |

## 3. Why it fails (root causes)

1. **Funding mean-reverts in ~4 hours (median).** Spikes are brief dislocations,
   not persistent regimes. The median spike yields $6 against $75 in costs.
2. **Costs are structural.** 4 fills × (fee + slippage) = ~30bps = $75/trade
   on $25k. Costs scale with size (bps-based); funding scales with size.
   Bigger size does NOT fix the ratio.
3. **Adverse selection on basis.** Extreme funding coincides with perp premium;
   as funding normalizes the premium compresses, adding -$259 to -$1,552
   of basis drag across the test.
4. **More trades = worse.** Lowering the entry bar from 50% to 20% added
   22 trades and lost an additional $2,392. The edge is not in frequency.
5. **Speed doesn't help.** Spikes last 4h; entering in seconds vs minutes
   doesn't change the $6 of harvestable funding.

## 4. What would need to change

For this strategy to become viable, at least one of these must be true:

- [ ] **Predict spike persistence.** Identify the 4% of spikes that last 24h+
    before entering. This is a forecasting problem, not an arb.
- [ ] **Earn rebates.** Maker rebates exceeding slippage (net negative costs).
    Requires top-tier volume and HFT infrastructure.
- [ ] **A different edge.** Market-making (earn spread + funding), cross-venue
    basis, or options-based carry — all different businesses.
- [ ] **A different regime.** In a sustained mania (weeks of elevated funding),
    the math works. The last 21 days were not that regime.

## 5. Infrastructure value

The fund backtesting framework itself is sound and reusable for any
delta-neutral strategy: multi-asset portfolio engine, realistic cost modeling,
spike lifecycle analysis, and full risk reporting. It is the right tool to
test the *next* thesis — it just proved this one wrong.

---

*Research completed 2026-10-11. Data: Hyperliquid public API + Coinbase public API.
All code and data pipelines in `research/`. Not financial advice.*
