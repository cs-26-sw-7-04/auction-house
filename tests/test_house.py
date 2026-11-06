"""Business-logic tests of the auction flow, through the house's public methods."""
import datetime
from dataclasses import replace

import pytest

from auction_house.bootstrap import build_house
from auction_house.config import Settings
from auction_house.domain import (
    AuctionClosed,
    BidRequest,
    IneligibleBid,
    InvalidBid,
    InvalidTask,
    NotAssigned,
    SolverError,
    TaskSpec,
    TaskStatus,
    UnknownTask,
    utcnow,
)
from auction_house.plugins import ComponentSpec


class Clock:
    def __init__(self):
        self.now = utcnow()

    def __call__(self):
        return self.now

    def advance(self, **kw):
        self.now += datetime.timedelta(**kw)


def spec(budget: int = 100, **kw) -> TaskSpec:
    return TaskSpec(image="registry/job:1", deadline=utcnow() + datetime.timedelta(hours=1), max_budget=budget, **kw)


def place(house, auction, bidder: str, prices: dict) -> None:
    """Bid `bidder` places on each task in {task_id: price}."""
    for task_id, price in prices.items():
        house.submit_bid(auction.auction_id, task_id, bidder, BidRequest(price=price))


@pytest.fixture
def house():
    settings = Settings(_env_file=None, bundler=ComponentSpec(name="batch", options={"size": 2}))
    house = build_house(settings)
    house.clock = Clock()
    return house


# --- bidding ----------------------------------------------------------------------

def test_a_bidder_can_bid_on_several_tasks_and_rebidding_replaces_only_that_task(house):
    t1, t2 = (house.submit_task("s", spec()) for _ in range(2))
    (auction,) = house.open_auctions()
    place(house, auction, "a", {t1.task_id: 20, t2.task_id: 20})
    place(house, auction, "a", {t1.task_id: 5})
    prices = {b.task_id: b.price for b in house.own_bids(auction.auction_id, "a")}
    assert prices == {t1.task_id: 5, t2.task_id: 20}


def test_own_bids_are_only_the_callers(house):
    task = house.submit_task("s", spec())
    (auction,) = house.open_auctions()
    place(house, auction, "a", {task.task_id: 10})
    place(house, auction, "b", {task.task_id: 20})
    assert [b.bidder_id for b in house.own_bids(auction.auction_id, "a")] == ["a"]
    assert house.own_bids(auction.auction_id, "nobody") == []


def test_a_bid_on_a_task_outside_the_auction_is_rejected(house):
    for _ in range(3):
        house.submit_task("s", spec())
    first, second = house.open_auctions()
    with pytest.raises(InvalidBid):
        house.submit_bid(first.auction_id, second.task_ids[0], "a", BidRequest(price=1))


def test_ineligibility_is_per_task(house):
    t1, t2 = (house.submit_task("s", spec()) for _ in range(2))

    class NotForFirstTask:
        def is_eligible(self, bidder_id, task):
            return task.task_id != t1.task_id

    house.c = replace(house.c, eligibility=NotForFirstTask())
    (auction,) = house.open_auctions()
    with pytest.raises(IneligibleBid):
        house.submit_bid(auction.auction_id, t1.task_id, "a", BidRequest(price=1))
    house.submit_bid(auction.auction_id, t2.task_id, "a", BidRequest(price=1))


def test_a_closed_auction_refuses_bids(house):
    task = house.submit_task("s", spec())
    (auction,) = house.open_auctions()
    house.clock.advance(minutes=2)
    with pytest.raises(AuctionClosed):
        house.submit_bid(auction.auction_id, task.task_id, "a", BidRequest(price=1))


def test_a_bid_above_the_budget_is_accepted_but_cannot_win(house):
    task = house.submit_task("s", spec(50))
    (auction,) = house.open_auctions()
    # Accepted without error: rejecting it would reveal the budget to bidders.
    house.submit_bid(auction.auction_id, task.task_id, "a", BidRequest(price=80))
    house.clock.advance(minutes=2)
    house.clear(auction.auction_id)
    assert house.get_task(task.task_id, "s").status is TaskStatus.PENDING


# --- clearing ---------------------------------------------------------------------

