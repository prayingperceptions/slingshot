"""Parabolic guard: trailing stops, time decay, momentum exhaustion, funding flips.

- trailing -20% from peak -> exit 50% (tightens to -15% at 8x+)
- 30min with no new high -> decay exit 50%
- 60min force -> exit 100%
- RSI > 85 with volume down 50% -> exit 100%
- perps funding flip to <= -7% annualized -> exit perps 100%
"""
import time


def check(position, mid: float, rsi: float | None = None,
          vol_now: float | None = None, vol_ref: float | None = None,
          funding_ann: float | None = None, now: int | None = None) -> tuple[str, float, str]:
    now = now or int(time.time())
    age_min = (now - position.opened_ts) / 60

    # Funding flip kills perps positions immediately
    if funding_ann is not None and funding_ann <= -7.0:
        return ("exit_frac", 1.0, f"funding_flip_{funding_ann:.1f}%")

    # Trailing stop from peak (-20%, -15% at 8x+)
    multiple = mid / position.entry_price if position.entry_price else 1.0
    trail_pct = 15 if multiple >= 8 else 20
    dd_from_peak = (position.peak_price - mid) / position.peak_price * 100 if position.peak_price else 0
    if dd_from_peak >= trail_pct:
        return ("exit_frac", 0.50, f"trailing_-{trail_pct}%_from_peak")

    # Momentum exhaustion: overbought + volume collapse
    if rsi is not None and rsi > 85 and vol_now is not None and vol_ref:
        if vol_now <= vol_ref * 0.5:
            return ("exit_frac", 1.0, f"rsi_{rsi:.0f}_vol_collapse")

    # Time decay
    if age_min >= 60:
        return ("exit_frac", 1.0, f"force_exit_{age_min:.0f}min")
    if age_min >= 30 and mid <= position.peak_price:
        return ("exit_frac", 0.50, f"no_new_high_{age_min:.0f}min")

    return ("hold", 0.0, "parabolic_ok")
