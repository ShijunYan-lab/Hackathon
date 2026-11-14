"""Frozen single-map transport settings. No outcome depends on run number."""
from pydantic import Field
from shared.protocol import DTO, Tile


class TransportScenario(DTO):
    cargo_initial: int = Field(default=10, gt=0)
    gold_initial: int = Field(default=20, gt=0)
    escort_cost: int = Field(default=5, ge=0)
    cargo_loss_per_hit: int = Field(default=2, ge=0)
    timeout_s: float = Field(default=45, gt=0, le=300)
    success_ratio: float = Field(default=.8, ge=0, le=1)
    alpha: float = Field(default=.8, gt=0, le=1)
    direct_value: float = Field(default=.6, ge=-1, le=1)
    escort_value: float = Field(default=.5, ge=-1, le=1)
    start: Tile = Field(default_factory=lambda: Tile(x=8.5, y=8.5))
    destination: Tile = Field(default_factory=lambda: Tile(x=20.5, y=8.5))
    threat: Tile = Field(default_factory=lambda: Tile(x=14.5, y=8.5))
    guard_consents: bool = True

