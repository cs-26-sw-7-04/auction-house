"""Configuration from `AH_*` environment variables or a `.env` file.

Components are chosen by name, with nested variables, e.g.

    AH_SOLVER__NAME=c
    AH_SOLVER__OPTIONS='{"library": "/path/to/libvcg.so"}'
    AH_DEPLOYER__NAME=kubernetes
"""
import datetime
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from auction_house.plugins import ComponentSpec

Role = Literal["submitter", "bidder", "operator"]


class Principal(BaseModel, frozen=True):
    role: Role
    id: str


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AH_", env_nested_delimiter="__", env_file=".env", extra="ignore")

    # API key -> who it belongs to. AH_API_KEYS='{"k1": {"role": "bidder", "id": "alice"}}'
    api_keys: dict[str, Principal] = {}

    bidding_window: datetime.timedelta = datetime.timedelta(minutes=1)
    max_rounds: int = Field(3, ge=1, description="Auctions a task may enter before it is given up on")
    auto_run: bool = Field(False, description="Open and clear auctions on a timer")
    tick: datetime.timedelta = datetime.timedelta(seconds=1)

    task_store: ComponentSpec = ComponentSpec(name="memory")
    auction_store: ComponentSpec = ComponentSpec(name="memory")
    bid_pool: ComponentSpec = ComponentSpec(name="memory")
    grouper: ComponentSpec = ComponentSpec(name="batch")
    eligibility: ComponentSpec = ComponentSpec(name="all")
    engine: ComponentSpec = ComponentSpec(name="vcg")
    solver: ComponentSpec = ComponentSpec(name="vcg_combinatorial")
    deployer: ComponentSpec = ComponentSpec(name="logging")
    verifier: ComponentSpec = ComponentSpec(name="accept-none-empty-results")
    ledger: ComponentSpec = ComponentSpec(name="logging")
    notifier: ComponentSpec = ComponentSpec(name="logging")
