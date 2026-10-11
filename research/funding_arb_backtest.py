"""The honest dude: hedged funding-rate arbitrage backtest on REAL data.

The REAL arb (not directional):
  - funding_ann >= ENTER  ->  SHORT perp + LONG spot (delta-neutral)
  - each hour in position -> collect funding = notional * funding_1h
      (positive funding: shorts receive; negative: shorts pay)
  - funding_ann < EXIT or max_hold hit -> close both legs

P&L per trade =
    funding_collected            <- the edge (real data)
  - entry_costs - exit_costs      <- 4 fills: 2 legs x (taker_fee + spread/2)
  + basis_pnl                    <- -(basis_exit - basis_entry) x notional

All fee assumptions are explicit parameters. Spot taker fee is swept because
it is THE deciding variable: 5bps (pro venue) vs 60bps (retail) changes
everything. Nothing is hidden.
"""
import json
import pathlib
import sys

DATA = pathlib.Path(__file__).parent / "data"

# ---- honest cost model (per fill, in bps of notional) ----
PERP_TAKER_BPS = 4.5      # Hyperliquid low-tier taker
PERP_SPREAD_BPS = 2.0     # typical BTC perp spread
SPOT_SPREAD_BPS = 1.0     # BTC spot spread
# spot taker swept: 5 / 25 / 60 bps

HOURS_PER_YEAR = 8760


def load(coin: str):
    funding = json.loads((DATA / f"{coin}_funding.json").read_text())
    perp = json.loads((DATA / f"{coin}_perp.json").read_text())
    spot = json.loads((DATA / f"{coin}_spot.json").read_text())
    # bucket to hour-start (seconds); forward-fill funding across gaps
    # (Hyperliquid only logs funding when it updates)
    fmap = {}
    for p in funding:
        h = (p["time"] // 3_600_000) * 3600
        fmap[h] = float(p["fundingRate"])  # per-hour rate
    pmap = {}
    for c in perp:
        h = (int(c["t"]) // 3_600_000) * 3600
        pmap[h] = float(c["c"])
    smap = {}
    for c in spot:
        h = (int(c[0]) // 3600) * 3600
        smap[h] = float(c[4])  # close
    hours = sorted(set(pmap) & set(smap))
    # forward-fill funding: last known rate persists
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


def backtest(rows, notional=10_000.0, enter=20.0, exit_th=5.0,
             max_hold=168, spot_taker_bps=5.0):
    """Returns (trades, summary). All $ on `notional` per trade."""
    entry_cost = notional * ((PERP_TAKER_BPS + PERP_SPREAD_BPS / 2) +
                             (spot_taker_bps + SPOT_SPREAD_BPS / 2)) / 1e4
    exit_cost = entry_cost  # symmetric
    trades = []
    pos = None  # dict(entry_h, perp_in, spot_in, funding_acc)
    for h, f1h, perp, spot in rows:
        fann = f1h * HOURS_PER_YEAR * 100
        basis = (perp - spot) / spot  # in fraction
        if pos is None:
            if fann >= enter:
                pos = {"entry_h": h, "perp_in": perp, "spot_in": spot,
                       "basis_in": basis, "funding_acc": 0.0, "hours": 0,
                       "fann_in": fann}
        else:
            # collect this hour's funding (short receives when positive)
            pos["funding_acc"] += notional * f1h
            pos["hours"] += 1
            if fann < exit_th or pos["hours"] >= max_hold:
                basis_pnl = -(basis - pos["basis_in"]) * notional
                net = (pos["funding_acc"] - entry_cost - exit_cost + basis_pnl)
                trades.append({
                    "entry_h": pos["entry_h"], "exit_h": h,
                    "hours": pos["hours"], "fann_in": pos["fann_in"],
                    "funding": pos["funding_acc"], "basis_pnl": basis_pnl,
                    "costs": entry_cost + exit_cost, "net": net,
                })
                pos = None
    # force-close any open position at the end (mark to market, pay exit)
    if pos:
        h, f1h, perp, spot = rows[-1]
        basis = (perp - spot) / spot
        basis_pnl = -(basis - pos["basis_in"]) * notional
        net = pos["funding_acc"] - entry_cost - exit_cost + basis_pnl
        trades.append({"entry_h": pos["entry_h"], "exit_h": h,
                       "hours": pos["hours"], "fann_in": pos["fann_in"],
                       "funding": pos["funding_acc"], "basis_pnl": basis_pnl,
                       "costs": entry_cost + exit_cost, "net": net,
                       "forced": True})
    tot_net = sum(t["net"] for t in trades)
    tot_funding = sum(t["funding"] for t in trades)
    tot_costs = sum(t["costs"] for t in trades)
    tot_basis = sum(t["basis_pnl"] for t in trades)
    wins = sum(1 for t in trades if t["net"] > 0)
    return trades, {
        "n": len(trades), "net": tot_net, "funding": tot_funding,
        "costs": tot_costs, "basis": tot_basis,
        "win_rate": wins / len(trades) if trades else 0,
        "avg_hours": sum(t["hours"] for t in trades) / len(trades) if trades else 0,
    }


def main():
    coin = sys.argv[1] if len(sys.argv) > 1 else "BTC"
    rows = load(coin)
    days = (rows[-1][0] - rows[0][0]) / 86400 if rows else 0
    print(f"{coin}: {len(rows)} aligned hours (~{days:.0f} days)")
    print(f"cost model: perp taker {PERP_TAKER_BPS}bps + {PERP_SPREAD_BPS}bps spread; "
          f"spot spread {SPOT_SPREAD_BPS}bps; spot taker swept")
    print()
    for spot_fee in (5.0, 25.0, 60.0):
        for enter, exit_th in ((20.0, 5.0), (30.0, 10.0), (10.0, 3.0)):
            _, s = backtest(rows, enter=enter, exit_th=exit_th,
                            spot_taker_bps=spot_fee)
            print(f"spot_fee={spot_fee:>4.0f}bps enter={enter:>4.0f}% exit={exit_th:>3.0f}%: "
                  f"trades={s['n']:>3} net=${s['net']:>+8.2f} "
                  f"(funding ${s['funding']:+.2f} costs ${s['costs']:.2f} "
                  f"basis ${s['basis']:+.2f}) win={s['win_rate']:.0%} "
                  f"avg_hold={s['avg_hours']:.0f}h")


if __name__ == "__main__":
    main()
