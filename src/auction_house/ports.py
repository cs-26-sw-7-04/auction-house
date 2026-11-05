"""The interfaces (ports) the auction house is built from.

Each is a `Protocol`: a component only has to have the right methods, it does
not inherit from anything. Components are chosen by name in `plugins.py`, so
swapping one is a configuration change.
"""
import uuid
from collections.abc import Mapping, Sequence
from typing import Protocol, runtime_checkable

import auction_house.domain


@runtime_checkable
class TaskStore(Protocol):
    def add(self, task: auction_house.domain.Task) -> None: ...
    def get(self, task_id: uuid.UUID) -> auction_house.domain.Task: ...
    def update(self, task: auction_house.domain.Task) -> None: ...
    def list(self, *, status: auction_house.domain.TaskStatus | None = None, owner: str | None = None) -> list[auction_house.domain.Task]: ...


@runtime_checkable
class AuctionStore(Protocol):
    def put(self, auction: auction_house.domain.Auction) -> None: ...
    def get(self, auction_id: uuid.UUID) -> auction_house.domain.Auction: ...
    def all(self) -> list[auction_house.domain.Auction]: ...


@runtime_checkable
class BidPool(Protocol):
    """Sealed storage. The house reads `all` only when it clears."""
    def put(self, auction_id: uuid.UUID, bid: auction_house.domain.Bid) -> None:
        """Store the bid, replacing the same bidder's earlier bid on the same task."""
    def of(self, auction_id: uuid.UUID, bidder_id: str) -> list[auction_house.domain.Bid]:
        """The bids this bidder has placed in the auction."""
    def all(self, auction_id: uuid.UUID) -> list[auction_house.domain.Bid]: ...


@runtime_checkable
class Bundler(Protocol):
    def plan(self, pending: Sequence[auction_house.domain.Task]) -> list[list[auction_house.domain.Task]]:
        """Split pending tasks into collections, each sold in one auction."""


@runtime_checkable
class Eligibility(Protocol):
    def is_eligible(self, bidder_id: str, task: auction_house.domain.Task) -> bool:
        """Whether the bidder may bid on, and receive, the task."""


@runtime_checkable
class Solver(Protocol):
    def solve(self, values: Mapping[uuid.UUID, int], bids: Sequence[auction_house.domain.Bid]) -> auction_house.domain.Selection:
        """Allocate tasks (valued by their submitters) to bidders for maximal
        welfare. A bid is for one task, and each task goes to at most one bidder."""


@runtime_checkable
class ClearingEngine(Protocol):
    def clear(self, values: Mapping[uuid.UUID, int], bids: Sequence[auction_house.domain.Bid]) -> auction_house.domain.Outcome:
        """Pick the winners and decide what each is paid."""


@runtime_checkable
class Deployer(Protocol):
    def deploy(self, task: auction_house.domain.Task, award: auction_house.domain.Award) -> str:
        """Start the task on the winner's node. Returns a handle."""


@runtime_checkable
class Verifier(Protocol):
    def verify(self, task: auction_house.domain.Task, result_hash: str | None) -> bool: ...


@runtime_checkable
class Ledger(Protocol):
    """Reputation. Written to after every settled task; nothing reads it yet."""
    def record(self, bidder_id: str, task_id: uuid.UUID, success: bool) -> None: ...


@runtime_checkable
class Notifier(Protocol):
    def auction_opened(self, auction: auction_house.domain.Auction) -> None: ...
    def auction_closed(self, auction: auction_house.domain.Auction) -> None: ...


class Subscription(Protocol):
    async def get(self) -> auction_house.domain.Announcement:
        """Wait for the next announcement."""
 
 
@runtime_checkable
class Announcer(Protocol):
    """Lets bidders listen for announcements instead of polling. Usually implemented
    by the notifier, so the house publishes and bidders subscribe through one object."""
    def subscribe(self, bidder_id: str) -> AbstractContextManager[Subscription]:
        """Start listening. Leaving the context stops it."""
