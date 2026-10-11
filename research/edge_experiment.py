"""Edge experiment: full trade lifecycles with simulated time.

Drives the Engine directly with a mocked clock (60s per tick) so time-based
guards (30-min decay, 60-min force) fire naturally. This is the honest test
of whether the strategy's entry edge survives its exit logic and costs.
"""
import sys, json, time, pathlib, random
sys.path.insert(0, str(pathlib.Path(__file__).parent / "src"))

from trader.config import load_config
from trader import risk
from trader.engine import Engine
from trader.jev.client import PaperJudge
from trader.loop import synthetic_feed

# --- mock clock: 60s per tick ---
_clock = [1_790_000_000]
_real_time = time.time
def fake_time():
    return _clock[0]
time.time = fake_time

def run_experiment(ticks=500, bankroll=50.0, seed=42):
    random.seed(seed)
    _clock[0] = 1_790_000_000
    risk._state.armed = False
    risk._state.tripped = False
    risk._state.trip_reason = ""
    risk._state.daily_pnl = 0
    cfg = load_config("config/default.toml")
    risk.arm()
    eng = Engine(cfg, PaperJudge(), bankroll)
    feed_state = {}
    reports = []
    for _ in range(ticks):
        _clock[0] += 60  # 1 minute per tick
        # day rollover check (mirrors loop.py)
        md = synthetic_feed(feed_state)
        r = eng.tick(md)
        reports.append(r)
    time.time = _real_time
    return eng, reports

def analyze(eng, reports):
    l = eng.broker.ledger()
    # close any open position at last mid for accounting
    fills = eng.broker.fills
    entries = [f for f in fills if f.action == "open"]
    closes = [f for f in fills if f.action in ("close", "close_partial")]
    print(f"bankroll: ${eng.broker.start_bankroll} -> ${l['bankroll']:.2f}")
    print(f"realized PnL: ${l['realized_pnl']:.2f} over {len(entries)} entries, {len(closes)} closes")
    print(f"open positions: {l['open_positions']}, max DD: {l['drawdown_pct']}%")
    from collections import Counter
    reasons = Counter()
    for r in reports:
        for a in r["actions"]:
            if "guard_exit" in a:
                reasons[a["guard_exit"].split("_")[0]] += 1
            if "stash" in a:
                reasons["stash_hit"] += 1
    print("exit/stash reasons:", dict(reasons))
    # per-trade PnL reconstruction from fills
    print(f"total fills: {len(fills)}")

if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 500
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 42
    eng, reports = run_experiment(n, seed=seed)
    analyze(eng, reports)
