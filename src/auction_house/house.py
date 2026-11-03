"""The auction house: the one place where the flow of an auction is written down.

It owns no storage and makes no assumptions about how auctions are cleared or
tasks run; everything it needs comes in as a port (see `ports.py`).
"""
import datetime
import logging
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass

from auction_house import ports
from auction_house.domain import (
    Assignment, Auction, AuctionClosed, AuctionStatus, AuctionView, Bid, BidRequest, IneligibleBid,
    InvalidTask, NotAssigned, Task, TaskOffer, TaskSpec, TaskStatus, UnknownTask, utcnow,
)

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Components:
    tasks: ports.TaskStore
    auctions: ports.AuctionStore
    bids: ports.BidPool
    bundler: ports.Bundler
    eligibility: ports.Eligibility
    engine: ports.ClearingEngine
    deployer: ports.Deployer
    verifier: ports.Verifier
    ledger: ports.Ledger
    notifier: ports.Notifier


class AuctionHouse:
    """Thread-safe. State changes happen under a lock; the lock is *not* held
    while the engine solves or the deployer talks to a cluster."""

    def __init__(
        self,
        components: Components,
        *,
        bidding_window: datetime.timedelta = datetime.timedelta(minutes=1),
        max_rounds: int = 3,
        clock: Callable[[], datetime.datetime] = utcnow,
    ):
        self.c = components
        self.bidding_window = bidding_window
        self.max_rounds = max_rounds
        self.clock = clock
        self._lock = threading.RLock()

    # --- submitters -----------------------------------------------------------

    def submit_task(self, owner: str, spec: TaskSpec) -> Task:
        if spec.deadline <= self.clock():
            raise InvalidTask("deadline must be in the future")
        task = Task(task_id=uuid.uuid4(), owner=owner, spec=spec, submitted_at=self.clock())
        self.c.tasks.add(task)
        return task

    def get_task(self, task_id: uuid.UUID, owner: str) -> Task:
        task = self.c.tasks.get(task_id)
        if task.owner != owner:
            raise UnknownTask(str(task_id))  # do not reveal that it exists
        return task

    def tasks_of(self, owner: str) -> list[Task]:
        return self.c.tasks.list(owner=owner)

    # --- the auction cycle ------------------------------------------------------

    def open_auctions(self) -> list[Auction]:
        """Bundle the pending tasks and open one auction per collection."""
        opened: list[Auction] = []
        with self._lock:
            self._expire_pending()
            for collection in self.c.bundler.plan(self.c.tasks.list(status=TaskStatus.PENDING)):
                auction = Auction(
                    auction_id=uuid.uuid4(),
                    task_ids=tuple(t.task_id for t in collection),
                    closes_at=self.clock() + self.bidding_window,
                )
                for task in collection:
                    self._set(task.task_id, status=TaskStatus.IN_AUCTION, rounds=task.rounds + 1,
                              auction_id=auction.auction_id)
                self.c.auctions.put(auction)
                opened.append(auction)
        for auction in opened:
            self.c.notifier.auction_opened(auction)
        return opened

    def submit_bid(self, auction_id: uuid.UUID, bidder_id: str, request: BidRequest) -> Bid:
        with self._lock:
            auction = self.c.auctions.get(auction_id)
            if auction.status is not AuctionStatus.OPEN or self.clock() >= auction.closes_at:
                raise AuctionClosed(f"auction {auction_id} is not accepting bids")
            for task_id in auction.task_ids:
                if not self.c.eligibility.is_eligible(bidder_id, self.c.tasks.get(task_id)):
                    raise IneligibleBid(f"not eligible for task {task_id}")
            bid = Bid(bidder_id=bidder_id, placed_at=self.clock(), **request.model_dump())
            self.c.bids.put(auction_id, bid)
            return bid

    def own_bid(self, auction_id: uuid.UUID, bidder_id: str) -> Bid | None:
        self.c.auctions.get(auction_id)
        return self.c.bids.get(auction_id, bidder_id)

    def clear(self, auction_id: uuid.UUID, *, force: bool = False) -> Auction:
        """Clear the auction and hand the winning tasks to the deployer.

        Before `closes_at` this needs `force`, so bidders are not cut off by accident."""
        with self._lock:
            auction = self.c.auctions.get(auction_id)
            if auction.status is not AuctionStatus.OPEN:
                raise AuctionClosed(f"auction {auction_id} is {auction.status}")
            if not force and self.clock() < auction.closes_at:
                raise AuctionClosed("the bidding window is still open")
            auction = self._save(auction, status=AuctionStatus.CLEARING)  # no more bids
            tasks = {t: self.c.tasks.get(t) for t in auction.task_ids}
            bids = self.c.bids.all(auction_id)

        try:
            outcome = self.c.engine.clear({t: task.spec.max_budget for t, task in tasks.items()}, bids)
        except Exception:
            with self._lock:
                for task_id, task in tasks.items():
                    self._set(task_id, status=TaskStatus.PENDING, rounds=task.rounds - 1, auction_id=None)
                auction = self._save(auction, status=AuctionStatus.FAILED)
            self.c.notifier.auction_closed(auction)
            raise

        handles: dict[uuid.UUID, str] = {}
        for award in outcome.awards:
            for task_id in award.task_ids:
                try:
                    handle = self.c.deployer.deploy(tasks[task_id], award)
                except Exception:  # one failed dispatch must not block the other winners
                    log.exception("deploying task %s to %s failed", task_id, award.bidder_id)
                    self._set(task_id, status=TaskStatus.FAILED, bidder_id=award.bidder_id)
                else:
                    handles[task_id] = handle
                    self._set(task_id, status=TaskStatus.EXECUTING, bidder_id=award.bidder_id, handle=handle)
        with self._lock:
            for task_id in outcome.unallocated:
                self._requeue_or_give_up(tasks[task_id])
            auction = self._save(auction, status=AuctionStatus.CLEARED, outcome=outcome, handles=handles)
        self.c.notifier.auction_closed(auction)
        return auction

    def clear_due(self) -> list[Auction]:
        """Clear every open auction whose bidding window has ended."""
        with self._lock:
            due = [a.auction_id for a in self.c.auctions.all()
                   if a.status is AuctionStatus.OPEN and self.clock() >= a.closes_at]
        cleared = []
        for auction_id in due:
            try:
                cleared.append(self.clear(auction_id))
            except Exception:
                log.exception("clearing auction %s failed", auction_id)
        return cleared

    def tick(self) -> None:
        """One round of housekeeping; what the optional timer runs."""
        self.open_auctions()
        self.clear_due()

    # --- bidders ------------------------------------------------------------------

    def list_auctions(self) -> list[AuctionView]:
        return [self.view(a) for a in self.c.auctions.all()]

    def get_auction(self, auction_id: uuid.UUID) -> Auction:
        return self.c.auctions.get(auction_id)

    def view(self, auction: Auction) -> AuctionView:
        offers = tuple(
            TaskOffer(task_id=t.task_id, resources=t.spec.resources, deadline=t.spec.deadline)
            for t in map(self.c.tasks.get, auction.task_ids)
        )
        return AuctionView(auction_id=auction.auction_id, status=auction.status,
                           closes_at=auction.closes_at, tasks=offers)

    def assignments_of(self, bidder_id: str) -> list[Assignment]:
        return [
            Assignment(auction_id=a.auction_id, award=award,
                       tasks=tuple(self.c.tasks.get(t) for t in award.task_ids))
            for a in self.c.auctions.all() if a.outcome
            for award in a.outcome.awards if award.bidder_id == bidder_id
        ]

    def report_result(self, bidder_id: str, task_id: uuid.UUID, result_hash: str | None) -> Task:
        """Verify a result from the winner and settle the task."""
        with self._lock:
            task = self.c.tasks.get(task_id)
            if task.bidder_id != bidder_id or task.status is not TaskStatus.EXECUTING:
                raise NotAssigned(f"task {task_id} is not executing for {bidder_id}")
            accepted = self.c.verifier.verify(task, result_hash)
            self.c.ledger.record(bidder_id, task_id, accepted)
            return self._set(task_id, status=TaskStatus.COMPLETED if accepted else TaskStatus.FAILED)

    # --- internals ------------------------------------------------------------------

    def _set(self, task_id: uuid.UUID, **changes) -> Task:
        task = self.c.tasks.get(task_id).model_copy(update=changes)
        self.c.tasks.update(task)
        return task

    def _save(self, auction: Auction, **changes) -> Auction:
        auction = auction.model_copy(update=changes)
        self.c.auctions.put(auction)
        return auction

    def _expire_pending(self) -> None:
        for task in self.c.tasks.list(status=TaskStatus.PENDING):
            if task.spec.deadline <= self.clock():
                self._set(task.task_id, status=TaskStatus.EXPIRED)

    def _requeue_or_give_up(self, task: Task) -> None:
        """No winning bid this round: try again in the next auction, a few times."""
        retry = task.rounds < self.max_rounds and task.spec.deadline > self.clock()
        self._set(task.task_id, status=TaskStatus.PENDING if retry else TaskStatus.UNALLOCATED)
