"""Whale guard: a single wallet holding >1% of supply moving against you
exits 50% of the position. Pure function.
"""


def check(top_holder_pct: float, whale_sold_usd: float = 0.0) -> tuple[str, float, str]:
    """Return (action, exit_frac, reason)."""
    if top_holder_pct > 1.0 or whale_sold_usd > 0:
        return ("exit_frac", 0.50, f"whale_top_{top_holder_pct:.2f}%")
    return ("hold", 0.0, "no_whale")
