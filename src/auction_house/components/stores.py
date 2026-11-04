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


@plugins.tasks.register("memory")
class InMemoryTaskStore:
    def __init__(self):
        self._tasks: dict[uuid.UUID, Task] = {}
        self._lock = threading.Lock()

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

    def put(self, auction: Auction) -> None:
        self._auctions[auction.auction_id] = auction

    def get(self, auction_id: uuid.UUID) -> Auction:
        try:
            return self._auctions[auction_id]
        except KeyError:
            raise UnknownAuction(str(auction_id)) from None

    def all(self) -> list[Auction]:
        return list(self._auctions.values())


@plugins.bids.register("memory")
class InMemoryBidPool:
    def __init__(self):
        self._bids: defaultdict[uuid.UUID, dict[str, Bid]] = defaultdict(dict)

    def put(self, auction_id: uuid.UUID, bid: Bid) -> None:
        self._bids[auction_id][bid.bidder_id] = bid

    def get(self, auction_id: uuid.UUID, bidder_id: str) -> Bid | None:
        return self._bids[auction_id].get(bidder_id)

    def all(self, auction_id: uuid.UUID) -> list[Bid]:
        return list(self._bids[auction_id].values())
