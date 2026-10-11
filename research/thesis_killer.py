"""Thesis killer: three strategies tested against real data, honestly.

Thesis 1: Hedged funding arb (see fund_backtest.py) -> DEAD
Thesis 2: Contrarian directional (short crowded longs) -> DEAD
Thesis 3: Basis mean-reversion -> DEAD at retail costs; CONDITIONAL at <20bps

This script reproduces theses 2 and 3 (thesis 1 is fund_backtest.py).
The honest versions include execution delay and persistence requirements
to kill lookahead bias and bad-print artifacts.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fund_backtest import load_coin, COINS, HOURS_PER_YEAR

NOTIONAL = 25_000.0


def thesis2_contrarian(enter_th=100.0, exit_th=20.0, stop_pct=5.0,
                       cost_bps=8.0):
    """Short extreme positive funding. Collect funding, fade the crowd."""
    universe = {c: load_coin(c) for c in COINS}
    trades = []
    for coin, rows in universe.items():
        pos = None
        for r in rows:
            fann = r["f1h"] * HOURS_PER_YEAR * 100
            if pos is None:
                if fann >= enter_th:
                    pos = {"entry": r["perp"], "h": 0, "fund": 0.0}
            else:
                pos["fund"] += NOTIONAL * r["f1h"]
                pos["h"] += 1
                pnl_pct = (pos["entry"] - r["perp"]) / pos["entry"]
                if pnl_pct <= -stop_pct / 100 or fann < exit_th or pos["h"] >= 168:
                    net = (NOTIONAL * pnl_pct + pos["fund"]
                           - NOTIONAL * cost_bps / 1e4)
                    trades.append(net)
                    pos = None
    tot = sum(trades)
    return {"n": len(trades), "net": tot,
            "win": sum(1 for t in trades if t > 0) / len(trades) if trades else 0}


def thesis3_basis(enter_bps=30.0, exit_bps=10.0, cost_bps=30.0,
                  persist_h=2):
    """Basis mean-reversion with persistence + execution delay (honest)."""
    universe = {c: load_coin(c) for c in COINS}
    trades = []
    for coin, rows in universe.items():
        pos, pending = None, 0
        for i, r in enumerate(rows):
            b = (r["perp"] - r["spot"]) / r["spot"]
            bps = abs(b) * 1e4
            if pos is None:
                pending = pending + 1 if bps >= enter_bps else 0
                if pending >= persist_h and i + 1 < len(rows):
                    r2 = rows[i + 1]
                    b2 = (r2["perp"] - r2["spot"]) / r2["spot"]
                    pos = {"b_in": b2, "h": 0, "short_perp": b2 > 0}
                    pending = 0
            else:
                pos["h"] += 1
                pnl = (-(b - pos["b_in"]) if pos["short_perp"]
                       else (b - pos["b_in"])) * NOTIONAL
                if bps <= exit_bps or pos["h"] >= 48:
                    trades.append(pnl - NOTIONAL * cost_bps / 1e4)
                    pos = None
    tot = sum(trades)
    return {"n": len(trades), "net": tot,
            "win": sum(1 for t in trades if t > 0) / len(trades) if trades else 0}


def main():
    print("THESIS 2: contrarian directional (short extreme funding)")
    for eth in (80, 100, 150):
        s = thesis2_contrarian(enter_th=eth)
        print(f"  enter={eth}%: n={s['n']} net=${s['net']:+,.0f} win={s['win']:.0%}")
    print("\nTHESIS 3: basis mean-reversion (honest: 2h persist + 1h delay)")
    for cbps in (30, 20, 15, 10):
        s = thesis3_basis(cost_bps=cbps)
        print(f"  cost={cbps}bps: n={s['n']} net=${s['net']:+,.0f} win={s['win']:.0%}")
    print("\nVerdict: T2 dead at all params. "
          "T3 dead at retail costs, conditional below ~20bps.")


if __name__ == "__main__":
    main()
