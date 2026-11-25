"""Business-logic tests of allocation and payments: solvers and clearing engines."""
import random
import uuid

import pytest

from auction_house.components.solver_c_vcg_old import DEFAULT_LIBRARY, OldCVcgSolver
from auction_house.components.engines import PayAsBidEngine, VcgEngine
from auction_house.components.solver_brute_force import BruteForceSolver
from auction_house.domain import Bid, utcnow

SOLVERS = [
    pytest.param(BruteForceSolver, id="brute-force"),
    pytest.param(OldCVcgSolver, id="c", marks=pytest.mark.skipif(not DEFAULT_LIBRARY.exists(), reason="C library not built")),
]


def bid(bidder: str, task: uuid.UUID, price: int) -> Bid:
    """Bid fake"""
    return Bid(task_id=task, bidder_id=bidder, price=price, placed_at=utcnow())


def values(*vs: int) -> dict[uuid.UUID, int]:
    """Value creator"""
    return {uuid.uuid4(): v for v in vs}


# --- solving ----------------------------------------------------------------------

@pytest.mark.parametrize("solver", SOLVERS)
def test_each_task_goes_to_its_cheapest_bid(solver):
    vs = values(100, 90)
    t1, t2 = vs
    bids = [bid("a", t1, 10), bid("a", t2, 50), bid("b", t1, 40), bid("b", t2, 20)]
    selection = solver().solve(vs, bids)
    assert selection.assignment == {t1: "a", t2: "b"}
    assert selection.welfare == (100 - 10) + (90 - 20)


@pytest.mark.parametrize("solver", SOLVERS)
def test_a_task_is_not_allocated_when_every_bid_is_above_its_value(solver):
    vs = values(100)
    (task,) = vs
    selection = solver().solve(vs, [bid("a", task, 120)])
    assert selection.assignment == {}
    assert selection.welfare == 0


def test_c_and_sorted_solvers_agree():
    if not DEFAULT_LIBRARY.exists():
        pytest.skip("C library not built")
    rng = random.Random(1)
    for _ in range(25):
        vs = values(*(rng.randint(1, 100) for _ in range(rng.randint(1, 5))))
        bids = [bid(f"b{i}", task, rng.randint(0, 80)) for i in range(rng.randint(1, 3)) for task in vs]
        assert CVcgSolver().solve(vs, bids).welfare == SortedSolver().solve(vs, bids).welfare


# --- payments ---------------------------------------------------------------------

@pytest.mark.parametrize("solver", SOLVERS)
def test_vcg_with_one_task_is_a_second_price_auction(solver):
    vs = values(100)
    (task,) = vs
    outcome = VcgEngine(solver()).clear(vs, [bid("a", task, 30), bid("b", task, 50)])
    (award,) = outcome.awards
    assert (award.bidder_id, award.payment) == ("a", 50)


@pytest.mark.parametrize("solver", SOLVERS)
def test_vcg_payment_is_capped_at_the_value_of_the_task(solver):
    vs = values(100)
    (task,) = vs
    outcome = VcgEngine(solver()).clear(vs, [bid("a", task, 30), bid("b", task, 120)])
    (award,) = outcome.awards
    assert (award.bidder_id, award.payment) == ("a", 100)


@pytest.mark.parametrize("solver", SOLVERS)
def test_vcg_pays_the_second_price_on_each_task(solver):
    vs = values(100, 90)
    t1, t2 = vs
    bids = [bid("a", t1, 10), bid("a", t2, 60), bid("b", t1, 40), bid("b", t2, 20)]
    outcome = VcgEngine(solver()).clear(vs, bids)
    assert {(a.task_id, a.bidder_id, a.payment) for a in outcome.awards} == {(t1, "a", 40), (t2, "b", 60)}
    assert not outcome.unallocated


@pytest.mark.parametrize("solver", SOLVERS)
def test_a_bidder_winning_several_tasks_gets_one_award_per_task(solver):
    vs = values(100, 90)
    t1, t2 = vs
    bids = [bid("a", t1, 10), bid("a", t2, 10), bid("b", t1, 40), bid("b", t2, 50)]
    outcome = VcgEngine(solver()).clear(vs, bids)
    assert {(a.task_id, a.bidder_id, a.payment) for a in outcome.awards} == {(t1, "a", 40), (t2, "a", 50)}


@pytest.mark.parametrize("solver", SOLVERS)
def test_tasks_without_a_winning_bid_are_unallocated(solver):
    vs = values(100, 5)
    t1, t2 = vs
    outcome = VcgEngine(solver()).clear(vs, [bid("a", t1, 10), bid("a", t2, 10)])
    assert [a.task_id for a in outcome.awards] == [t1]
    assert outcome.unallocated == (t2,)


@pytest.mark.parametrize("solver", SOLVERS)
def test_pay_as_bid_pays_the_ask(solver):
    vs = values(100)
    (task,) = vs
    (award,) = PayAsBidEngine(solver()).clear(vs, [bid("a", task, 30), bid("b", task, 50)]).awards
    assert award.payment == 30


def test_truthful_bidding_is_never_worse_under_vcg():
    rng = random.Random(7)
    engine = VcgEngine(SortedSolver())
    for _ in range(200):
        vs = values(*(rng.randint(1, 100) for _ in range(rng.randint(1, 5))))
        tasks = list(vs)
        others = [bid(f"o{i}", task, rng.randint(0, 80)) for i in range(2) for task in tasks]
        cost = {task: rng.randint(0, 80) for task in tasks}

        def profit(asks: dict[uuid.UUID, int]) -> int:
            mine = [bid("me", task, asks[task]) for task in tasks]
            outcome = engine.clear(vs, [*others, *mine])
            return sum(a.payment - cost[a.task_id] for a in outcome.awards if a.bidder_id == "me")

        truthful = profit(cost)
        for _ in range(5):
            assert truthful >= profit({task: rng.randint(0, 100) for task in tasks})
