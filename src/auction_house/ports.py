"""The interfaces (ports) the auction house is built from.

Each is a `Protocol`: a component only has to have the right methods, it does
not inherit from anything. Components are chosen by name in `plugins.py`, so
swapping one is a configuration change.
"""
import uuid
from collections.abc import Mapping, Sequence
from typing import Protocol, runtime_checkable

from auction_house.domain import (
    Auction,
    Award,
    Bid,
    Outcome,
    Selection,
    Task,
    TaskStatus,
)


@runtime_checkable
class TaskStore(Protocol):
    def add(self, task: Task) -> None: ...
    def get(self, task_id: uuid.UUID) -> Task: ...
    def update(self, task: Task) -> None: ...
    def list(self, *, status: TaskStatus | None = None, owner: str | None = None) -> list[Task]: ...


@runtime_checkable
class AuctionStore(Protocol):
    def put(self, auction: Auction) -> None: ...
    def get(self, auction_id: uuid.UUID) -> Auction: ...
    def all(self) -> list[Auction]: ...


@runtime_checkable
class BidPool(Protocol):
    """Sealed storage. The house reads `all` only when it clears."""
    def put(self, auction_id: uuid.UUID, bid: Bid) -> None:
        """Store the bid, replacing the same bidder's earlier bid on the same task."""
    def of(self, auction_id: uuid.UUID, bidder_id: str) -> list[Bid]:
        """The bids this bidder has placed in the auction."""
    def all(self, auction_id: uuid.UUID) -> list[Bid]: ...


@runtime_checkable
class Bundler(Protocol):
    def plan(self, pending: Sequence[Task]) -> list[list[Task]]:
        """Split pending tasks into collections, each sold in one auction."""


@runtime_checkable
class Eligibility(Protocol):
    def is_eligible(self, bidder_id: str, task: Task) -> bool:
        """Whether the bidder may bid on, and receive, the task."""


@runtime_checkable
class Solver(Protocol):
    def solve(self, values: Mapping[uuid.UUID, int], bids: Sequence[Bid]) -> Selection:
        """Allocate tasks (valued by their submitters) to bidders for maximal
        welfare. A bid is for one task, and each task goes to at most one bidder."""


@runtime_checkable
class ClearingEngine(Protocol):
    def clear(self, values: Mapping[uuid.UUID, int], bids: Sequence[Bid]) -> Outcome:
        """Pick the winners and decide what each is paid."""


@runtime_checkable
class Deployer(Protocol):
    def deploy(self, task: Task, award: Award) -> str:
        """Start the task on the winner's node. Returns a handle."""


@runtime_checkable
class Verifier(Protocol):
    def verify(self, task: Task, result_hash: str | None) -> bool: ...


@runtime_checkable
class Ledger(Protocol):
    """Reputation. Written to after every settled task; nothing reads it yet."""
    def record(self, bidder_id: str, task_id: uuid.UUID, success: bool) -> None: ...


@runtime_checkable
class Notifier(Protocol):
    def auction_opened(self, auction: Auction) -> None: ...
    def auction_closed(self, auction: Auction) -> None: ...