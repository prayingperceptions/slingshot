"""Slingshot engine: fetch -> snapshot -> judge -> risk -> execute.

One tick = one full pass. Every decision is logged to the tick report.
Paper mode only — the broker is always PaperBroker here.
"""
import time

from .config import Config
from .state_engine import build_snapshot
from . import risk
from . import policy
from .execution.paper import PaperBroker
from .execution import stash as stash_mod
from .execution import velocity as velocity_mod
from .guards import whale as g_whale
from .guards import liquidity as g_liq
from .guards import sentiment as g_sent
from .guards import parabolic as g_para
from .jev.client import JevClient


class Engine:
    def __init__(self, config: Config, judge, bankroll: float):
        self.config = config
        self.judge = judge
        self.broker = PaperBroker(bankroll)
        self.symbol = "BTC-PERP"  # default market; loop may override
        self._liq_ref: float | None = None
        self._sent_ref: tuple[float, int] | None = None
        self.ticks = 0
        self.trades = 0

    def tick(self, md: dict) -> dict:
        """md: market data dict with keys used below. Returns tick report."""
        self.ticks += 1
        now = int(time.time())
        report: dict = {"ts": now, "actions": []}

        snap = build_snapshot(
            bid=md["bid"], ask=md["ask"],
            bid_vol=md.get("bid_vol", 1.0), ask_vol=md.get("ask_vol", 1.0),
            closes_1h=md.get("closes_1h", [md["bid"]]),
            funding_8h=md.get("funding_8h", 0.0),
            perp_price=md.get("perp_price", md["bid"]),
            spot_price=md.get("spot_price", md["bid"]),
            liq_depth_2x=md.get("liq_depth_2x", 0.0),
            rug_score=md.get("rug_score", 0),
            top10_pct=md.get("top10_pct", 100.0),
            inventory=self.broker.realized_pnl,
            drawdown_pct=self.broker.drawdown_pct(),
            bankroll=self.broker.bankroll,
            slippage_bps=md.get("slippage_bps", 5.0),
            vol=md.get("vol_24h", 0.0),
            liq=md.get("liq_usd", 0.0),
        )
        report["snapshot_tokens"] = len(snap.to_prompt().split())

        # Judge — JevClient takes the prompt string, PaperJudge takes the snapshot
        if isinstance(self.judge, JevClient):
            decision = self.judge.judge(snap.to_prompt())
        else:
            decision = self.judge.judge(snap)
        report["decision"] = decision.model_dump()

        mid = snap.mid

        # Manage open positions first: guards + stash
        for symbol in list(self.broker.positions):
            pos = self.broker.positions[symbol]
            self.broker.update_peak(symbol, mid)

            guard_results = [
                g_whale.check(md.get("top_holder_pct", 0.0)),
                g_liq.check(md.get("liq_usd", 0.0), self._liq_ref or md.get("liq_usd", 0.0),
                            pos.size_usd),
                g_para.check(pos, mid,
                             rsi=md.get("rsi"),
                             vol_now=md.get("vol_24h"), vol_ref=md.get("vol_ref"),
                             funding_ann=snap.funding_annualized, now=now),
            ]
            if self._sent_ref:
                s_now = md.get("sentiment", 0.0)
                s_old, s_ts = self._sent_ref
                if now - s_ts < 600:
                    guard_results.append(g_sent.check(s_now, s_old))

            # Strongest exit signal wins
            exits = [g for g in guard_results if g[0] == "exit_frac"]
            if exits:
                exits.sort(key=lambda g: g[1], reverse=True)
                _, frac, reason = exits[0]
                pnl_before = self.broker.realized_pnl
                ok, msg = self.broker.close(symbol, mid, frac)
                # incremental PnL only — realized_pnl is cumulative
                risk.update_pnl(self.broker.realized_pnl - pnl_before)
                report["actions"].append({"guard_exit": reason, "result": msg})
                continue

            # Stash ladder on parabolic multiples
            profit, alloc = stash_mod.stash_amount(pos.entry_price, mid, pos.size_usd)
            if profit > 0:
                report["actions"].append({"stash": alloc, "profit_usd": profit})

        # New entries
        if self.symbol not in self.broker.positions:
            ok, reason = risk.check_limits(snap, self.config, self.config.risk.max_position_frac)
            report["risk"] = {"ok": ok, "reason": reason}
            if ok and policy.should_trade(decision,
                                          snap.spread_bps, 5.0, snap.slippage_bps):
                tradable = velocity_mod.tradable_bankroll(
                    self.broker.bankroll, self.config.min_bankroll)
                size = policy.decide_size(decision.confidence,
                                          self.config.risk.max_position_frac,
                                          self.config.risk.max_position_frac_low_conf,
                                          tradable)
                if size > 0:
                    ok, msg = self.broker.open(self.symbol, decision.direction, size,
                                               mid, snap.liq_depth_2x, snap.slippage_bps)
                    report["actions"].append({"entry": msg})
                    if ok:
                        self.trades += 1
            else:
                report["actions"].append({"no_trade": reason if not ok else "policy_reject"})
        else:
            report["risk"] = {"ok": True, "reason": "managing_open"}

        # Reference updates
        if self._liq_ref is None and md.get("liq_usd"):
            self._liq_ref = md["liq_usd"]
        self._sent_ref = (md.get("sentiment", 0.0), now)

        report["ledger"] = self.broker.ledger()
        return report
