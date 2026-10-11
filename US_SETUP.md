# US Setup Guide — Double Edge Fund

## Why Binance.US (not Binance global, not Coinbase)

You're US-based. Your spot venue options:

| Venue | Maker fee | $25k trade cost | Verdict |
|---|---|---|---|
| **Binance.US** | **0.00%** | ~$7.50 (slippage only) | ✅ Edge survives |
| Kraken Pro | 0.40% | ~$107.50 | ❌ Kills the edge |
| Coinbase Advanced | 0.50% | ~$132.50 | ❌ Kills the edge |

The double edge needs <20bps all-in. Binance.US at 0% maker is the ONLY US
venue where the math works. With limit orders:
- Spot: 0bps fee + 3bps slippage = 3bps × 2 fills = 6bps
- Perp (Hyperliquid): 0.5bps + 2bps = 2.5bps × 2 fills = 5bps
- **Total: ~11bps** ✅

**Tradeoff:** Binance.US lists 6 of our 12 coins (NEAR, ALGO, ONDO, PENGU,
USELESS, FARTCOIN). Missing MINA and AZTEC (our top backtest performers).
US universe backtest: +$886 over 111 days at 11bps (84% win) vs +$10,066
full universe. Thinner, but real and compliant.

## Step 1: Binance.US Account

1. Go to [binance.us](https://www.binance.us) → Sign Up
2. Complete KYC (driver's license + selfie, ~10 min)
3. Enable 2FA (Google Authenticator, NOT SMS)
4. Deposit: bank transfer (ACH, free) or crypto
   - Start with $1,000-$2,000 for test phase
5. Generate API key:
   - Account → API Management → Create API
   - **Permissions: Enable Spot Trading ONLY**
   - **DISABLE withdrawals** (critical)
   - Note the API key + secret → store in secure vault
   - Enable IP allowlisting if you have a static IP

## Step 2: Hyperliquid Account

1. Go to [app.hyperliquid.xyz](https://app.hyperliquid.xyz)
2. Connect wallet (MetaMask, Rabby, or Coinbase Wallet)
3. No KYC required — wallet IS your account
4. Deposit USDC:
   - Bridge USDC from Arbitrum (or buy on exchange, withdraw to Arbitrum)
   - Deposit into Hyperliquid (gas-less, takes ~1 min)
   - Start with $1,000-$2,000 for test phase
5. Generate API key:
   - Settings → API → New API Key
   - **Trade-only permissions** (Hyperliquid API keys can't withdraw by default)
   - Store in secure vault

## Step 3: Verify Both Work

```bash
# Test Hyperliquid read-only (no key needed)
curl -X POST https://api.hyperliquid.xyz/info \
  -H "Content-Type: application/json" \
  -d '{"type": "metaAndAssetCtxs"}' | head -c 200

# Test Binance.US (needs API key in vault)
# We'll do this together when you're ready
```

## Fee Reality Check

Before going live, verify your ACTUAL fee tier on Binance.US:
- Log in → Account → Fee Schedule
- Confirm 0% maker (should be default for all users)
- If you see anything else, STOP and tell me

## What NOT to Do

- ❌ Do NOT use market orders (taker fees kill the edge)
- ❌ Do NOT enable withdrawals on API keys
- ❌ Do NOT share keys in chat, email, or screenshots
- ❌ Do NOT deposit more than $2k until test trades verify costs
- ❌ Do NOT use Coinbase Advanced (50bps maker = edge dead on arrival)

## Next Step

Once both accounts are funded with test amounts and API keys are in the
vault, say "keys ready" and we'll run the $100 live test trades.
