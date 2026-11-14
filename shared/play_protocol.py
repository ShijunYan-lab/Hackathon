"""Additive local-game APIs. Never accept prices, rewards or damage from clients."""
from typing import Literal
from pydantic import Field
from shared.protocol import DTO, RequestBase, VersionedRequest

class ModelConfig(RequestBase):
    enabled: bool = False
    base_url: str = Field(default="", max_length=500)
    model: str = Field(default="", max_length=160)
    api_key: str = Field(default="", max_length=2048, repr=False)

class ShopBuy(VersionedRequest):
    item_id: str
    quote_id: str

class ContainerTake(VersionedRequest):
    item_id: str | None = None
    take_gold: bool = False

class ConsumableUse(VersionedRequest):
    item_id: str

class QuestAccept(VersionedRequest):
    quest_id: str
