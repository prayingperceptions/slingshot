"""Paper broker: simulated fills, real accounting.

No network, no keys, no money. Records every fill so the paper soak
produces an auditable ledger.
"""
import time
from dataclasses import dataclass, field

from ..market import book_walk_fill, calc_pnl


@dataclass
class Fill:
    ts: int
    symbol: str
    side: str  # long | short
    size_usd: float
    price: float
    fee_usd: float
    action: str  # open | close | close_partial


@dataclass
class Position:
    symbol: str
    side: str
    size_usd: float
    entry_price: float
    peak_price: float
    opened_ts: int
    partial_taken: bool = False


class PaperBroker:
    def __init__(self, bankroll: float):
        self.start_bankroll = bankroll
        self.bankroll = bankroll
        self.positions: dict[str, Position] = {}
        self.fills: list[Fill] = []
        self.realized_pnl = 0.0

    def open(self, symbol: str, side: str, size_usd: float, mid: float,
             depth_2x: float, slippage_bps: float) -> tuple[bool, str]:
        if symbol in self.positions:
            return False, "already_open"
        ok, price = book_walk_fill(mid, size_usd, depth_2x, slippage_bps)
        if not ok:
            return False, "fill_rejected_depth_or_slippage"
        fee = price * (size_usd / price) * 5 / 10000  # 5bps
        self.positions[symbol] = Position(
            symbol=symbol, side=side, size_usd=size_usd,
            entry_price=price, peak_price=price, opened_ts=int(time.time()),
        )
        self.fills.append(Fill(int(time.time()), symbol, side, size_usd, price, fee, "open"))
        return True, f"opened_{side}_{size_usd:.2f}_at_{price:.4f}"

    def close(self, symbol: str, mid: float, frac: float = 1.0) -> tuple[bool, str]:
        pos = self.positions.get(symbol)
        if not pos:
            return False, "no_position"
        close_usd = pos.size_usd * frac
        qty = close_usd / pos.entry_price
        pnl = calc_pnl(pos.entry_price, mid, qty, pos.side)
        fee = mid * qty * 5 / 10000
        net = pnl - fee
        self.realized_pnl += net
        self.bankroll += net
        self.fills.append(Fill(int(time.time()), symbol, pos.side, close_usd, mid, fee,
                               "close" if frac >= 1.0 else "close_partial"))
        if frac >= 1.0:
            del self.positions[symbol]
        else:
            pos.size_usd -= close_usd
            pos.partial_taken = True
        return True, f"closed_{frac*100:.0f}pct_pnl_{net:+.2f}"

    def unrealized(self, symbol: str, mid: float) -> float:
        pos = self.positions.get(symbol)
        if not pos:
            return 0.0
        qty = pos.size_usd / pos.entry_price
        return calc_pnl(pos.entry_price, mid, qty, pos.side)

    def update_peak(self, symbol: str, mid: float):
        pos = self.positions.get(symbol)
        if pos and mid > pos.peak_price:
            pos.peak_price = mid

    def drawdown_pct(self) -> float:
        peak = max(self.start_bankroll, self.bankroll)
        return (peak - self.bankroll) / peak * 100 if peak else 0.0

    def ledger(self) -> dict:
        return {
            "bankroll": round(self.bankroll, 2),
            "realized_pnl": round(self.realized_pnl, 2),
            "open_positions": len(self.positions),
            "fills": len(self.fills),
            "drawdown_pct": round(self.drawdown_pct(), 2),
        }
