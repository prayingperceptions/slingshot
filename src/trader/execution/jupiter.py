"""Jupiter Ultra execution client.

Paper mode (default): simulated quotes off mid + book-walk fills.
Live mode: NOT IMPLEMENTED — requires explicit build-out against the
Ultra API with real keys, which this repo does not do.
"""
from ..market import book_walk_fill


class JupiterClient:
    ULTRA_URL = "https://ultra.jup.ag"

    def __init__(self, mode: str = "paper", api_key: str | None = None):
        self.mode = mode
        self.api_key = api_key

    def quote(self, input_mint: str, output_mint: str, amount_usd: float,
              mid: float, depth_2x: float, slippage_bps: float) -> dict:
        """Return a fill-or-reject quote. Paper: simulated. Live: refused."""
        if self.mode != "paper":
            raise RuntimeError(
                "Jupiter live execution is not implemented. "
                "Paper mode only."
            )
        ok, price = book_walk_fill(mid, amount_usd, depth_2x, slippage_bps)
        return {
            "ok": ok,
            "price": price,
            "reason": "ok" if ok else "depth_or_slippage_reject",
            "route": "paper-simulated",
        }
