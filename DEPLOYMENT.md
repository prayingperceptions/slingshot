# DOUBLE EDGE FUND — Deployment Roadmap
## From Paper to Live, Step by Step

**Current status: PAPER MODE. No real money. No exchange keys. No live orders.**

This document is the exact sequence to make the fund real. Each phase requires
explicit user approval before proceeding to the next. No step is automatic.

---

## Phase 1: Paper Track Record (ACTIVE NOW)

**Goal:** Build a verifiable live track record on paper before risking capital.

- [x] Strategy validated on 111 days historical (+6.6% ann, 80% win)
- [x] Production engine built (`src/fund/double_edge.py`)
- [x] State persistence (`state/fund_state.json`)
- [ ] Run paper fund 24/7 for 30 days minimum
- [ ] Compare live paper results vs backtest expectations
- [ ] Document any divergence

**Run it:**
```bash
# hourly via cron, or:
PYTHONPATH=src python -m fund.double_edge 24  # 24 ticks
```

**Gate to Phase 2:** 30 days of paper trading with results roughly matching
backtest (positive, 60%+ win rate). If paper fails, STOP — do not proceed.

## Phase 2: Exchange Setup (USER ACTION REQUIRED)

**Goal:** Create the accounts and API keys needed for live execution.

### Hyperliquid (perp leg)
- [ ] Create Hyperliquid account
- [ ] Deposit USDC (start with $1,000 test amount)
- [ ] Generate API key with **trade-only permissions** (no withdrawals)
- [ ] Store key in secure vault (NEVER in chat, code, or config files)
- [ ] Verify API connectivity with read-only calls

### Binance or Coinbase (spot leg)
- [ ] Create account (Binance preferred for lower maker fees)
- [ ] Complete KYC
- [ ] Deposit USDC/USDT (start with $1,000 test amount)
- [ ] Generate API key with **trade-only permissions** (no withdrawals)
- [ ] Store key in secure vault
- [ ] Verify API connectivity

**Security rules:**
- Keys NEVER in chat, code, git, or logs
- Trade-only permissions (withdrawals disabled)
- IP allowlisting if the exchange supports it
- Start with minimum deposits

**Gate to Phase 3:** Both exchanges connected, API verified, test deposits confirmed.

## Phase 3: Live Execution Test (NEEDS EXPLICIT APPROVAL)

**Goal:** Prove live execution works with tiny size before scaling.

- [ ] Implement `LiveExecutor` class (real order placement via exchange APIs)
- [ ] **USER APPROVAL REQUIRED:** Place first live test trade ($100 notional)
- [ ] Verify: both legs fill, hedge is delta-neutral, costs match model
- [ ] Run 10 test trades at $100-500 size
- [ ] Compare live costs vs backtest cost model
- [ ] Document slippage, fill rates, any issues

**If live costs exceed 25bps:** STOP. The edge doesn't survive. Do not scale.

**Gate to Phase 4:** 10 successful test trades, costs within model, no major issues.

## Phase 4: Gradual Scale (NEEDS EXPLICIT APPROVAL PER STEP)

**Goal:** Scale to full size incrementally, verifying at each step.

- [ ] **Approval 1:** Scale to $1,000/position (4% of target size)
- [ ] Run 2 weeks, verify performance
- [ ] **Approval 2:** Scale to $5,000/position (20% of target size)
- [ ] Run 2 weeks, verify performance
- [ ] **Approval 3:** Scale to $25,000/position (full size)
- [ ] Ongoing monitoring

**At each step:** If win rate drops below 60% or costs exceed model, HALT and investigate.

## Phase 5: Ongoing Operations

- Daily NAV reconciliation
- Weekly performance review vs backtest
- Monthly strategy review (is the edge decaying?)
- Kill switch: `touch /tmp/slingshot_kill` flattens everything

---

## Risk Disclosure

- Past performance (backtest + paper) does not guarantee future results
- Crypto markets are volatile; delta-neutral does not mean risk-free
- Basis can diverge further before converging (unlimited loss on directional leg if hedge fails)
- Exchange risk: hacks, outages, API failures
- Smart contract risk (Hyperliquid)
- Regulatory risk

**Maximum recommended allocation:** Only capital you can afford to lose entirely.

---

*Last updated: 2026-10-11. Status: Phase 1 active.*
