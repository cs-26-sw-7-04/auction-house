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
    Assignment,
    Auction,
    AuctionClosed,
    AuctionStatus,
    AuctionView,
    Bid,
    BidRequest,
    IneligibleBid,
    InvalidBid,
    InvalidTask,
    NotAssigned,
    Task,
    TaskOffer,
    TaskSpec,
    TaskStatus,
    UnknownTask,
    utcnow,
)

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Components:
    """The ports the house depends on, bundled so they can be swapped as a unit
    (e.g. in-memory implementations for tests, real ones in production)."""

    tasks: ports.TaskStore          # persistence of tasks
    auctions: ports.AuctionStore    # persistence of auctions
    bids: ports.BidPool             # sealed bids, one per bidder and task
    bundler: ports.Bundler          # groups pending tasks into collections, one auction each
    eligibility: ports.Eligibility  # decides whether a bidder may bid on a task
    engine: ports.ClearingEngine    # decides winners and prices from the bids
    deployer: ports.Deployer        # starts a won task on the winner's infrastructure
    verifier: ports.Verifier        # checks a reported result
    ledger: ports.Ledger            # records whether each bidder delivered
    notifier: ports.Notifier        # outbound events (auction opened / closed)


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
        """
        `bidding_window`: how long an auction accepts bids after it opens.
        `max_rounds`: how many auctions a task may enter before it is given up on.
        `clock`: source of the current time. Injectable / can be interfaced.
        """
        self.c = components
        self.bidding_window = bidding_window
        self.max_rounds = max_rounds
        self.clock = clock
        # Multiple ivvocatiosn of the auctionhosue should be able to run concurrently
        # Methods that hold the lock can call helpers that take it
        self._lock = threading.RLock()

    # --- submitters -----------------------------------------------------------

    def submit_task(self, owner: str, spec: TaskSpec) -> Task:
        """Register a new task as pending. It enters an auction on the next `open_auctions`."""
        if spec.deadline <= self.clock():
            raise InvalidTask("deadline must be in the future")
        task = Task(task_id=uuid.uuid4(), owner=owner, spec=spec, submitted_at=self.clock())
        self.c.tasks.add(task)
        return task


    def get_task(self, task_id: uuid.UUID, owner: str) -> Task:
        """:3 return one of the task owner's task"""
        task = self.c.tasks.get(task_id)
        if task.owner != owner:
            raise UnknownTask(str(task_id))  # do not reveal that it exists
        return task

    def tasks_of(self, owner: str) -> list[Task]:
        """:3 return all tasks of an ownser"""
        return self.c.tasks.list(owner=owner)

    # --- the auction cycle ------------------------------------------------------

    def open_auctions(self) -> list[Auction]:
        """Bundle the pending tasks and open one auction per collection."""
        opened: list[Auction] = []
        with self._lock:
            # We want to drop the tasks whos deadline passed while we waited, such that they are not bundled.
            # This is of cause not so well, but they can be passed to the submitter that its deadlien passed.
            self._expire_pending()
            for collection in self.c.bundler.plan(self.c.tasks.list(status=TaskStatus.PENDING)):
                # Create an auction
                auction = Auction(
                    auction_id=uuid.uuid4(),
                    task_ids=tuple(t.task_id for t in collection),
                    closes_at=self.clock() + self.bidding_window,
                )
                # put tasks to auction
                for task in collection:
                    # `rounds` counts auctions entered; `_requeue_or_give_up` checks it against `max_rounds`.
                    self._set(task.task_id, status=TaskStatus.IN_AUCTION, rounds=task.rounds + 1,
                              auction_id=auction.auction_id)
                self.c.auctions.put(auction)
                opened.append(auction)

        # We want to notify the outside that a auction ahs opened, such that a slwo notifier cannot block other operations
        for auction in opened:
            self.c.notifier.auction_opened(auction)
        return opened


    def submit_bid(self, auction_id: uuid.UUID, task_id: uuid.UUID, bidder_id: str, request: BidRequest) -> Bid:
        """:3 Place a bid on one task of an open auction, replacing the bidder's earlier
        bid on that task. A bidder can bid on any number of the auction's tasks.
        """

        with self._lock:
            auction = self.c.auctions.get(auction_id)
            # Check both the stored status and the clock: the status only changes
            # when someone clears the auction, which may happen after `closes_at`.
            if auction.status is not AuctionStatus.OPEN or self.clock() >= auction.closes_at:
                raise AuctionClosed(f"auction {auction_id} is not accepting bids")
            if task_id not in auction.task_ids:
                raise InvalidBid(f"task {task_id} is not in auction {auction_id}")
            if not self.c.eligibility.is_eligible(bidder_id, self.c.tasks.get(task_id)):
                raise IneligibleBid(f"not eligible for task {task_id}")
            bid = Bid(task_id=task_id, bidder_id=bidder_id, placed_at=self.clock(), **request.model_dump())
            self.c.bids.put(auction_id, bid)
            return bid


    def own_bids(self, auction_id: uuid.UUID, bidder_id: str) -> Bid | None:
        """:3 The bidder's own bids in the auction. Bids are sealed, so there is no way
        to read anyone else's."""

        self.c.auctions.get(auction_id)  # rejser en error hvis en auction ikke findes
        return self.c.bids.of(auction_id, bidder_id)


    def clear(self, auction_id: uuid.UUID, *, force: bool = False) -> Auction:
        """Clear the auction and hand the winning tasks to the deployer.

        Before `closes_at` this needs `force`, so bidders are not cut off by accident."""

        # Clear auction by running auction using the auction engine
        # Define under lock claming the auction
        with self._lock:
            auction = self.c.auctions.get(auction_id)
            if auction.status is not AuctionStatus.OPEN:
                raise AuctionClosed(f"auction {auction_id} is {auction.status}")
            if not force and self.clock() < auction.closes_at:
                raise AuctionClosed("the bidding window is still open")
            auction = self._save(auction, status=AuctionStatus.CLEARING)  # no more bids
            tasks = {t: self.c.tasks.get(t) for t in auction.task_ids}
            bids = self.c.bids.all(auction_id)

        # Run the auction engine (not under lock). 
        # Setting auctio nstatus to CLEARING, such that no others can commence the auction
        try:
            outcome = self.c.engine.clear({t: task.spec.max_budget for t, task in tasks.items()}, bids)
        except Exception:
            # It faild, so we want to undo the auction claim (PENDING), and let someone else to it.
            with self._lock:
                for task_id, task in tasks.items():
                    self._set(task_id, status=TaskStatus.PENDING, rounds=task.rounds - 1, auction_id=None)
                auction = self._save(auction, status=AuctionStatus.FAILED)
            self.c.notifier.auction_closed(auction)
            raise

        # (not under lock), dispatch tasks to external systems
        handles: dict[uuid.UUID, str] = {}
        for award in outcome.awards:
            try:
                handle = self.c.deployer.deploy(tasks[award.task_id], award)
            except Exception:  # one failed dispatch must not block the other winners
                log.exception("deploying task %s to %s failed", award.task_id, award.bidder_id)
                self._set(award.task_id, status=TaskStatus.FAILED, bidder_id=award.bidder_id)
            else:
                handles[award.task_id] = handle
                self._set(award.task_id, status=TaskStatus.EXECUTING, bidder_id=award.bidder_id, handle=handle)

        
        # with lock, handle that nobody won and record outcome to notifier
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
                # One broken auction must not stop the others from being cleared.
                log.exception("clearing auction %s failed", auction_id)
        return cleared

    def tick(self) -> None:
        """One round of housekeeping; what the optional timer runs."""
        self.open_auctions()
        self.clear_due()

    # --- bidders ------------------------------------------------------------------

    def list_auctions(self) -> list[AuctionView]:
        """Every auction as bidders see it: tasks on offer (no bids or outcomes are to be shown)"""
        return [self.view(a) for a in self.c.auctions.all()]

    def get_auction(self, auction_id: uuid.UUID) -> Auction:
        """The full auction record, including outcome. For operators; bidders use `view`."""
        return self.c.auctions.get(auction_id)

    def view(self, auction: Auction) -> AuctionView:
        """Reduce an auction to what a bidder may see. Only the resources and
        deadline of each task are exposed, not the owner or the budget."""
        offers = tuple(
            TaskOffer(task_id=t.task_id, resources=t.spec.resources, deadline=t.spec.deadline)
            for t in map(self.c.tasks.get, auction.task_ids)
        )
        return AuctionView(auction_id=auction.auction_id, status=auction.status,
                           closes_at=auction.closes_at, tasks=offers)

    def assignments_of(self, bidder_id: str) -> list[Assignment]:
        """Every task the bidder has won, across all cleared auctions."""
        return [
            Assignment(auction_id=a.auction_id, award=award, task=self.c.tasks.get(award.task_id))
            for a in self.c.auctions.all() if a.outcome
            for award in a.outcome.awards if award.bidder_id == bidder_id
        ]

    def report_result(self, bidder_id: str, task_id: uuid.UUID, result_hash: str | None) -> Task:
        """Verify a result from the winner and settle the task."""
        with self._lock:
            task = self.c.tasks.get(task_id)

            # Only the winning bidder mayu report! And only while the task status is in EXECUTING in the auction stores
            # Prevents setting the same task twice
            if task.bidder_id != bidder_id or task.status is not TaskStatus.EXECUTING:
                raise NotAssigned(f"task {task_id} is not executing for {bidder_id}")
            accepted = self.c.verifier.verify(task, result_hash)
            self.c.ledger.record(bidder_id, task_id, accepted)
            # Now set task status to COMPLEATED or FAILED depending on verifyer in auction stores
            return self._set(task_id, status=TaskStatus.COMPLETED if accepted else TaskStatus.FAILED)

    # --- internals ------------------------------------------------------------------

    def _set(self, task_id: uuid.UUID, **changes) -> Task:
        """Apply `changes` to the stored task, persist it, and return the updated copy.
        Tasks are immutable models, so this replaces rather than mutates."""
        task = self.c.tasks.get(task_id).model_copy(update=changes)
        self.c.tasks.update(task)
        return task

    def _save(self, auction: Auction, **changes) -> Auction:
        """Apply `changes` to an auction, persist the copy, and return it."""
        auction = auction.model_copy(update=changes)
        self.c.auctions.put(auction)
        return auction

    def _expire_pending(self) -> None:
        """Mark pending tasks whose deadline has passed as expired."""
        for task in self.c.tasks.list(status=TaskStatus.PENDING):
            if task.spec.deadline <= self.clock():
                self._set(task.task_id, status=TaskStatus.EXPIRED)

    def _requeue_or_give_up(self, task: Task) -> None:
        """No winning bid this round: try again in the next auction, a few times."""
        retry = task.rounds < self.max_rounds and task.spec.deadline > self.clock()
        self._set(task.task_id, status=TaskStatus.PENDING if retry else TaskStatus.UNALLOCATED)
