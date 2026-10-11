import os, pathlib, time
from dataclasses import dataclass

@dataclass
class RiskState:
    armed: bool = False
    tripped: bool = False
    daily_pnl: float = 0
    peak_bankroll: float = 50.0
    last_reset_ts: int = 0

_state = RiskState()

def arm():
    _state.armed = True
    _state.tripped = False

def check_kill_file(path="/tmp/slingshot_kill") -> bool:
    return pathlib.Path(path).exists()

def check_limits(snapshot, config, position_frac: float) -> tuple[bool, str]:
    # Kill file flattens everything
    if check_kill_file(config.risk.kill_file):
        return False, "kill_file_exists_flatten"

    if not _state.armed:
        return False, "not_armed"

    if _state.tripped:
        # tripped allows exits only
        if position_frac > 0:
            return False, "tripped_exits_only"
        return True, "ok_tripped_exit"

    # Max DD 15%
    if snapshot.drawdown_pct >= config.risk.max_drawdown_pct:
        _state.tripped = True
        return False, f"max_dd_{snapshot.drawdown_pct:.1f}%"

    # Daily loss $10 or 30%
    daily_loss_pct = (-snapshot.inventory / config.min_bankroll * 100) if snapshot.inventory < 0 else 0
    if _state.daily_pnl <= -config.risk.max_daily_loss_usd or daily_loss_pct >= config.risk.max_daily_loss_pct:
        _state.tripped = True
        return False, f"daily_loss_${_state.daily_pnl:.2f}_{daily_loss_pct:.1f}%"

    # -20% halt require YES
    if snapshot.drawdown_pct >= config.risk.halt_drawdown_pct:
        return False, "halt_-20%_require_YES"

    # Position caps clip never enlarge
    max_frac = config.risk.max_position_frac if snapshot.rug_score >=95 else config.risk.max_position_frac_low_conf
    if position_frac > max_frac:
        return False, f"cap_clip_{max_frac}"

    return True, "ok"

def update_pnl(pnl: float):
    _state.daily_pnl += pnl

def reset_daily():
    _state.daily_pnl = 0
    _state.last_reset_ts = int(time.time())
