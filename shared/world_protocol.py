"""Additive world economy requests; existing v1 command payloads remain unchanged."""
from typing import Literal
from pydantic import Field, model_validator
from shared.protocol import VersionedRequest


class OfferRequest(VersionedRequest):
    actor_id: str
    target_id: str
    kind: Literal['trade', 'invite', 'relation']
    item_id: str | None = None
    price: int = Field(default=0, ge=0)
    org_id: str | None = None
    target_org_id: str | None = None
    stance: Literal['trade', 'allied', 'neutral'] | None = None
    expires_in_ticks: int = Field(default=3, ge=1, le=20)

    @model_validator(mode='after')
    def terms(self):
        if self.kind == 'trade':
            if not self.item_id or self.org_id or self.target_org_id or self.stance:
                raise ValueError('Trade requires only item_id and price')
        elif self.kind == 'invite':
            if not self.org_id or self.item_id or self.target_org_id or self.stance or self.price:
                raise ValueError('Invite requires only org_id')
        elif not self.org_id or not self.target_org_id or not self.stance or self.item_id or self.price:
            raise ValueError('Relation requires two organizations and stance')
        return self


class CraftRequest(VersionedRequest):
    actor_id: str
    recipe_id: str


class SupplyRequest(VersionedRequest):
    actor_id: str
    org_id: str
    item_ids: list[str] = Field(min_length=1, max_length=20)
