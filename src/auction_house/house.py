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

import auction_house.domain
from auction_house import ports

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Components:
    """The ports the house depends on, grouped together so they can be swapped as a unit
    (e.g. in-memory implementations for tests, real ones in production)."""

    tasks: ports.TaskStore          # persistence of tasks
    auctions: ports.AuctionStore    # persistence of auctions
    bids: ports.BidPool             # sealed bids, one per bidder and auction
    grouper: ports.Grouper          # groups pending tasks into collections, one auction each
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
        clock: Callable[[], datetime.datetime] = auction_house.domain.utcnow,
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

    def submit_task(self, owner: str, spec: auction_house.domain.TaskSpec) -> auction_house.domain.Task:
        """Register a new task as pending. It enters an auction on the next `open_auctions`."""
        if spec.deadline <= self.clock():
            raise auction_house.domain.InvalidTask("deadline must be in the future")
        task = auction_house.domain.Task(task_id=uuid.uuid4(), owner=owner, spec=spec, submitted_at=self.clock())
        self.c.tasks.add(task)
        return task


    def get_task(self, task_id: uuid.UUID, owner: str) -> auction_house.domain.Task:
        """:3 return one of the task owner's task"""
        task = self.c.tasks.get(task_id)
        if task.owner != owner:
            raise auction_house.domain.UnknownTask(str(task_id))  # do not reveal that it exists
        return task


    def tasks_of(self, owner: str) -> list[auction_house.domain.Task]:
        """:3 return all tasks of an ownser"""
        return self.c.tasks.list(owner=owner)


    # --- the auction cycle ------------------------------------------------------

    def open_auctions(self) -> list[auction_house.domain.Auction]:
        """Group the pending tasks and open one auction per collection."""
        opened: list[auction_house.domain.Auction] = []
        with self._lock:
            # We want to drop the tasks whos deadline passed while we waited, such that they are not goruped.
            # This is of cause not so well, but they can be passed to the submitter that its deadlien passed.
            self._expire_pending()
            for collection in self.c.grouper.plan(self.c.tasks.list(status=auction_house.domain.TaskStatus.PENDING)):
                # Create an auction
                auction = auction_house.domain.Auction(
                    auction_id=uuid.uuid4(),
                    task_ids=tuple(t.task_id for t in collection),
                    closes_at=self.clock() + self.bidding_window,
                )
                # put tasks to auction
                for task in collection:
                    # `rounds` counts auctions entered; `_requeue_or_give_up` checks it against `max_rounds`.
                    self._set(task.task_id, status=auction_house.domain.TaskStatus.IN_AUCTION, rounds=task.rounds + 1,
                              auction_id=auction.auction_id)
                self.c.auctions.put(auction)
                opened.append(auction)

        # We want to notify the outside that a auction ahs opened, such that a slwo notifier cannot block other operations
        for auction in opened:
            self.c.notifier.auction_opened(auction)
        return opened


    def submit_bid(self, auction_id: uuid.UUID, bidder_id: str, request: auction_house.domain.BidRequest) -> auction_house.domain.Bid:
        """Place a sealed bid on an open auction, replacing the bidder's earlier bid
        in full. The bid lists the bundles of tasks the bidder is willing to run."""
        
        # lock auction so it cannot be claimed by other thread
        with self._lock:
            auction = self.c.auctions.get(auction_id)

            # Check stored status and deadline
            # Do not accept bids for closed auctions.
            if auction.status is not auction_house.domain.AuctionStatus.OPEN or self.clock() >= auction.closes_at:
                raise auction_house.domain.AuctionClosed(f"auction {auction_id} is not accepting bids")

            # Every task named in any bundle, flattened into one set.
            requested = set().union(*(bundle.tasks for bundle in request.bundles))

            # Check membership of the auction, as the bid model does not know of the auction it is for.
            outside = requested - set(auction.task_ids)
            if outside:
                raise auction_house.domain.InvalidBundle(f"tasks not in auction {auction_id}: {sorted(map(str, outside))}")

            # Eligibility is per task. One ineligible task rejects the whole bid.
            for task_id in requested:
                if not self.c.eligibility.is_eligible(bidder_id, self.c.tasks.get(task_id)):
                    raise auction_house.domain.IneligibleBid(f"not eligible for task {task_id}")

            # The bid is valid, so store it. 
            # The bid is sealed, so the house does not read it until clearing.
            bid = auction_house.domain.Bid(
                auction_id=auction_id,
                bidder_id=bidder_id,
                placed_at=self.clock(),
                bundles=request.bundles,
            )
            self.c.bids.put(bid)
            return bid


    def own_bid(self, auction_id: uuid.UUID, bidder_id: str) -> auction_house.domain.Bid | None:
        """:3 The bidder's own bid in the auction. 
        Bids are sealed, so there is no wayto read anyone else's."""

        self.c.auctions.get(auction_id)  # rejser UnknownAuction hvis en auction ikke findes
        bid = self.c.bids.of(auction_id, bidder_id)
        if bid is None:
            raise auction_house.domain.Nobid(f"no bid from {bidder_id} in auction {auction_id}")
        return bid


    def clear(self, auction_id: uuid.UUID, *, force: bool = False) -> auction_house.domain.Auction:
        """Clear the auction and hand the winning tasks to the deployer.

        Before `closes_at` this needs `force`, so bidders are not cut off by accident."""

        # Clear auction by running auction using the auction engine
        # Define under lock claming the auction
        with self._lock:
            auction = self.c.auctions.get(auction_id)
            if auction.status is not auction_house.domain.AuctionStatus.OPEN:
                raise auction_house.domain.AuctionClosed(f"auction {auction_id} is {auction.status}")
            if not force and self.clock() < auction.closes_at:
                raise auction_house.domain.AuctionClosed("the bidding window is still open")
            auction = self._save(auction, status=auction_house.domain.AuctionStatus.CLEARING)  # no more bids
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
                    self._set(task_id, status=auction_house.domain.TaskStatus.PENDING, rounds=task.rounds - 1, auction_id=None)
                auction = self._save(auction, status=auction_house.domain.AuctionStatus.FAILED)
            self.c.notifier.auction_closed(auction)
            raise

        # (not under lock), dispatch tasks to external systems
        # Deployment is "per task"
        handles: dict[uuid.UUID, str] = {}
        for award in outcome.awards:
            for task_id in award.task_ids:
                try:
                    handle = self.c.deployer.deploy(tasks[task_id], award.bidder_id)
                except Exception:  # one failed dispatch must not block the others
                    log.exception("deploying task %s to %s failed", task_id, award.bidder_id)
                    self._set(task_id, status=auction_house.domain.TaskStatus.FAILED, bidder_id=award.bidder_id)
                else:
                    handles[task_id] = handle
                    self._set(task_id, status=auction_house.domain.TaskStatus.EXECUTING, bidder_id=award.bidder_id, handle=handle)

        # with lock, handle that nobody won and record outcome to notifier
        with self._lock:
            for task_id in outcome.unallocated:
                self._requeue_or_give_up(tasks[task_id])
            auction = self._save(auction, status=auction_house.domain.AuctionStatus.CLEARED, outcome=outcome, handles=handles)
        self.c.notifier.auction_closed(auction)
        return auction


    def clear_due(self) -> list[auction_house.domain.Auction]:
        """Clear every open auction whose bidding window has ended."""
        with self._lock:
            due = [a.auction_id for a in self.c.auctions.all()
                   if a.status is auction_house.domain.AuctionStatus.OPEN and self.clock() >= a.closes_at]
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

    def list_auctions(self) -> list[auction_house.domain.AuctionView]:
        """Every auction as bidders see it: tasks on offer (no bids or outcomes are to be shown)"""
        return [self.view(a) for a in self.c.auctions.all()]


    def get_auction(self, auction_id: uuid.UUID) -> auction_house.domain.Auction:
        """The full auction record, including outcome. For operators; bidders use `view`."""
        return self.c.auctions.get(auction_id)


    def view(self, auction: auction_house.domain.Auction) -> auction_house.domain.AuctionView:
        """Reduce an auction to what a bidder may see. Only the resources and
        deadline of each task are exposed, not the owner or the budget."""
        offers = tuple(
            auction_house.domain.TaskOffer(task_id=t.task_id, resources=t.spec.resources, deadline=t.spec.deadline)
            for t in map(self.c.tasks.get, auction.task_ids)
        )
        return auction_house.domain.AuctionView(auction_id=auction.auction_id, status=auction.status,
                           closes_at=auction.closes_at, tasks=offers)


    def assignments_of(self, bidder_id: str) -> list[auction_house.domain.Assignment]:
        """Every task the bidder has won, across all cleared auctions."""
        return [
            auction_house.domain.Assignment(
                auction_id=a.auction_id,
                award=award,
                tasks=tuple(self.c.tasks.get(t) for t in award.task_ids),
            )
            for a in self.c.auctions.all() if a.outcome
            for award in a.outcome.awards if award.bidder_id == bidder_id
        ]


    def report_result(self, bidder_id: str, task_id: uuid.UUID, result_hash: str | None) -> auction_house.domain.Task:
        """Verify a result from the winner and settle the task."""
        with self._lock:
            task = self.c.tasks.get(task_id)

            # Only the winning bidder mayu report! And only while the task status is in EXECUTING in the auction stores
            # Prevents setting the same task twice
            if task.bidder_id != bidder_id or task.status is not auction_house.domain.TaskStatus.EXECUTING:
                raise auction_house.domain.NotAssigned(f"task {task_id} is not executing for {bidder_id}")
            accepted = self.c.verifier.verify(task, result_hash)
            self.c.ledger.record(bidder_id, task_id, accepted)
            # Now set task status to COMPLEATED or FAILED depending on verifyer in auction stores
            return self._set(task_id, status=auction_house.domain.TaskStatus.COMPLETED if accepted else auction_house.domain.TaskStatus.FAILED)


    # --- internals ------------------------------------------------------------------

    def _set(self, task_id: uuid.UUID, **changes) -> auction_house.domain.Task:
        """Apply `changes` to the stored task, persist it, and return the updated copy.
        Tasks are immutable models, so this replaces rather than mutates."""
        task = self.c.tasks.get(task_id).model_copy(update=changes)
        self.c.tasks.update(task)
        return task


    def _save(self, auction: auction_house.domain.Auction, **changes) -> auction_house.domain.Auction:
        """Apply `changes` to an auction, persist the copy, and return it."""
        auction = auction.model_copy(update=changes)
        self.c.auctions.put(auction)
        return auction


    def _expire_pending(self) -> None:
        """Mark pending tasks whose deadline has passed as expired."""
        for task in self.c.tasks.list(status=auction_house.domain.TaskStatus.PENDING):
            if task.spec.deadline <= self.clock():
                self._set(task.task_id, status=auction_house.domain.TaskStatus.EXPIRED)


    def _requeue_or_give_up(self, task: auction_house.domain.Task) -> None:
        """No winning bid this round: try again in the next auction, a few times."""
        retry = task.rounds < self.max_rounds and task.spec.deadline > self.clock()
        self._set(task.task_id, status=auction_house.domain.TaskStatus.PENDING if retry else auction_house.domain.TaskStatus.UNALLOCATED)
