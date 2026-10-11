import sys, os, unittest, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "src"))

from trader.config import load_config
from trader.state_engine import build_snapshot, compute_mid, compute_spread_bps
from trader import risk
from trader.jev.schema import JevDecision
from trader.jev.client import PaperJudge
from trader import policy, market
from trader.execution.paper import PaperBroker
from trader.execution import stash, velocity
from trader.guards import whale, liquidity, sentiment, parabolic


def snap(**kw):
    base = dict(bid=67400.0, ask=67405.0, bid_vol=1.0, ask_vol=1.0,
                closes_1h=[67000.0, 67100.0], funding_8h=0.0001,
                perp_price=67410.0, spot_price=67402.0, liq_depth_2x=5000.0,
                rug_score=97, top10_pct=8.0, inventory=0.0, drawdown_pct=2.0,
                bankroll=50.0, slippage_bps=4.0, vol=9000.0, liq=8000.0)
    base.update(kw)
    return build_snapshot(**base)


class TestConfig(unittest.TestCase):
    def test_loads_paper_default(self):
        cfg = load_config("config/default.toml")
        self.assertEqual(cfg.run_mode, "paper")
        self.assertEqual(cfg.risk.max_drawdown_pct, 15.0)

    def test_refuses_looser(self):
        cfg = load_config("config/default.toml")
        self.assertTrue(cfg.refuses_looser_limits({"risk": {"max_drawdown_pct": 50}}))
        self.assertTrue(cfg.refuses_looser_limits({"risk": {"max_position_frac": 0.5}}))
        # unspecified position frac defaults loose -> refuse
        self.assertTrue(cfg.refuses_looser_limits({"risk": {"max_drawdown_pct": 10}}))
        self.assertFalse(cfg.refuses_looser_limits(
            {"risk": {"max_drawdown_pct": 10, "max_position_frac": 0.10}}))


class TestStateEngine(unittest.TestCase):
    def test_mid_spread(self):
        self.assertEqual(compute_mid(100, 102), 101)
        self.assertAlmostEqual(compute_spread_bps(100, 102, 101), 198.02, places=1)

    def test_snapshot_prompt_compact(self):
        s = snap()
        self.assertLess(len(s.to_prompt().split()), 400)


class TestRisk(unittest.TestCase):
    def setUp(self):
        risk._state.armed = False
        risk._state.tripped = False
        risk._state.daily_pnl = 0

    def test_refuses_unarmed(self):
        cfg = load_config("config/default.toml")
        ok, reason = risk.check_limits(snap(), cfg, 0.1)
        self.assertFalse(ok)
        self.assertEqual(reason, "not_armed")

    def test_trips_on_max_dd(self):
        cfg = load_config("config/default.toml")
        risk.arm()
        ok, reason = risk.check_limits(snap(drawdown_pct=16.0), cfg, 0.1)
        self.assertFalse(ok)
        self.assertIn("max_dd", reason)
        self.assertTrue(risk._state.tripped)

    def test_daily_trip_clears_on_rollover(self):
        cfg = load_config("config/default.toml")
        risk.arm()
        risk._state.daily_pnl = -11.0
        ok, reason = risk.check_limits(snap(), cfg, 0.0)
        self.assertFalse(ok)
        self.assertIn("daily_loss", reason)
        self.assertEqual(risk._state.trip_reason, "daily_loss")
        risk.reset_daily()
        self.assertFalse(risk._state.tripped)
        self.assertEqual(risk._state.daily_pnl, 0)

    def test_max_dd_trip_survives_rollover(self):
        cfg = load_config("config/default.toml")
        risk.arm()
        ok, _ = risk.check_limits(snap(drawdown_pct=16.0), cfg, 0.0)
        self.assertFalse(ok)
        self.assertEqual(risk._state.trip_reason, "max_dd")
        risk.reset_daily()
        self.assertTrue(risk._state.tripped)  # sticky: needs manual re-arm

    def test_kill_file(self):
        cfg = load_config("config/default.toml")
        risk.arm()
        p = pathlib.Path("/tmp/slingshot_kill_test")
        p.write_text("x")
        cfg2 = load_config("config/default.toml")
        import dataclasses
        cfg2 = dataclasses.replace(cfg2, risk=dataclasses.replace(cfg2.risk, kill_file=str(p)))
        ok, reason = risk.check_limits(snap(), cfg2, 0.0)
        self.assertFalse(ok)
        self.assertEqual(reason, "kill_file_exists_flatten")
        p.unlink()


