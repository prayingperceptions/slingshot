"""Velocity reinvest ladder — capital rules, hard-coded.

- $0–$500:    100% reinvest
- $500–$2K:   70% reinvest / 30% stash
- $2K–$10K:   50% / 50%
- $10K+:      30% / 70%
Withdraw anytime, min bankroll $500.
"""


def reinvest_split(bankroll: float) -> dict:
    """Return {reinvest_frac, stash_frac} for a bankroll level."""
    if bankroll < 500:
        return {"reinvest_frac": 1.0, "stash_frac": 0.0}
    if bankroll < 2000:
        return {"reinvest_frac": 0.70, "stash_frac": 0.30}
    if bankroll < 10000:
        return {"reinvest_frac": 0.50, "stash_frac": 0.50}
    return {"reinvest_frac": 0.30, "stash_frac": 0.70}


def tradable_bankroll(bankroll: float, min_bankroll: float = 500.0) -> float:
    """Capital available for new positions.

    min_bankroll is a WITHDRAWAL floor, not a trading gate — the $0-$500
    phase is 100% reinvest by design. Never returns 0 for positive bankroll.
    """
    if bankroll <= 0:
        return 0.0
    split = reinvest_split(bankroll)
    return bankroll * split["reinvest_frac"]
