import tomli, pathlib, dataclasses

@dataclasses.dataclass(frozen=True)
class RiskConfig:
    max_drawdown_pct: float
    max_daily_loss_usd: float
    max_daily_loss_pct: float
    max_position_frac: float
    max_position_frac_low_conf: float
    halt_drawdown_pct: float
    kill_file: str

@dataclasses.dataclass(frozen=True)
class Config:
    run_mode: str
    min_bankroll: float
    risk: RiskConfig
    raw: dict

    def refuses_looser_limits(self, other: dict) -> bool:
        # Enforce cannot loosen beyond defaults
        return (
            other.get("risk", {}).get("max_drawdown_pct", 100) > self.risk.max_drawdown_pct or
            other.get("risk", {}).get("max_position_frac", 1) > self.risk.max_position_frac
        )

def load_config(path="config/default.toml") -> Config:
    p = pathlib.Path(path)
    data = tomli.loads(p.read_text())
    r = data["risk"]
    risk = RiskConfig(
        max_drawdown_pct=r["max_drawdown_pct"],
        max_daily_loss_usd=r["max_daily_loss_usd"],
        max_daily_loss_pct=r["max_daily_loss_pct"],
        max_position_frac=r["max_position_frac"],
        max_position_frac_low_conf=r["max_position_frac_low_conf"],
        halt_drawdown_pct=r["halt_drawdown_pct"],
        kill_file=r["kill_file"],
    )
    return Config(run_mode=data["run"]["mode"], min_bankroll=data["run"]["min_bankroll"], risk=risk, raw=data)
