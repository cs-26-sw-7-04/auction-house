"""The vocabulary of the auction house: plain data and the errors it raises.

Nothing here knows about HTTP, Kubernetes or any particular solver.
"""
import datetime
import enum
import uuid
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator


def utcnow() -> datetime.datetime:
    """The current time as a timezone-aware UTC datetime. The house's default clock implementation"""
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
    """What a task needs to run. Bidders see it so they can valuate the task, and
    the deployer turns it into resource requests for the winner's node."""
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
    """Where a task is in its life.
    
    Normal path: pending -> in_auction -> executing -> completed or failed.
    A task nobody wins goes back to pending until it runs out of rounds (then
    unallocated), and a pending task past its deadline expires."""
    PENDING = "pending"          # waiting for the next auction
    IN_AUCTION = "in_auction"    # part of an open auction
    EXECUTING = "executing"      # awarded and deployed
    COMPLETED = "completed"      # result reported and accepted
    FAILED = "failed"            # deployment failed or result rejected
    UNALLOCATED = "unallocated"  # no winning bid in any round
    EXPIRED = "expired"          # deadline passed before it was awarded


# Statuses a task can never leave. Immutable.
TERMINAL = frozenset({TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.UNALLOCATED, TaskStatus.EXPIRED})


class Task(Model):
    """A task as the house stores it.
    
    the submitter's spec plus what the house has learned about it since. 
    Is immutable."""
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
    """Sealed: only the bidder who placed it and the house can read it. The task it
    is for is supplied separately; see `Bid`."""
    #capacity: int = Field(ge=1, description="Most tasks the bidder can run in this auction")
    price: int = Field(ge=0, description="Price asked to run task")


class Bid(BidRequest):
    """A bid as stored: the request plus the task it is for, who placed it and when."""
    task_id: uuid.UUID
    bidder_id: str
    placed_at: UtcDatetime


class Award(Model):
    """One task awarded to one bidder, and what the bidder is paid for it, which the
    clearing rule may set above or below the price asked."""
    task_id: uuid.UUID
    bidder_id: str
    payment: int


class Outcome(Model):
    """The result of clearing an auction: who won what, which tasks nobody won, 
    and the welfare of the allocation (task values less the winners' asks)."""
    awards: tuple[Award, ...]
    unallocated: tuple[uuid.UUID, ...]
    welfare: int


class Selection(Model):
    """A solver's allocation: which bidder runs which task."""
    assignment: dict[uuid.UUID, str]
    welfare: int


class AuctionStatus(enum.StrEnum):
    """Where an auction is in its life."""
    OPEN = "open"          # accepting bids until `closes_at`
    CLEARING = "clearing"  # bids closed; the engine and deployer are running
    CLEARED = "cleared"    # finished; the outcome is recorded
    FAILED = "failed"      # the engine failed; its tasks went back to pending


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


class Announcement(Model):
    """What bidders are told when an auction opens or closes. 
    Thin: it names the auction, and bidders fetch the offers with its id. Never carry bids, outcomes or budgets."""
    event: Literal["auction_opened", "auction_closed"]
    auction_id: uuid.UUID
    status: AuctionStatus
    closes_at: UtcDatetime


class Assignment(Model):
    """An award as the winning bidder sees it, with the payload it may now run."""
    auction_id: uuid.UUID
    award: Award
    task: Task


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
class InvalidBid(Invalid): ...
class IneligibleBid(Invalid): ...
class NotAssigned(Forbidden): ...
class SolverError(Unavailable): ...
