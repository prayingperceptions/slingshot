"""Production validation: replay 111 days through the live signal logic.

Feeds historical data through the SAME signal/exit logic as the production
fund engine, proving the research backtest and production code agree.
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "src"))

from fund.double_edge import (
    ENTER_BASIS_BPS, ENTER_FUND_PCT, EXIT_BASIS_BPS, EXIT_FUND_PCT,
    PERSIST_HOURS, MAX_HOLD_H, NOTIONAL_PER_POSITION,
)

HOURS_PER_YEAR = 8760

DATA = pathlib.Path(__file__).parent / "data" / "fund_ext"
COINS = ["MET", "MINA", "S", "STRK", "USELESS", "PENGU", "GRASS",
         "NEAR", "FARTCOIN", "ALGO", "ONDO", "AZTEC"]

COST_BPS = 14.0  # production cost model


def load(coin):
    funding = json.loads((DATA / f"{coin}_funding.json").read_text())
    perp = json.loads((DATA / f"{coin}_perp.json").read_text())
    spot = json.loads((DATA / f"{coin}_spot.json").read_text())
    fmap = {(p["time"] // 3_600_000) * 3600: float(p["fundingRate"]) for p in funding}
    pmap = {(int(c["t"]) // 3_600_000) * 3600: float(c["c"]) for c in perp}
    smap = {(int(c[0]) // 3600) * 3600: float(c[4]) for c in spot}
    hours = sorted(set(pmap) & set(smap))
    fevents = sorted(fmap.items())
    rows, fi, last_f = [], 0, None
    for h in hours:
        while fi < len(fevents) and fevents[fi][0] <= h:
            last_f = fevents[fi][1]
            fi += 1
        if last_f is None:
            continue
        rows.append((h, last_f, pmap[h], smap[h]))
    return rows


def main():
    universe = {c: load(c) for c in COINS if (DATA / f"{c}_funding.json").exists()}
    trades = []
    for coin, rows in universe.items():
        pos, pending = None, 0
        for i, (h, f1h, perp, spot) in enumerate(rows):
            b = (perp - spot) / spot
            bps = abs(b) * 1e4
            fann = f1h * HOURS_PER_YEAR * 100
            aligned = (b > 0) == (fann > 0)
            if pos is None:
                if bps >= ENTER_BASIS_BPS and abs(fann) >= ENTER_FUND_PCT and aligned:
                    pending += 1
                else:
                    pending = 0
                if pending >= PERSIST_HOURS and i + 1 < len(rows):
                    _, f2, p2, s2 = rows[i + 1]
                    b2 = (p2 - s2) / s2
                    pos = {"b_in": b2, "hrs": 0, "sp": b2 > 0, "f": 0.0}
                    pending = 0
            else:
                pos["hrs"] += 1
                pos["f"] += NOTIONAL_PER_POSITION * abs(f1h)
                pnl = (-(b - pos["b_in"]) if pos["sp"] else (b - pos["b_in"]))
                pnl *= NOTIONAL_PER_POSITION
                if bps <= EXIT_BASIS_BPS or abs(fann) < EXIT_FUND_PCT or pos["hrs"] >= MAX_HOLD_H:
                    net = pnl + pos["f"] - NOTIONAL_PER_POSITION * COST_BPS / 1e4
                    trades.append(net)
                    pos = None
    n = len(trades)
    tot = sum(trades)
    wins = sum(1 for t in trades if t > 0)
    print(f"PRODUCTION REPLAY (111d, {COST_BPS}bps costs):")
    print(f"  trades={n} net=${tot:+,.0f} win={wins/n:.0%} avg=${tot/n:+,.0f}")
    print(f"  on $500k: {tot/5000:+.2f}% over 111d (~{tot/5000*365/111:+.1f}% ann)")


if __name__ == "__main__":
    main()
