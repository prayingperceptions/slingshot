"""Spike lifecycle analyzer: the fundamental question for funding arb.

When funding spikes above a threshold, how long does it stay elevated and
how much funding can actually be harvested? This measures the raw material
of the strategy — before costs, before execution.
"""
import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))

from fund_backtest import load_coin, COINS, HOURS_PER_YEAR


def analyze(threshold=50.0, floor=20.0, notional=25_000.0):
    spikes = []
    for coin in COINS:
        rows = load_coin(coin)
        i = 0
        while i < len(rows):
            fann = abs(rows[i]["f1h"]) * HOURS_PER_YEAR * 100
            if fann >= threshold:
                start, peak, j = i, fann, i
                while j < len(rows) and abs(rows[j]["f1h"]) * HOURS_PER_YEAR * 100 >= floor:
                    peak = max(peak, abs(rows[j]["f1h"]) * HOURS_PER_YEAR * 100)
                    j += 1
                tot_f = sum(abs(rows[k]["f1h"]) for k in range(start, j))
                spikes.append({"coin": coin, "peak": peak,
                               "dur_h": j - start, "funding_usd": tot_f * notional})
                i = j
            else:
                i += 1
    return spikes


def main():
    spikes = analyze()
    n = len(spikes)
    print(f"{n} spikes >=50% across {len(COINS)} coins / 21 days\n")
    for label, key in (("duration above 20% (h)", "dur_h"),
                       ("harvestable funding on $25k", "funding_usd"),
                       ("peak funding %", "peak")):
        vals = sorted(s[key] for s in spikes)
        print(f"{label}:")
        print(f"  min={vals[0]:.1f}  p25={vals[n//4]:.1f}  "
              f"median={vals[n//2]:.1f}  p75={vals[3*n//4]:.1f}  max={vals[-1]:.1f}")
    for cost in (75.0, 37.5, 20.0):
        k = sum(1 for s in spikes if s["funding_usd"] > cost)
        print(f"\nspikes covering ${cost:.0f} round-trip: {k}/{n} ({k/n:.1%})")


if __name__ == "__main__":
    main()
