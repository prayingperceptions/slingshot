def calc_pnl(entry: float, exit: float, size: float, side: str, fee_bps: float = 5) -> float:
    gross = (exit - entry) * size if side == "long" else (entry - exit) * size
    fees = (entry + exit) * size * fee_bps / 10000
    return gross - fees

def book_walk_fill(mid: float, size: float, depth_2x: float, slippage_bps: float) -> tuple[bool, float]:
    # fail if depth <2x size or slippage >10bps
    if depth_2x < size * 2:
        return False, 0
    if slippage_bps > 10:
        return False, 0
    fill_price = mid * (1 + slippage_bps/10000)
    return True, fill_price
