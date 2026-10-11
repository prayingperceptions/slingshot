from typing import Literal
from pydantic import BaseModel, Field

class JevDecision(BaseModel):
    regime: Literal["trending", "mean_reverting", "high_vol", "crisis"]
    direction: Literal["long", "short", "neutral"]
    toxic_flow: Literal["noul"] = "noul"
    setup_quality: int = Field(ge=0, le=3)  # require >=2
    risk_state: Literal["safe", "near_limit", "reduce"]  # require safe
    confidence: float = Field(ge=0, le=1)  # require >=0.97 for velocity
    brier: float = Field(ge=0, le=1)

    def passes_95_pathway(self) -> bool:
        return (
            self.confidence >= 0.97 and
            self.setup_quality >= 2 and
            self.risk_state == "safe" and
            self.brier < 0.10
        )
