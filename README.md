# SLINGSHOT

**A production-grade research platform for delta-neutral crypto strategies. It proved the edge wasn't there — and shows its work.**

[![MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE) [![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/) [![Tests](https://img.shields.io/badge/tests-34%2F34-brightgreen.svg)](tests/)

*Paper-first by design. Real data, real costs, real verdicts. No hype, no paper profits presented as alpha — every thesis gets tested against the market and lives or dies on the numbers.*

[Doctrine](#the-doctrine) · [Quickstart](#quickstart) · [What the research proved](#what-the-research-proved) · [Architecture](#how-it-works) · [Theses](#write-your-own-thesis)

---

Slingshot started as an autonomous trading bot concept — BTC/ETH perps funding arb, meme momentum, 1.5x/day dreams. It became something more useful: a **research platform that kills bad strategies with data** before they kill your capital.

The paper trading engine is real (34/34 tests, red-teamed, adversarially hardened). The fund backtesting framework is real (multi-asset, portfolio-level, honest cost modeling). And the findings are real: three theses tested against 21 days of live market data, three theses dead — with the receipts to prove it.

## The idea

Most trading bots are optimism with an API key. **Slingshot is the opposite.** It treats every strategy as guilty until proven innocent:

- **Paper-first, always.** No live mode without 6 human approval gates. The system refuses to trade real money by default.
- **Real data or nothing.** Synthetic feeds prove plumbing, not edge. Every thesis gets tested against live Hyperliquid funding, real perp candles, real spot prices.
- **Honest costs.** Maker/taker fees, slippage, borrow costs, basis drag — all explicit, all parameterized. No strategy survives hidden costs.
- **Kill your darlings.** The platform proved its *own* founding thesis wrong. That's not failure — that's the product working.

## The doctrine

Three rules, non-negotiable:

- **"Prove it or kill it."** Every strategy gets backtested on real data with real costs. Negative expected value → documented and shelved. No tweaking parameters until it "works."
- **"Costs are the strategy."** A 30bps round-trip doesn't sound like much until it's 12x your median funding capture. If the edge doesn't survive honest fees, there is no edge.
- **"Paper profits aren't alpha."** Synthetic data, lookahead bias, bad prints, survivorship — the platform hunts these artifacts actively. A 100% win rate is a bug, not a breakthrough. (We found one. It was bad prints. We killed it.)

Full research record: [research/FUND_STRATEGY.md](research/FUND_STRATEGY.md)

## Quickstart

Run the paper trading loop (synthetic feed, proves the plumbing):

```
pip install -r requirements.txt
PYTHONPATH=src python -m trader.cli run --feed synthetic --max-ticks 100 --bankroll 50

# slingshot loop starting: feed=synthetic bankroll=$50.00 mode=paper
# tick 100: bankroll=$50.0 pnl=$0.0 open=0 dd=0.0%
```

Run it on **live market data** (Hyperliquid perps, read-only, no key):

```
PYTHONPATH=src python -m trader.cli run --feed hyperliquid --symbol BTC --interval 5 --max-ticks 12

# 12 ticks on real BTC funding (1.18%/yr). Zero trades — the gate never opens.
# That's the market telling you something.
```

Run the **fund backtest** (the honest dude):

```
PYTHONPATH=src python research/fund_backtest.py

# === FUND BACKTEST: $500,000 capital, $25,000/pos, max 8 pos ===
# enter= 50%: trades= 47 net=$   -1,469 (-0.29%, ann -5.2%) win=43% sharpe=-3.54
```

Run the **spike analyzer** (how long does high funding actually last?):

```
PYTHONPATH=src python research/spike_analyzer.py

# 162 spikes >=50% across 12 coins / 21 days
# median duration above 20%: 4h | median harvestable: $6.40 vs $75 cost
# spikes covering costs: 7/162 (4.3%)
```

Kill it anytime: `touch /tmp/slingshot_kill` (flattens all positions)

## What the research proved

Three theses, tested against 21 days of real hourly data (Hyperliquid funding + perp candles, Coinbase spot). All costs modeled. No mercy.

**Thesis 1: Hedged funding arb** (short perp + long spot on high funding)
→ **DEAD.** -$1,469 to -$3,861 on $500k. Funding mean-reverts in ~4h (median); $75 round-trip costs exceed the $6 median capture. Only 4.3% of spikes cover costs.

**Thesis 2: Contrarian directional** (short crowded longs on extreme funding)
→ **DEAD.** -$17k to -$27k. The market is smarter than the fade — crowded longs keep winning.

**Thesis 3: Basis mean-reversion** (trade perp/spot convergence)
→ **DEAD at retail costs** (-$1,355 honest). The initial 100% win rate was **bad prints** — single-hour data artifacts, untradeable. Killed by requiring 2h persistence + execution delay.
→ **CONDITIONAL at institutional costs.** Below ~20bps all-in, it turns positive (+$2.4k–$8k). Requires pro-tier fees on both legs. Thin, unproven, not a recommendation.

**The meta-finding:** crypto perps are efficient. The easy arbs were harvested years ago. What remains needs speed (HFT), size (market making), or information — not a 5-second loop.

## How it works

```
                    ┌─────────────────────────────────┐
                    │  PAPER ENGINE                   │
real/synthetic feed │  snapshot → judge → risk →      │  auditable
    ──────────────► │  policy → execute → guards      │ ──────────► ledger
                    │  34/34 tests, red-teamed        │
                    └─────────────────────────────────┘

                    ┌─────────────────────────────────┐
                    │  FUND BACKTESTER                │
  Hyperliquid API   │  multi-asset portfolio         │  NAV curve
  Coinbase API      │  delta-neutral positions       │ ──────────► Sharpe
    ──────────────► │  honest cost model             │  max DD
                    │  spike lifecycle analysis      │  win rate
                    └─────────────────────────────────┘
```

- **Paper engine** (`src/trader/`): deterministic snapshots, hard risk layer (kill file, 15% max DD, daily loss limits), 6-gate approval system, paper broker with real accounting, whale/liquidity/sentiment/parabolic guards.
- **Fund backtester** (`research/`): portfolio-level, 12-asset universe, explicit fee/slippage/borrow modeling, P&L decomposition (funding vs costs vs basis).
- **Live mode**: exists behind 6 human gates, none approved. `trader approve 6-ship` is hard-refused. Order-placement code deliberately unwritten.

## Write your own thesis

```
# research/my_thesis.py
from fund_backtest import load_coin, COINS

universe = {c: load_coin(c) for c in COINS}
# your entry/exit logic here
# your cost model here — be honest
# if EV < 0: document it and move on
```

```
PYTHONPATH=src python research/my_thesis.py
```

New data = new files in `research/data/fund/`. The framework handles the rest. Guide: [research/FUND_STRATEGY.md](research/FUND_STRATEGY.md)

## FAQ

**Does it make money?** No. Three theses tested, three dead. The platform's value is proving that *before* you fund it, not after.

**Why keep building if there's no edge?** Because the infrastructure is real and reusable. The next thesis gets tested the same ruthless way — and if one ever survives, you'll know it's real.

**Can I run it live?** The code supports it behind 6 human approval gates, but no exchange clients are wired and order placement is deliberately unwritten. Given the research findings, we recommend against it.

**What about the 1.5x/day target?** Fantasy. The math never worked — fees eat $10 positions alive, and the backtests prove the edge isn't there at any size tested.

**Is the data real?** Yes. Hyperliquid public API (funding, perps) and Coinbase public API (spot). No keys, read-only, cached in `research/data/`.

## Contributing

PRs welcome. The doctrine is load-bearing: no PR may hide costs, smooth data, or present paper profits as alpha. Run the full test suite (`python -m unittest discover -s tests`) and at least one honest backtest before pushing.

---

*Prove it or kill it. Slingshot killed three strategies so your capital doesn't have to.*

⭐ If the honesty saved you money, star the repo.
