"""Red-team harness: adversarial scenarios against the live engine.

Each test attacks a failure mode an autonomous trader WILL encounter:
flash crashes, stale feeds, corrupt data, whale dumps, kill-switch,
risk trips, judge outages. A pass means the system degrades safely —
never crashes, never trades blind, never ignores the kill file.
"""
import sys, os, time, pathlib, unittest
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "src"))

from trader.config import load_config
from trader.state_engine import build_snapshot
from trader import risk
from trader.engine import Engine
from trader.jev.client import PaperJudge
from trader.execution.paper import PaperBroker


def hot_md(price=67400.0, **kw):
    """A tradeable hot tick."""
    spread = price * 0.0035
    d = dict(bid=price - spread / 2, ask=price + spread / 2,
             bid_vol=1.0, ask_vol=1.0, closes_1h=[price] * 60,
             funding_8h=0.0006, perp_price=price * 1.008, spot_price=price,
             liq_depth_2x=50000.0, rug_score=97, top10_pct=8.0,
             slippage_bps=4.0, vol_24h=900000.0, liq_usd=400000.0,
             rsi=55.0, sentiment=0.0)
    d.update(kw)
    return d


def fresh_engine(bankroll=50.0):
    risk._state.armed = False
    risk._state.tripped = False
    risk._state.trip_reason = ""
    risk._state.daily_pnl = 0
    cfg = load_config("config/default.toml")
    risk.arm()
    return Engine(cfg, PaperJudge(), bankroll)


def open_long(eng, price=67400.0):
    r = eng.tick(hot_md(price))
    assert eng.broker.positions, f"setup failed: no position opened: {r['actions']}"
    return eng.broker.positions[eng.symbol]


class TestFlashCrash(unittest.TestCase):
    def test_40pct_crash_exits_safely(self):
        eng = fresh_engine()
        pos = open_long(eng)
        # next tick: -40% flash crash
        r = eng.tick(hot_md(price=67400.0 * 0.6, funding_8h=0.0001))
        # trailing stop (-20% from peak) must have fired
        actions = str(r["actions"])
        self.assertIn("trailing", actions)
        # position reduced or closed, never crashed
        self.assertIn("ledger", r)


class TestStaleFeed(unittest.TestCase):
    def test_100_identical_ticks_no_crash(self):
        eng = fresh_engine()
        md = hot_md()
        for _ in range(100):
            r = eng.tick(dict(md))
        self.assertIn("ledger", r)
        # time-decay guard uses real timestamps; just verify no exception
        # and no runaway position sizing
        self.assertLessEqual(len(eng.broker.positions), 1)


class TestCorruptData(unittest.TestCase):
    def test_zero_prices(self):
        eng = fresh_engine()
        r = eng.tick(hot_md(price=0))
        # must not raise, must not trade on zero
        self.assertIn("ledger", r)
        self.assertEqual(len(eng.broker.positions), 0)

    def test_missing_keys(self):
        eng = fresh_engine()
        r = eng.tick({})
        self.assertIn("error", r)
        self.assertEqual(len(eng.broker.positions), 0)

    def test_negative_prices(self):
        eng = fresh_engine()
        r = eng.tick(hot_md(price=-100.0))
        self.assertIn("error", r)


class TestWhaleDump(unittest.TestCase):
    def test_whale_exits_half(self):
        eng = fresh_engine()
        pos = open_long(eng)
        size_before = pos.size_usd
        r = eng.tick(hot_md(top_holder_pct=5.0))
        pos_after = eng.broker.positions.get(eng.symbol)
        # 50% exit: position halved or closed
        remaining = pos_after.size_usd if pos_after else 0
        self.assertLess(remaining, size_before)
        self.assertIn("whale", str(r["actions"]))


class TestKillSwitch(unittest.TestCase):
    def test_kill_flattens_open_position(self):
        eng = fresh_engine()
        open_long(eng)
        self.assertTrue(eng.broker.positions)
        kill = pathlib.Path("/tmp/slingshot_kill_test_red")
        kill.write_text("test")
        eng.config = eng.config  # keep
        # point risk at test kill file via config replace
        import dataclasses
        eng.config = dataclasses.replace(
            eng.config, risk=dataclasses.replace(eng.config.risk, kill_file=str(kill)))
        r = eng.tick(hot_md())
        kill.unlink()
        self.assertEqual(len(eng.broker.positions), 0,
                         f"kill file did not flatten: {r['actions']}")
        self.assertIn("kill_flatten", str(r["actions"]))

    def test_kill_blocks_new_entries(self):
        eng = fresh_engine()
        kill = pathlib.Path("/tmp/slingshot_kill_test_red2")
        kill.write_text("test")
        import dataclasses
        eng.config = dataclasses.replace(
            eng.config, risk=dataclasses.replace(eng.config.risk, kill_file=str(kill)))
        r = eng.tick(hot_md())
        kill.unlink()
        self.assertEqual(len(eng.broker.positions), 0)


class TestRiskTrips(unittest.TestCase):
    def test_max_dd_blocks_entries_sticky(self):
        eng = fresh_engine()
        # force drawdown by draining bankroll
        eng.broker.bankroll = 40.0  # 20% DD from 50
        r = eng.tick(hot_md())
        self.assertFalse(r["risk"]["ok"])
        self.assertIn("max_dd", r["risk"]["reason"])
        self.assertEqual(len(eng.broker.positions), 0)


class TestJudgeOutage(unittest.TestCase):
    def test_judge_raise_skips_tick(self):
        eng = fresh_engine()
        class Boom:
            def judge(self, snap):
                raise RuntimeError("jev down")
        eng.judge = Boom()
        r = eng.tick(hot_md())
        self.assertIn("judge_error", r)
        self.assertEqual(len(eng.broker.positions), 0)


class TestLiquidityBlackHole(unittest.TestCase):
    def test_zero_liquidity_no_entry(self):
        eng = fresh_engine()
        r = eng.tick(hot_md(liq_depth_2x=0.0, liq_usd=0.0))
        # book-walk rejects: no fill on zero depth
        self.assertEqual(len(eng.broker.positions), 0)


if __name__ == "__main__":
    unittest.main()