def test_full_round(house):
    for budget in (100, 80, 5):
        house.submit_task("s", spec(budget))
    first, _ = house.open_auctions()
    for task_id in first.task_ids:
        assert house.get_task(task_id, "s").status is TaskStatus.IN_AUCTION

    place(house, first, "a", {task_id: 10 for task_id in first.task_ids})
    with pytest.raises(AuctionClosed):
        house.clear(first.auction_id)  # window still open

    house.clock.advance(minutes=2)
    cleared = house.clear(first.auction_id)
    assert {award.bidder_id for award in cleared.outcome.awards} == {"a"}
    for task_id in first.task_ids:
        task = house.get_task(task_id, "s")
        assert (task.status, task.bidder_id) == (TaskStatus.EXECUTING, "a")
    assert {a.task.task_id for a in house.assignments_of("a")} == set(first.task_ids)
    assert house.assignments_of("b") == []


def test_each_task_goes_to_its_cheapest_bidder(house):
    t1, t2 = (house.submit_task("s", spec()) for _ in range(2))
    (auction,) = house.open_auctions()
    place(house, auction, "a", {t1.task_id: 10, t2.task_id: 50})
    place(house, auction, "b", {t1.task_id: 40, t2.task_id: 20})
    house.clock.advance(minutes=2)
    house.clear(auction.auction_id)
    assert house.get_task(t1.task_id, "s").bidder_id == "a"
    assert house.get_task(t2.task_id, "s").bidder_id == "b"


def test_tasks_nobody_bid_on_are_requeued_while_the_others_run(house):
    t1, t2 = (house.submit_task("s", spec()) for _ in range(2))
    (auction,) = house.open_auctions()
    place(house, auction, "a", {t1.task_id: 10})
    house.clock.advance(minutes=2)
    house.clear(auction.auction_id)
    assert house.get_task(t1.task_id, "s").status is TaskStatus.EXECUTING
    assert house.get_task(t2.task_id, "s").status is TaskStatus.PENDING


def test_unwon_tasks_are_retried_then_given_up(house):
    task = house.submit_task("s", spec(5))
    for round_ in range(1, 4):
        (auction,) = house.open_auctions()
        house.clock.advance(minutes=2)
        house.clear(auction.auction_id)
        expected = TaskStatus.PENDING if round_ < 3 else TaskStatus.UNALLOCATED
        assert house.get_task(task.task_id, "s").status is expected
    assert house.open_auctions() == []


def test_a_failing_engine_returns_tasks_to_pending(house):
    class Broken:
        def clear(self, values, bids):
            raise SolverError("too big")

    house.c = replace(house.c, engine=Broken())
    task = house.submit_task("s", spec())
    (auction,) = house.open_auctions()
    house.clock.advance(minutes=2)
    with pytest.raises(SolverError):
        house.clear(auction.auction_id)
    after = house.get_task(task.task_id, "s")
    assert (after.status, after.rounds) == (TaskStatus.PENDING, 0)


# --- tasks and results ------------------------------------------------------------

def test_pending_tasks_expire_at_their_deadline(house):
    task = house.submit_task("s", spec())
    house.clock.advance(hours=2)
    assert house.open_auctions() == []
    assert house.get_task(task.task_id, "s").status is TaskStatus.EXPIRED


def test_input_checks(house):
    with pytest.raises(InvalidTask):
        house.submit_task("s", spec().model_copy(update={"deadline": utcnow() - datetime.timedelta(seconds=1)}))
    with pytest.raises(ValueError):
        TaskSpec(image="x", deadline=utcnow(), max_budget=1, verification="hash")

    task = house.submit_task("s", spec())
    with pytest.raises(UnknownTask):
        house.get_task(task.task_id, "someone-else")


def test_results_are_verified_and_only_taken_from_the_winner(house):
    good = "a" * 64
    task = house.submit_task("s", spec(verification="hash", expected_result_hash=good))
    (auction,) = house.open_auctions()
    place(house, auction, "a", {task.task_id: 1})
    house.clock.advance(minutes=2)
    house.clear(auction.auction_id)

    with pytest.raises(NotAssigned):
        house.report_result("b", task.task_id, good)
    assert house.report_result("a", task.task_id, "b" * 64).status is TaskStatus.FAILED
    with pytest.raises(NotAssigned):
        house.report_result("a", task.task_id, good)
