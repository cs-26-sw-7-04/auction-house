"""The vocabulary of the auction house: plain data and the errors it raises.

Nothing here knows about HTTP, Kubernetes or any particular solver.
"""
import datetime
import enum
import uuid
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator


def utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _to_utc(value: datetime.datetime) -> datetime.datetime:
    """Naive datetimes are taken to be UTC already."""
    if value.tzinfo is None:
        return value.replace(tzinfo=datetime.timezone.utc)
    return value.astimezone(datetime.timezone.utc)


UtcDatetime = Annotated[datetime.datetime, AfterValidator(_to_utc)]
Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class Model(BaseModel):
    model_config = ConfigDict(frozen=True)


# --- Tasks -------------------------------------------------------------------

class Resources(Model):
    cpu_millis: int = Field(500, gt=0)
    memory_mb: int = Field(256, gt=0)
    gpu: bool = False


class Verification(enum.StrEnum):
    NONE = "none"
    HASH = "hash"


class TaskSpec(Model):
    """What a submitter sends."""
    image: str = Field(description="Container image that runs the task")
    deadline: UtcDatetime
    max_budget: int = Field(gt=0, description="The most the submitter will pay; used as the task's value")
    resources: Resources = Resources()
    verification: Verification = Verification.NONE
    expected_result_hash: Sha256 | None = None

    @model_validator(mode="after")
    def _hash_needed_for_hash_verification(self):
        if self.verification is Verification.HASH and self.expected_result_hash is None:
            raise ValueError("expected_result_hash is required when verification is 'hash'")
        return self


class TaskStatus(enum.StrEnum):
    PENDING = "pending"          # waiting for the next auction
    IN_AUCTION = "in_auction"    # part of an open auction
    EXECUTING = "executing"      # awarded and deployed
    COMPLETED = "completed"      # result reported and accepted
    FAILED = "failed"            # deployment failed or result rejected
    UNALLOCATED = "unallocated"  # no winning bid in any round
    EXPIRED = "expired"          # deadline passed before it was awarded


TERMINAL = frozenset({TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.UNALLOCATED, TaskStatus.EXPIRED})


class Task(Model):
    task_id: uuid.UUID
    owner: str
    spec: TaskSpec
    status: TaskStatus = TaskStatus.PENDING
    submitted_at: UtcDatetime
    rounds: int = Field(0, description="Auctions this task has been part of")
    auction_id: uuid.UUID | None = None
    bidder_id: str | None = Field(None, description="The winner, once awarded")
    handle: str | None = Field(None, description="Deployer handle, e.g. a Job name")


class TaskOffer(Model):
    """What a bidder is shown of a task: enough to price it, not to run it or see its budget."""
    task_id: uuid.UUID
    resources: Resources
    deadline: UtcDatetime


# --- Bids and outcomes ---------------------------------------------------------

class BidRequest(Model):
    """Sealed: only the bidder who placed it and the house can read it."""
    capacity: int = Field(ge=1, description="Most tasks the bidder can run in this auction")
    unit_price: int = Field(ge=0, description="Price asked per task")


class Bid(BidRequest):
    bidder_id: str
    placed_at: UtcDatetime


class Award(Model):
    bidder_id: str
    task_ids: tuple[uuid.UUID, ...]
    unit_price: int
    payment: int = Field(description="What the bidder is paid in total, by the clearing rule")


class Outcome(Model):
    awards: tuple[Award, ...]
    unallocated: tuple[uuid.UUID, ...]
    welfare: int


class Selection(Model):
    """A solver's allocation: which bidder runs which task."""
    assignment: dict[uuid.UUID, str]
    welfare: int


class AuctionStatus(enum.StrEnum):
    OPEN = "open"
    CLEARING = "clearing"
    CLEARED = "cleared"
    FAILED = "failed"


class AuctionView(Model):
    """The public face of an auction: no bids, no outcome."""
    auction_id: uuid.UUID
    status: AuctionStatus
    closes_at: UtcDatetime
    tasks: tuple[TaskOffer, ...]


class Auction(Model):
    """The full record, for the operator."""
    auction_id: uuid.UUID
    task_ids: tuple[uuid.UUID, ...]
    closes_at: UtcDatetime
    status: AuctionStatus = AuctionStatus.OPEN
    outcome: Outcome | None = None
    handles: dict[uuid.UUID, str] = {}


class Assignment(Model):
    """An award as the winning bidder sees it, with the payloads it may now run."""
    auction_id: uuid.UUID
    award: Award
    tasks: tuple[Task, ...]


# --- Errors ----------------------------------------------------------------------

class AuctionHouseError(Exception):
    """Base of everything the house raises on purpose."""


class NotFound(AuctionHouseError): ...
class Conflict(AuctionHouseError): ...
class Invalid(AuctionHouseError): ...
class Forbidden(AuctionHouseError): ...
class Unavailable(AuctionHouseError): ...


class UnknownTask(NotFound): ...
class UnknownAuction(NotFound): ...
class AuctionClosed(Conflict): ...
class InvalidTask(Invalid): ...
class IneligibleBid(Invalid): ...
class NotAssigned(Forbidden): ...
class SolverError(Unavailable): ...
