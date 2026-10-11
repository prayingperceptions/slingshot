"""Base market data via Dexscreener public API (no key needed).

Used for meme-token discovery and rug-score inputs: liquidity, volume,
holder concentration proxy, pair age.
"""
import json
import urllib.request
import urllib.error

DEXSCREENER_TOKENS = "https://api.dexscreener.com/tokens/v1/base/"


def fetch_token_pairs(address: str, timeout: int = 10) -> list[dict]:
    try:
        with urllib.request.urlopen(DEXSCREENER_TOKENS + address, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return []


def summarize_pair(pair: dict) -> dict:
    liq = (pair.get("liquidity") or {}).get("usd") or 0
    vol = (pair.get("volume") or {}).get("h24") or 0
    txns = (pair.get("txns") or {}).get("h24") or {}
    return {
        "dex": pair.get("dexId"),
        "pair_address": pair.get("pairAddress"),
        "base_symbol": (pair.get("baseToken") or {}).get("symbol"),
        "liquidity_usd": liq,
        "volume_24h": vol,
        "buys_24h": txns.get("buys", 0),
        "sells_24h": txns.get("sells", 0),
        "price_usd": pair.get("priceUsd"),
        "fdv": pair.get("fdv"),
        "created_at": pair.get("pairCreatedAt"),
        "url": pair.get("url"),
    }


def best_pair(address: str) -> dict | None:
    """Highest-liquidity pair for a token, or None if unreachable."""
    pairs = fetch_token_pairs(address)
    if not pairs:
        return None
    top = max(pairs, key=lambda p: (p.get("liquidity") or {}).get("usd") or 0)
    return summarize_pair(top)
