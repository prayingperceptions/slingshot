"""Fetch and cache real market data for the honest funding-arb backtest.

Simple and robust: one funding window per coin (Hyperliquid caps at 500
hourly points ~ 21 days), perp candles + Coinbase spot candles for the same
span. All public APIs, no keys.

Writes research/data/{BTC,ETH}_{funding,perp,spot}.json
"""
import json
import pathlib
import sys
import time
import urllib.request

HL = "https://api.hyperliquid.xyz/info"
OUT = pathlib.Path(__file__).parent / "data"
OUT.mkdir(parents=True, exist_ok=True)


def hl_post(payload: dict, timeout: int = 30):
    req = urllib.request.Request(
        HL, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def fetch(coin: str, product: str):
    now_ms = int(time.time() * 1000)
    start_ms = now_ms - 25 * 24 * 3600 * 1000  # recent window; API caps at 500 pts
    print(f"[{coin}] funding...", flush=True)
    funding = hl_post({"type": "fundingHistory", "coin": coin,
                       "startTime": start_ms, "endTime": now_ms})
    f_times = [p["time"] for p in funding]
    start_ms, end_ms = min(f_times), max(f_times)
    print(f"[{coin}] {len(funding)} funding pts, "
          f"{(end_ms - start_ms) / 3.6e6:.0f}h span", flush=True)

    print(f"[{coin}] perp candles...", flush=True)
    perp = hl_post({"type": "candleSnapshot", "req": {
        "coin": coin, "interval": "1h",
        "startTime": start_ms, "endTime": end_ms}})
    print(f"[{coin}] {len(perp)} perp candles", flush=True)

    print(f"[{coin}] spot candles (Coinbase, windowed)...", flush=True)
    spot = []
    start_s, end_s = start_ms // 1000, end_ms // 1000
    # walk backwards in 300h windows using explicit start+end (Coinbase paging
    # with end-only was returning the same window)
    win_end = end_s
    for _ in range(10):
        win_start = max(start_s, win_end - 300 * 3600)
        iso = lambda s: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(s))
        url = (f"https://api.exchange.coinbase.com/products/{product}/candles"
               f"?granularity=3600&start={iso(win_start)}&end={iso(win_end)}")
        req = urllib.request.Request(url, headers={"User-Agent": "slingshot-research"})
        with urllib.request.urlopen(req, timeout=30) as r:
            batch = json.loads(r.read().decode())
        spot.extend(batch)
        if win_start <= start_s or not batch:
            break
        win_end = win_start - 1
        time.sleep(0.4)
    spot = [c for c in spot if start_s <= c[0] <= end_s]
    spot.sort(key=lambda c: c[0])
    # dedupe by timestamp
    seen, uniq = set(), []
    for c in spot:
        if c[0] not in seen:
            seen.add(c[0])
            uniq.append(c)
    spot = uniq
    print(f"[{coin}] {len(spot)} spot candles", flush=True)

    (OUT / f"{coin}_funding.json").write_text(json.dumps(funding))
    (OUT / f"{coin}_perp.json").write_text(json.dumps(perp))
    (OUT / f"{coin}_spot.json").write_text(json.dumps(spot))
    print(f"[{coin}] cached", flush=True)


if __name__ == "__main__":
    for coin, product in (("BTC", "BTC-USD"), ("ETH", "ETH-USD")):
        fetch(coin, product)
    print("done ->", OUT)
