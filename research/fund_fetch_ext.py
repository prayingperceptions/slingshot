"""Extended fund data: ~80 days for robust backtesting.

Pages funding history backwards (500 pts/window), fetches perp candles
and spot candles for the full span.
"""
import json
import pathlib
import time
import urllib.request

HL = "https://api.hyperliquid.xyz/info"
OUT = pathlib.Path(__file__).parent / "data" / "fund_ext"
OUT.mkdir(parents=True, exist_ok=True)

UNIVERSE = [
    ("MET", "MET-USD"), ("MINA", "MINA-USD"), ("S", "S-USD"),
    ("STRK", "STRK-USD"), ("USELESS", "USELESS-USD"), ("PENGU", "PENGU-USD"),
    ("GRASS", "GRASS-USD"), ("NEAR", "NEAR-USD"), ("FARTCOIN", "FARTCOIN-USD"),
    ("ALGO", "ALGO-USD"), ("ONDO", "ONDO-USD"), ("AZTEC", "AZTEC-USD"),
]


def hl_post(payload: dict, timeout: int = 30):
    req = urllib.request.Request(
        HL, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def fetch_funding_ext(coin: str, windows: int = 4):
    all_pts, seen = [], set()
    end = int(time.time() * 1000)
    for _ in range(windows):
        start = end - 30 * 24 * 3600 * 1000
        batch = hl_post({"type": "fundingHistory", "coin": coin,
                         "startTime": start, "endTime": end})
        new = [p for p in batch if p["time"] not in seen]
        if not new:
            break
        for p in new:
            seen.add(p["time"])
        all_pts.extend(new)
        end = min(p["time"] for p in new) - 1
        time.sleep(0.4)
    all_pts.sort(key=lambda p: p["time"])
    return all_pts


def fetch(coin: str, product: str):
    funding = fetch_funding_ext(coin)
    if not funding:
        print(f"[{coin}] no funding", flush=True)
        return
    s_ms = min(p["time"] for p in funding)
    e_ms = max(p["time"] for p in funding)
    perp = hl_post({"type": "candleSnapshot", "req": {
        "coin": coin, "interval": "1h", "startTime": s_ms, "endTime": e_ms}})
    # spot in 300h windows
    spot, win_end = [], e_ms // 1000
    start_s = s_ms // 1000
    iso = lambda s: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(s))
    for _ in range(10):
        win_start = max(start_s, win_end - 300 * 3600)
        url = (f"https://api.exchange.coinbase.com/products/{product}/candles"
               f"?granularity=3600&start={iso(win_start)}&end={iso(win_end)}")
        req = urllib.request.Request(url, headers={"User-Agent": "slingshot-fund"})
        with urllib.request.urlopen(req, timeout=30) as r:
            batch = json.loads(r.read().decode())
        spot.extend(batch)
        if win_start <= start_s or not batch:
            break
        win_end = win_start - 1
        time.sleep(0.4)
    spot = [c for c in spot if start_s <= c[0] <= e_ms // 1000]
    spot.sort(key=lambda c: c[0])
    seen, uniq = set(), []
    for c in spot:
        if c[0] not in seen:
            seen.add(c[0])
            uniq.append(c)
    (OUT / f"{coin}_funding.json").write_text(json.dumps(funding))
    (OUT / f"{coin}_perp.json").write_text(json.dumps(perp))
    (OUT / f"{coin}_spot.json").write_text(json.dumps(uniq))
    span_h = (e_ms - s_ms) / 3600000
    print(f"[{coin}] funding={len(funding)} perp={len(perp)} spot={len(uniq)} "
          f"span={span_h:.0f}h", flush=True)


if __name__ == "__main__":
    for coin, product in UNIVERSE:
        try:
            fetch(coin, product)
        except Exception as e:
            print(f"[{coin}] FAILED: {e}", flush=True)
    print("done ->", OUT)
