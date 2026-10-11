"""Liquidity guard: 30% liquidity drop exits 50%. Depth must stay >= 2x size."""


def check(liq_now: float, liq_ref: float, position_usd: float) -> tuple[str, float, str]:
    if liq_ref <= 0:
        return ("hold", 0.0, "no_reference_liq")
    drop_pct = (liq_ref - liq_now) / liq_ref * 100
    if drop_pct >= 30:
        return ("exit_frac", 0.50, f"liq_drop_{drop_pct:.1f}%")
    if liq_now < position_usd * 2:
        return ("exit_frac", 1.0, "depth_below_2x_size_flatten")
    return ("hold", 0.0, "liq_ok")
