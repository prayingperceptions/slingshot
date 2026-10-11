"""Parabolic profit-stash ladder.

When a position runs to a multiple of entry, peel profit into blue chips
instead of letting it ride to zero. Pure function: multiple in, allocation out.
"""


def stash_splits(multiple: float) -> dict:
    """Return {asset: frac_of_profit} for a given run multiple.

    Ladder per spec:
      2x  -> 25% of profit to USDC
      3x  -> 25% of profit split 50% USDC / 25% SOL / 25% ETH
      5x  -> 25% of profit split 40% BTC / 30% ETH / 20% SOL / 10% USDC
      8x+ -> trailing stop tightens to -15%, 25% of profit to blue chips
    """
    if multiple >= 8:
        return {"BTC": 0.10, "ETH": 0.075, "SOL": 0.05, "USDC": 0.025, "trailing_pct": 15}
    if multiple >= 5:
        return {"BTC": 0.10, "ETH": 0.075, "SOL": 0.05, "USDC": 0.025}
    if multiple >= 3:
        return {"USDC": 0.125, "SOL": 0.0625, "ETH": 0.0625}
    if multiple >= 2:
        return {"USDC": 0.25}
    return {}


def stash_amount(entry: float, current: float, size_usd: float) -> tuple[float, dict]:
    """Profit in USD and its stash allocation. (0, {}) if below 2x."""
    if entry <= 0:
        return 0.0, {}
    multiple = current / entry
    splits = stash_splits(multiple)
    if not splits:
        return 0.0, {}
    profit = (current - entry) / entry * size_usd
    alloc = {k: round(profit * v, 2) for k, v in splits.items() if k != "trailing_pct"}
    return round(profit, 2), alloc
