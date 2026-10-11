"""Real market data feed: Hyperliquid public API (no key required).

Fetches live perp mark prices + funding rates for BTC/ETH, and spot prices
for basis computation. Read-only. If unreachable, raises — the loop decides
whether to fall back.
"""
import json
import urllib.request

HL_URL = "https://api.hyperliquid.xyz/info"


def _post(payload: dict, timeout: int = 10) -> dict | list:
    req = urllib.request.Request(
        HL_URL,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def fetch_perp_snapshot(symbol: str = "BTC", spot_override: float | None = None) -> dict:
    """Return a market-data dict ready for Engine.tick, with REAL funding/basis."""
    meta, ctxs = _post({"type": "metaAndAssetCtxs"})
    target = None
    for m, c in zip(meta["universe"], ctxs):
        if m["name"] == symbol:
            target = (m, c)
            break
    if not target:
        raise RuntimeError(f"{symbol} not found in Hyperliquid universe")
    m, c = target

    mark = float(c["markPx"])
    funding_1h = float(c["funding"])  # per-hour rate
    # spot: use Coinbase public API as the spot leg
    if spot_override is not None:
        spot = spot_override
    else:
        with urllib.request.urlopen(
            f"https://api.coinbase.com/v2/prices/{symbol}-USD/spot", timeout=10
        ) as r:
            spot = float(json.loads(r.read().decode())["data"]["amount"])

    spread = mark * 0.0002  # ~2bps typical BTC perp spread
    return {
        "bid": mark - spread / 2,
        "ask": mark + spread / 2,
        "bid_vol": 10.0,
        "ask_vol": 10.0,
        "closes_1h": [mark],  # single point; rv understated — noted in report
        "funding_8h": funding_1h * 8,  # convert hourly -> 8h for the snapshot math
        "perp_price": mark,
        "spot_price": spot,
        "liq_depth_2x": 1_000_000.0,  # deep BTC book
        "rug_score": 100,  # BTC/ETH are not meme rugs; neutral for perps arb
        "top10_pct": 5.0,
        "slippage_bps": 2.0,
        "vol_24h": float(c.get("dayNtlVlm") or 0),
        "liq_usd": 50_000_000.0,
        "rsi": 50.0,
        "sentiment": 0.0,
        "symbol": symbol,
        "funding_1h_raw": funding_1h,
    }


def funding_annualized_pct(funding_1h: float) -> float:
    return funding_1h * 24 * 365 * 100
