from dataclasses import dataclass
import time, math

@dataclass(frozen=True)
class Snapshot:
    # <400 tokens when serialized — Jev's only input
    mid: float
    spread_bps: float
    imbalance: float
    rv_1h: float
    funding_annualized: float
    basis_bps: float
    liq_depth_2x: float
    rug_score: int
    top10_pct: float
    inventory: float
    drawdown_pct: float
    ts: int
    bankroll: float
    slippage_bps: float
    volume_liq_ratio: float

    def to_prompt(self) -> str:
        # Keep <400 tokens, causal, no future
        return (
            f"mid={self.mid:.2f} spread_bps={self.spread_bps:.1f} imbalance={self.imbalance:.2f} "
            f"rv_1h={self.rv_1h:.2f} funding_ann={self.funding_annualized:.1f}% basis_bps={self.basis_bps:.1f} "
            f"liq_depth_2x={self.liq_depth_2x:.2f} rug={self.rug_score} top10={self.top10_pct:.1f}% "
            f"inv={self.inventory:.2f} dd={self.drawdown_pct:.1f}% bankroll={self.bankroll:.2f} "
            f"slip_bps={self.slippage_bps:.1f} vol_liq={self.volume_liq_ratio:.2f} ts={self.ts}"
        )

def compute_mid(bid: float, ask: float) -> float:
    return (bid + ask) / 2

def compute_spread_bps(bid: float, ask: float, mid: float) -> float:
    return ((ask - bid) / mid * 10000) if mid else 9999

def compute_imbalance(bid_vol: float, ask_vol: float) -> float:
    tot = bid_vol + ask_vol
    return (bid_vol - ask_vol) / tot if tot else 0

def compute_rv_1h(closes: list[float]) -> float:
    if len(closes) < 2: return 0
    # skip non-positive prints (bad feed data) rather than crashing
    clean = [c for c in closes if c and c > 0]
    if len(clean) < 2: return 0
    rets = [math.log(clean[i]/clean[i-1]) for i in range(1, len(clean))]
    return math.sqrt(sum(r*r for r in rets) / len(rets)) * math.sqrt(3600) * 100

def compute_funding_annualized(funding_8h: float) -> float:
    return funding_8h * 3 * 365 * 100

def compute_basis_bps(perp: float, spot: float) -> float:
    return ((perp - spot) / spot * 10000) if spot else 0

def build_snapshot(
    bid, ask, bid_vol, ask_vol, closes_1h, funding_8h, perp_price, spot_price,
    liq_depth_2x, rug_score, top10_pct, inventory, drawdown_pct, bankroll, slippage_bps, vol, liq
) -> Snapshot:
    mid = compute_mid(bid, ask)
    return Snapshot(
        mid=mid,
        spread_bps=compute_spread_bps(bid, ask, mid),
        imbalance=compute_imbalance(bid_vol, ask_vol),
        rv_1h=compute_rv_1h(closes_1h),
        funding_annualized=compute_funding_annualized(funding_8h),
        basis_bps=compute_basis_bps(perp_price, spot_price),
        liq_depth_2x=liq_depth_2x,
        rug_score=rug_score,
        top10_pct=top10_pct,
        inventory=inventory,
        drawdown_pct=drawdown_pct,
        ts=int(time.time()),
        bankroll=bankroll,
        slippage_bps=slippage_bps,
        volume_liq_ratio=(vol/liq if liq else 0),
    )
