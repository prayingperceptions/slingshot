"""Main loop: tick the engine on an interval until stopped.

Feeds:
  synthetic — random-walk market for soak testing (no network)
  base      — live Dexscreener data for a watched Base token (read-only)

Kill file (/tmp/slingshot_kill) is checked by the risk layer every tick.
"""
import json
import pathlib
import random
import time
import signal

from .config import load_config
from . import risk
from .engine import Engine
from .jev.client import PaperJudge
from .execution import base as base_feed

_running = True


def _stop(signum, frame):
    global _running
    _running = False


def synthetic_feed(state: dict) -> dict:
    """Random-walk BTC-perp-like market. Deterministic-ish for soak tests.

    ~5% of ticks are 'hot': real funding + basis + spread edge, so the
    95-pathway genuinely fires and the execution path gets exercised.
    """
    price = state.get("price", 67400.0)
    drift = random.gauss(0, 25)
    hot = random.random() < 0.05
    funding_8h = 0.0006 if hot else 0.0001
    basis_mult = 1.008 if hot else 1.0008
    spread_mult = 0.0035 if hot else 0.0001
    price = max(1000.0, price + drift)
    state["price"] = price
    closes = state.setdefault("closes", [price] * 60)
    closes.append(price)
    del closes[:-60]
    spread = price * spread_mult
    return {
        "bid": price - spread / 2,
        "ask": price + spread / 2,
        "bid_vol": random.uniform(0.5, 2.0),
        "ask_vol": random.uniform(0.5, 2.0),
        "closes_1h": list(closes),
        "funding_8h": funding_8h,
        "perp_price": price * basis_mult,
        "spot_price": price,
        "liq_depth_2x": 50000.0,
        "rug_score": 97,
        "top10_pct": 8.0,
        "slippage_bps": 4.0,
        "vol_24h": 900000.0,
        "liq_usd": 400000.0,
        "rsi": random.uniform(40, 70),
        "sentiment": 0.0,
    }


def base_feed_tick(address: str, state: dict) -> dict:
    """Live read-only market data for a Base token. No orders placed."""
    pair = base_feed.best_pair(address)
    if not pair or not pair["liquidity_usd"]:
        if not state.get("feed_warned"):
            print("WARN: base feed unreachable, falling back to synthetic")
            state["feed_warned"] = True
        return synthetic_feed(state)  # fall back rather than stall
    state["feed_warned"] = False
    price = float(pair["price_usd"] or 0) or 1.0
    spread = price * 0.003
    return {
        "bid": price - spread / 2,
        "ask": price + spread / 2,
        "bid_vol": 1.0, "ask_vol": 1.0,
        "closes_1h": [price],
        "funding_8h": 0.0,
        "perp_price": price, "spot_price": price,
        "liq_depth_2x": pair["liquidity_usd"] * 0.1,
        "rug_score": 90,
        "top10_pct": 15.0,
        "slippage_bps": 30.0,
        "vol_24h": pair["volume_24h"],
        "liq_usd": pair["liquidity_usd"],
        "vol_ref": pair["volume_24h"],
        "rsi": 50.0,
        "sentiment": 0.0,
    }


def hyperliquid_feed_tick(symbol: str, state: dict) -> dict:
    """Real Hyperliquid perp data (public API, read-only). Falls back to
    synthetic on outage, with a warning."""
    from .execution import hyperliquid as hl
    try:
        md = hl.fetch_perp_snapshot(symbol)
        state["feed_warned"] = False
        return md
    except Exception as e:
        if not state.get("feed_warned"):
            print(f"WARN: hyperliquid feed failed ({e}), falling back to synthetic")
            state["feed_warned"] = True
        return synthetic_feed(state)


def run(feed: str = "synthetic", address: str | None = None,
        interval: int = 5, max_ticks: int | None = None,
        bankroll: float = 50.0, log_path: str = "state/ticks.jsonl",
        symbol: str = "BTC"):
    global _running
    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    config = load_config()
    if config.run_mode != "paper":
        raise SystemExit(f"loop refuses non-paper mode (config: {config.run_mode})")
    risk.arm()
    engine = Engine(config, PaperJudge(), bankroll)
    if address:
        engine.symbol = address[:12]

    feed_state: dict = {}
    print(f"slingshot loop starting: feed={feed} bankroll=${bankroll:.2f} mode=paper")
    print("kill file:", config.risk.kill_file, "(touch it to flatten)")

    n = 0
    errors = 0
    current_day = time.strftime("%Y-%m-%d")
    log_p = pathlib.Path(log_path)
    with open(log_p, "a") as log:
        while _running:
            # day rollover: reset daily PnL / daily-loss trips
            today = time.strftime("%Y-%m-%d")
            if today != current_day:
                risk.reset_daily()
                print(f"day rollover {current_day} -> {today}: daily PnL reset")
                current_day = today
            # log rotation at ~50MB to bound disk in 24/7 operation
            if log_p.stat().st_size > 50 * 1024 * 1024:
                rotated = log_p.with_suffix(f".{current_day}.jsonl")
                log.close()
                log_p.rename(rotated)
                log = open(log_p, "a")
                print(f"log rotated -> {rotated.name}")
            try:
                if feed == "hyperliquid":
                    md = hyperliquid_feed_tick(symbol, feed_state)
                    engine.symbol = f"{symbol}-PERP"
                elif feed == "base" and address:
                    md = base_feed_tick(address, feed_state)
                else:
                    md = synthetic_feed(feed_state)
                report = engine.tick(md)
            except Exception as e:
                errors += 1
                print(f"tick error {errors}/10: {type(e).__name__}: {e}")
                if errors >= 10:
                    print("10 consecutive tick errors — stopping safely")
                    break
                time.sleep(interval)
                continue
            errors = 0
            log.write(json.dumps(report) + "\n")
            log.flush()
            n += 1
            if n % 20 == 0:
                l = report["ledger"]
                print(f"tick {n}: bankroll=${l['bankroll']} pnl=${l['realized_pnl']} "
                      f"open={l['open_positions']} dd={l['drawdown_pct']}%")
            if max_ticks and n >= max_ticks:
                break
            time.sleep(interval)

    print(f"stopped after {n} ticks. ledger:", engine.broker.ledger())
