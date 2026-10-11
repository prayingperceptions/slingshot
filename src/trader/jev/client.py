"""Jev judge client.

Jev judges only — code owns thresholds. The remote Jev service
(console.typesafe.ai) is UNVERIFIED from this environment; JevClient will
raise a clear error if unreachable. PaperJudge is a deterministic,
rules-based fallback so the full pipeline runs in paper mode without it.
"""
import json
import urllib.request
import urllib.error

from .schema import JevDecision

JEV_URL = "https://console.typesafe.ai/api/judge"


class JevUnreachable(RuntimeError):
    pass


class JevClient:
    """Thin HTTP client for the remote Jev judge model."""

    def __init__(self, api_key: str, model: str = "jev-v1", url: str = JEV_URL, timeout: int = 10):
        if not api_key:
            raise ValueError("JevClient needs an API key")
        self.api_key = api_key
        self.model = model
        self.url = url
        self.timeout = timeout

    def judge(self, prompt: str) -> JevDecision:
        body = json.dumps({"model": self.model, "input": prompt}).encode()
        req = urllib.request.Request(
            self.url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                payload = json.loads(resp.read().decode())
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            raise JevUnreachable(f"Jev service unreachable at {self.url}: {e}") from e
        # Expect the service to return the decision fields directly.
        decision = payload.get("decision", payload)
        try:
            return JevDecision(**decision)
        except Exception as e:
            raise JevUnreachable(f"Jev returned an unparsable decision: {e}") from e


class PaperJudge:
    """Deterministic rules-based judge. No network, no model.

    Scores the snapshot against the spec's hard thresholds and emits a
    JevDecision. This is what paper mode uses — and it doubles as the
    calibration reference: if PaperJudge can't reach 0.97 on your data,
    a remote model won't either.
    """

    def judge(self, snapshot) -> JevDecision:
        score = 0.50
        checks = 0

        # Perp edge: funding + basis
        if snapshot.funding_annualized >= 20.0:
            score += 0.15
            checks += 1
        if snapshot.basis_bps >= 50.0:
            score += 0.10
            checks += 1
        # Meme edge: contract safety + market structure
        if snapshot.rug_score >= 95:
            score += 0.10
            checks += 1
        if snapshot.top10_pct <= 12.0:
            score += 0.05
            checks += 1
        if snapshot.volume_liq_ratio >= 1.0:
            score += 0.05
            checks += 1
        # Execution edge: spread covers costs
        if snapshot.spread_bps > snapshot.slippage_bps + 25:
            score += 0.05
            checks += 1

        confidence = min(0.99, score)
        setup_quality = min(3, checks)

        # Direction from the strongest signal
        if snapshot.funding_annualized >= 20.0 and snapshot.basis_bps >= 50.0:
            direction = "long"  # basis/funding arb long leg
        elif snapshot.rug_score >= 95 and snapshot.volume_liq_ratio >= 1.0:
            direction = "long"
        elif snapshot.funding_annualized <= -7.0:
            direction = "short"
        else:
            direction = "neutral"

        # Regime from realized vol
        rv = snapshot.rv_1h
        if rv >= 100:
            regime = "crisis"
        elif rv >= 50:
            regime = "high_vol"
        elif abs(snapshot.basis_bps) >= 20:
            regime = "trending"
        else:
            regime = "mean_reverting"

        # Risk state from drawdown
        dd = snapshot.drawdown_pct
        if dd >= 13:
            risk_state = "reduce"
        elif dd >= 10:
            risk_state = "near_limit"
        else:
            risk_state = "safe"

        brier = round(max(0.02, 0.20 - 0.05 * checks), 3)

        return JevDecision(
            regime=regime,
            direction=direction,
            setup_quality=setup_quality,
            risk_state=risk_state,
            confidence=round(confidence, 3),
            brier=brier,
        )
