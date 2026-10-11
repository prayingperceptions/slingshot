from .jev.schema import JevDecision

def decide_size(confidence: float, max_frac: float, low_frac: float, bankroll: float) -> float:
    # Fractional Kelly quarter cap but concentration 20% when >=0.97
    frac = max_frac if confidence >= 0.97 else low_frac
    return bankroll * frac

def should_trade(jev: JevDecision, spread_bps: float, fee_bps: float, slippage_bps: float, min_edge_bps: float = 20) -> bool:
    if not jev.passes_95_pathway():
        return False
    if jev.direction == "neutral":
        return False
    # spread > fees+slippage+20bps
    if spread_bps <= fee_bps + slippage_bps + min_edge_bps:
        return False
    return True
