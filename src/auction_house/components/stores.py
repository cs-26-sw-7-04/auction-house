"""In-memory stores. Swap for a database by implementing the same ports."""
import threading
import uuid
from collections import defaultdict

from auction_house import plugins
from auction_house.domain import (
    Auction,
    Bid,
    Task,
    TaskStatus,
    UnknownAuction,
    UnknownTask,
)

# TODO: Reimplement another port `stores_redis.py` using redis in memory database
# This in not a requirement


@plugins.tasks.register("memory")
class InMemoryTaskStore:
    def __init__(self):
        self._tasks: dict[uuid.UUID, Task] = {}
        self._lock = threading.Lock() # for locking the memory store when adding, updating or listing tasks

    def add(self, task: Task) -> None:
        """:3"""
        with self._lock:
            self._tasks[task.task_id] = task

    def get(self, task_id: uuid.UUID) -> Task:
        """:3"""
        try:
            return self._tasks[task_id]
        except KeyError:
            raise UnknownTask(str(task_id)) from None

    def update(self, task: Task) -> None:
        """:3"""
        self.get(task.task_id)
        self.add(task)

    def list(self, *, status: TaskStatus | None = None, owner: str | None = None) -> list[Task]:
        """:3"""
        with self._lock:
            tasks = list(self._tasks.values())
        return [t for t in tasks if (status is None or t.status == status) and (owner is None or t.owner == owner)]


@plugins.auctions.register("memory")
class InMemoryAuctionStore:
    def __init__(self):
        self._auctions: dict[uuid.UUID, Auction] = {}
        self._lock = threading.Lock() # for locking the memory store when adding, updating or listing auctions

    def put(self, auction: Auction) -> None:
        """:3"""
        with self._lock:
            self._auctions[auction.auction_id] = auction

    def get(self, auction_id: uuid.UUID) -> Auction:
        """:3"""
        with self._lock:
            try:
                return self._auctions[auction_id]
            except KeyError:
                raise UnknownAuction(str(auction_id)) from None

    def all(self) -> list[Auction]:
        """:3"""
        with self._lock:
            return list(self._auctions.values())


@plugins.bids.register("memory")
class InMemoryBidPool:
    """Bids kept in memory: one per bidder in each auction."""

    def __init__(self):
        # auction -> bidder -> bid
        self._bids: defaultdict[uuid.UUID, dict[str, Bid]] = defaultdict(dict)
        # `own_bid` reads without the house's lock, so the pool guards its own state.
        self._lock = threading.Lock()

    def put(self, bid: Bid) -> None:
        """:3 Store the bid, replacing any earlier bid by the same bidder in the same auction."""
        with self._lock:
            self._bids[bid.auction_id][bid.bidder_id] = bid

    def of(self, auction_id: uuid.UUID, bidder_id: str) -> Bid | None:
        """:3 The bidder's bid in the auction, or None if they have not bid."""
        with self._lock:
            return self._bids.get(auction_id, {}).get(bidder_id)

    def all(self, auction_id: uuid.UUID) -> list[Bid]:
        """:3 Every bid in the auction. The house reads this only when it clears."""
        with self._lock:
            return list(self._bids.get(auction_id, {}).values())