class TestJev(unittest.TestCase):
    def test_pathway_gate(self):
        d = JevDecision(regime="trending", direction="long", setup_quality=3,
                        risk_state="safe", confidence=0.98, brier=0.05)
        self.assertTrue(d.passes_95_pathway())
        d2 = d.model_copy(update={"confidence": 0.90})
        self.assertFalse(d2.passes_95_pathway())

    def test_paper_judge_strong_setup(self):
        s = snap(funding_8h=0.0004, rug_score=98, top10_pct=5.0, vol=16000.0, liq=8000.0)
        d = PaperJudge().judge(s)
        self.assertEqual(d.direction, "long")
        self.assertGreaterEqual(d.setup_quality, 2)

    def test_paper_judge_weak_setup_neutral(self):
        s = snap(funding_8h=0.0, rug_score=40, top10_pct=60.0, vol=100.0, liq=8000.0)
        d = PaperJudge().judge(s)
        self.assertFalse(d.passes_95_pathway())


class TestPolicy(unittest.TestCase):
    def test_sizing(self):
        self.assertEqual(policy.decide_size(0.98, 0.20, 0.05, 50.0), 10.0)
        self.assertEqual(policy.decide_size(0.80, 0.20, 0.05, 50.0), 2.5)

    def test_should_trade_rejects_thin_edge(self):
        d = JevDecision(regime="trending", direction="long", setup_quality=3,
                        risk_state="safe", confidence=0.98, brier=0.05)
        self.assertFalse(policy.should_trade(d, 10.0, 5.0, 5.0))  # 10 <= 5+5+20
        self.assertTrue(policy.should_trade(d, 40.0, 5.0, 5.0))


class TestBroker(unittest.TestCase):
    def test_open_close_roundtrip(self):
        b = PaperBroker(50.0)
        ok, _ = b.open("X", "long", 10.0, 100.0, 5000.0, 4.0)
        self.assertTrue(ok)
        ok, msg = b.close("X", 110.0)
        self.assertTrue(ok)
        self.assertGreater(b.bankroll, 50.0)
        self.assertEqual(len(b.fills), 2)

    def test_rejects_thin_depth(self):
        b = PaperBroker(50.0)
        ok, _ = b.open("X", "long", 10.0, 100.0, 5.0, 4.0)
        self.assertFalse(ok)


class TestStashVelocity(unittest.TestCase):
    def test_stash_ladder(self):
        self.assertEqual(stash.stash_splits(1.5), {})
        self.assertIn("USDC", stash.stash_splits(2.5))
        s5 = stash.stash_splits(6.0)
        self.assertIn("BTC", s5)
        s8 = stash.stash_splits(9.0)
        self.assertEqual(s8["trailing_pct"], 15)

    def test_velocity_ladder(self):
        self.assertEqual(velocity.reinvest_split(100)["reinvest_frac"], 1.0)
        self.assertEqual(velocity.reinvest_split(1000)["reinvest_frac"], 0.70)
        self.assertEqual(velocity.reinvest_split(5000)["reinvest_frac"], 0.50)
        self.assertEqual(velocity.reinvest_split(20000)["reinvest_frac"], 0.30)
        self.assertEqual(velocity.tradable_bankroll(100), 100.0)  # withdrawal floor, not a trading gate


class TestGuards(unittest.TestCase):
    def test_whale(self):
        self.assertEqual(whale.check(2.5)[0], "exit_frac")
        self.assertEqual(whale.check(0.5)[0], "hold")

    def test_liquidity_drop(self):
        self.assertEqual(liquidity.check(7000, 10000, 100)[0], "exit_frac")
        self.assertEqual(liquidity.check(9500, 10000, 100)[0], "hold")

    def test_sentiment(self):
        self.assertEqual(sentiment.check(-0.8, -0.1)[0], "exit_frac")
        self.assertEqual(sentiment.check(0.1, 0.0)[0], "hold")

    def test_parabolic_trailing(self):
        b = PaperBroker(50.0)
        b.open("X", "long", 10.0, 100.0, 5000.0, 4.0)
        pos = b.positions["X"]
        pos.peak_price = 200.0  # 2x run
        action, frac, _ = parabolic.check(pos, 150.0, now=pos.opened_ts + 60)
        self.assertEqual(action, "exit_frac")  # -25% from peak > -20% trail

    def test_funding_flip(self):
        b = PaperBroker(50.0)
        b.open("X", "long", 10.0, 100.0, 5000.0, 4.0)
        pos = b.positions["X"]
        action, frac, _ = parabolic.check(pos, 101.0, funding_ann=-8.0, now=pos.opened_ts + 60)
        self.assertEqual((action, frac), ("exit_frac", 1.0))


if __name__ == "__main__":
    unittest.main()
