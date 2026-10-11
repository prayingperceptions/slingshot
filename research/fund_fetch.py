"""Fund data pipeline: historical funding + perp + spot for the alt universe.

Coins: high-|funding| alts with Coinbase spot markets.
Writes research/data/fund/{COIN}_{funding,perp,spot}.json
"""
import json
import pathlib
import time
import urllib.request

HL = "https://api.hyperliquid.xyz/info"
OUT = pathlib.Path(__file__).parent / "data" / "fund"
OUT.mkdir(parents=True, exist_ok=True)

# (hyperliquid perp coin, coinbase product)
UNIVERSE = [
    ("MET", "MET-USD"),
    ("MINA", "MINA-USD"),
    ("S", "S-USD"),
    ("STRK", "STRK-USD"),
    ("USELESS", "USELESS-USD"),
    ("PENGU", "PENGU-USD"),
    ("GRASS", "GRASS-USD"),
    ("NEAR", "NEAR-USD"),
    ("FARTCOIN", "FARTCOIN-USD"),
    ("ALGO", "ALGO-USD"),
    ("ONDO", "ONDO-USD"),
    ("AZTEC", "AZTEC-USD"),
]


def hl_post(payload: dict, timeout: int = 30):
    req = urllib.request.Request(
        HL, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def spot_window(product: str, start_s: int, end_s: int) -> list:
    iso = lambda s: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(s))
    out, win_end = [], end_s
    for _ in range(4):
        win_start = max(start_s, win_end - 300 * 3600)
        url = (f"https://api.exchange.coinbase.com/products/{product}/candles"
               f"?granularity=3600&start={iso(win_start)}&end={iso(win_end)}")
        req = urllib.request.Request(url, headers={"User-Agent": "slingshot-fund"})
        with urllib.request.urlopen(req, timeout=30) as r:
            batch = json.loads(r.read().decode())
        out.extend(batch)
        if win_start <= start_s or not batch:
            break
        win_end = win_start - 1
        time.sleep(0.4)
    out = [c for c in out if start_s <= c[0] <= end_s]
    out.sort(key=lambda c: c[0])
    seen, uniq = set(), []
    for c in out:
        if c[0] not in seen:
            seen.add(c[0])
            uniq.append(c)
    return uniq


def fetch(coin: str, product: str):
    now_ms = int(time.time() * 1000)
    start_ms = now_ms - 25 * 24 * 3600 * 1000
    funding = hl_post({"type": "fundingHistory", "coin": coin,
                       "startTime": start_ms, "endTime": now_ms})
    f_times = [p["time"] for p in funding]
    s_ms, e_ms = min(f_times), max(f_times)
    perp = hl_post({"type": "candleSnapshot", "req": {
        "coin": coin, "interval": "1h", "startTime": s_ms, "endTime": e_ms}})
    spot = spot_window(product, s_ms // 1000, e_ms // 1000)
    (OUT / f"{coin}_funding.json").write_text(json.dumps(funding))
    (OUT / f"{coin}_perp.json").write_text(json.dumps(perp))
    (OUT / f"{coin}_spot.json").write_text(json.dumps(spot))
    print(f"[{coin}] funding={len(funding)} perp={len(perp)} spot={len(spot)}",
          flush=True)


if __name__ == "__main__":
    for coin, product in UNIVERSE:
        try:
            fetch(coin, product)
        except Exception as e:
            print(f"[{coin}] FAILED: {e}", flush=True)
    print("done ->", OUT)
