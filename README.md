# SLINGSHOT VELOCITY PARABOLIC

Autonomous BTC/ETH perps funding/basis arb + SOL/BASE meme scanner. Paper-first by design.

## Status: PAPER ONLY — full system built, hardened, and verified 2026-10-11

`config/default.toml` → `mode = "paper"`. Live mode requires all 6 gates in
`state/approvals.json` (`1-spec` through `6-ship`) — none are approved.
`approvals.require_all_approved()` refuses live mode without them, and
`trader approve 6-ship` is hard-refused via CLI.

## What was built (26 files, ~1,300 lines)

- `src/trader/config.py` — TOML config, frozen dataclasses, refuses looser limits
- `src/trader/state_engine.py` — deterministic <400-token snapshots, no future leak
- `src/trader/risk.py` — hard layer: kill file, arming, 15% max DD (sticky trip,
  manual re-arm), $10/30% daily loss (clears on day rollover), -20% halt, position caps
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
- `src/trader/loop.py` — main loop: day-rollover PnL reset, tick error circuit-breaker (10 strikes),
  log rotation at 50MB, feed-fallback warnings, synthetic + base feeds
- `src/trader/cli.py` — `arm | run | status | review | approve`
- `monitor/app.py` — dashboard + /api/health + kill-switch UI (stdlib only)
- `research/regime.json` — thesis template (fill before any live consideration)
- `tests/test_trader.py` — 23 tests, all green
- `docs/LIVE_PATH.md` — the human-gated path to live, step by step

## Verified

- 23/23 unit tests pass (risk trips, day-rollover semantics, guards, sizing, stash/velocity ladders)
- Paper soak: judge fires 95-pathway on genuine setups, entries open,
  guards manage positions, ledger tracks bankroll/PnL/drawdown
- Monitor reads live ledger; kill switch writes `/tmp/slingshot_kill`

## Run

```bash
pip install -r requirements.txt
python -m unittest discover -s tests          # tests
PYTHONPATH=src python -m trader.cli run --feed synthetic --max-ticks 300 --interval 0
PYTHONPATH=src python -m trader.cli review    # soak summary
python monitor/app.py                          # dashboard :3000
```

## Going live (human steps, not automated)

See `docs/LIVE_PATH.md`. Summary: fill the research theses, 14-day paper soak,
approve gates 1–5, hand-edit gate 6-ship, add keys via `fly secrets set`, flip
`mode = "live"`, deploy. The order-placement code is intentionally not written —
that last mile is yours.

## Warnings

- The "Jev" service at `console.typesafe.ai` is **unverified** — domain resolves
  behind Cloudflare but the judge API could not be confirmed. PaperJudge is the
  working default.
- Return targets in the original spec (1.5x/day, 200x) are not realistic.
  This system is well-engineered plumbing around unproven edge.
- Never commit real API keys. `.env.example` is a template only.
