# Going Live — the real option, step by step

Paper is the default. Live is a real, supported option — but every step
below is a deliberate human action. Nothing here auto-arms.

## Preconditions (do not skip)

1. `research/regime.json` filled with 5–10 real theses (catalyst, bear case,
   invalidation, live sources with dates).
2. 14-day paper soak on real market data, reviewed nightly via `trader review`.
   If the ledger doesn't survive paper, it won't survive live.
3. Read this entire file before touching a key.

## Steps

### 1. Implement the live exchange clients (the last mile)

The engine calls two interfaces in live mode. Both are stubbed on purpose —
you (or someone you trust, reviewing every line) implement them:

- `src/trader/execution/jupiter.py` — `JupiterClient.quote()` currently
  raises in live mode. Implement against the Jupiter Ultra Order API
  (`https://ultra.jup.ag/order`): build the order request, sign with your
  Solana keypair, submit, confirm. Start with the Ultra API docs.
- Perps (Hyperliquid or similar): there is no perps client yet — create
  `src/trader/execution/perps.py` with the same shape (`quote`/`submit`
  returning the dict `JupiterClient.quote` returns in paper). Never reuse
  keys across venues.

Keep the paper implementations. Live code must return the exact same
dict shape so the engine, guards, and ledger behave identically.

### 2. Keys

- Copy `.env.example` to `.env` (never commit it — check `.gitignore`).
- Keys live in the environment, never in code, never in chat, never in logs.
- Use separate sub-accounts / limited-permission API keys per venue.
- Fund with money you can lose completely. Size it as tuition.

### 3. Approve the gates

```bash
PYTHONPATH=src python -m trader.cli approve 1-spec
# ... through 5-review, one at a time, after actually doing each phase
```

Gate `6-ship` is refused via CLI on purpose. When — and only when — steps
1–3 are genuinely done, hand-edit `state/approvals.json` and set `6-ship`
to `true`. That friction is the point.

### 4. Flip the mode

In `config/default.toml`: `mode = "live"`. The loop asserts paper and will
now proceed; `require_all_approved()` is checked before any live run.

### 5. Deploy

```bash
fly launch          # first time
fly deploy          # ships fly.toml as configured
```

Set secrets via `fly secrets set`, never in `fly.toml` or the repo.

### 6. Operate

- `monitor/app.py` (or the Fly service) shows bankroll, positions, decisions.
- The kill switch: `touch /tmp/slingshot_kill` (or the dashboard button)
  flattens everything on the next tick. Test it in paper first.
- Daily: `trader review`. Weekly: re-read your theses. The moment a thesis
  invalidates, stop that market — don't tune the bot to keep trading it.

## What live does NOT change

- Risk layer is identical: 15% max DD, $10/30% daily loss, -20% halt,
  position caps, kill file. These are hard-coded, not suggestions.
- The 95-pathway still governs every entry. If it stops firing, the bot
  stops trading. That is correct behavior, not a bug to fix.
- Fees and slippage are real now. A $10 position needs a genuine edge
  after costs — re-check the math before sizing up.

## Honest expectations

This system is well-engineered plumbing around unproven edge. Going live
tests the *strategy*, not the code — the code is already verified.
Size accordingly.
