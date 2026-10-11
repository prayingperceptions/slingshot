# SLINGSHOT VELOCITY PARABOLIC

Autonomous BTC/ETH perps funding/basis arb + SOL/BASE meme scanner. Paper-first by design.

## Status: PAPER ONLY — full system built and verified 2026-10-11

`config/default.toml` → `mode = "paper"`. Live mode requires all 6 gates in
`state/approvals.json` (`1-spec` through `6-ship`) — none are approved.
`approvals.require_all_approved()` refuses live mode without them, and
`trader approve 6-ship` is hard-refused via CLI.

## What was built (24 files, ~1,200 lines)

- `src/trader/config.py` — TOML config, frozen dataclasses, refuses looser limits
- `src/trader/state_engine.py` — deterministic <400-token snapshots, no future leak
- `src/trader/risk.py` — hard layer: kill file, arming, 15% max DD, $10/30% daily loss, -20% halt, position caps
- `src/trader/approvals.py` — 6-gate live approval system
- `src/trader/jev/schema.py` + `jev/client.py` — JevDecision + 95-pathway gate; JevClient (HTTP) + PaperJudge (deterministic rules fallback, "code owns thresholds")
- `src/trader/market.py` — PnL calc, book-walk fill simulation
- `src/trader/policy.py` — sizing (20% @ ≥0.97 else 5%), spread edge filter
- `src/trader/execution/paper.py` — PaperBroker: simulated fills, real accounting, auditable ledger
- `src/trader/execution/jupiter.py` — Jupiter Ultra client (paper-simulated; live refused)
- `src/trader/execution/base.py` — Base token data via Dexscreener public API (read-only, no key)
- `src/trader/execution/stash.py` — parabolic profit-stash ladder (2x/3x/5x/8x+)
- `src/trader/execution/velocity.py` — reinvest ladder (100/70/50/30%)
- `src/trader/guards/` — whale (>1%), liquidity (-30%), sentiment (-0.5/5m), parabolic (trailing, time decay, RSI, funding flip)
- `src/trader/engine.py` — tick pipeline: snapshot → judge → risk → policy → execute → guards → stash
- `src/trader/loop.py` — main loop, synthetic + base feeds, kill-file aware
- `src/trader/cli.py` — `arm | run | status | review | approve`
- `monitor/app.py` — dashboard + /api/health + kill-switch UI (stdlib only)
- `research/regime.json` — thesis template (fill before any live consideration)
- `tests/test_trader.py` — 21 tests, all green

## Verified

- 21/21 unit tests pass
- 300-tick paper soak: judge fires 95-pathway on genuine setups, entries open,
  guards manage positions, ledger tracks bankroll/PnL/drawdown
- Monitor reads live ledger; kill switch writes `/tmp/slingshot_kill`

## Run

```bash
.venv/bin/python -m unittest discover -s tests          # tests
PYTHONPATH=src .venv/bin/python -m trader.cli run --feed synthetic --max-ticks 300 --interval 0
PYTHONPATH=src .venv/bin/python -m trader.cli review    # soak summary
.venv/bin/python monitor/app.py                          # dashboard :3000
```

## Going live (human steps, not automated)

1. Fill `research/regime.json` with 5-10 real theses
2. 14-day paper soak, review nightly
3. Approve gates 1-5 via `trader approve <gate>`
4. Gate 6-ship: edit `state/approvals.json` by hand — deliberate friction
5. Add real keys to `.env`, set `mode = "live"`, deploy to Fly.io

## Warnings

- The "Jev" service at `console.typesafe.ai` is **unverified** — domain resolves
  behind Cloudflare but the judge API could not be confirmed. PaperJudge is the
  working default.
- Return targets in the original spec (1.5x/day, 200x) are not realistic.
- Never commit real API keys. `.env.example` is a template only.
