"""Business-logic tests of the C combinatorial solver. Skipped if the library is not built."""
import random
import uuid

import pytest

from auction_house.components.solver_vcg_combinatorial import DEFAULT_LIBRARY, CVcgSolver
from auction_house.components.engines import VcgEngine
from auction_house.domain import Bid, BundleBid, utcnow

pytestmark = pytest.mark.skipif(not DEFAULT_LIBRARY.exists(), reason="C library not built")

AUCTION = uuid.uuid4()


def bid(bidder: str, *bundles) -> Bid:
    """Bid fake: each bundle is (tasks, price); the bidder runs at most one of them."""
    return Bid(
        auction_id=AUCTION,
        bidder_id=bidder,
        bundles=tuple(BundleBid(tasks=frozenset(tasks), price=price) for tasks, price in bundles),
        placed_at=utcnow(),
    )


def values(*vs: int) -> dict[uuid.UUID, int]:
    """Value creator"""
    return {uuid.uuid4(): v for v in vs}


def won(selection) -> dict:
    return {bidder: set(bundle.tasks) for bidder, bundle in selection.winners.items()}


def paid(outcome) -> dict:
    return {a.bidder_id: a.payment for a in outcome.awards}


# --- the allocation ---------------------------------------------------------------

def test_the_cheaper_bid_on_a_task_wins():
    vs = values(100)
    (task,) = vs
    selection = CVcgSolver().solve(vs, [bid("a", ([task], 30)), bid("b", ([task], 50))])
    assert won(selection) == {"a": {task}}
    assert selection.welfare == 70


def test_a_bundle_wins_all_its_tasks_or_none():
    vs = values(100, 90)
    t1, t2 = vs
    selection = CVcgSolver().solve(vs, [bid("a", ([t1, t2], 20)), bid("b", ([t1, t2], 60))])
    assert won(selection) == {"a": {t1, t2}}
    assert selection.welfare == 170


def test_a_bidder_wins_at_most_one_of_its_bundles():
    vs = values(100, 90)
    t1, t2 = vs
    selection = CVcgSolver().solve(vs, [bid("a", ([t1], 10), ([t2], 10)), bid("b", ([t2], 50))])
    assert won(selection) == {"a": {t1}, "b": {t2}}
    assert selection.welfare == (100 - 10) + (90 - 50)


def test_an_excluded_bidder_cannot_win():
    vs = values(100)
    (task,) = vs
    selection = CVcgSolver().solve(vs, [bid("a", ([task], 30)), bid("b", ([task], 50))], exclude="a")
    assert won(selection) == {"b": {task}}
    assert selection.welfare == 50


def test_without_bids_nobody_wins():
    selection = CVcgSolver().solve(values(100, 5), [])
    assert selection.winners == {}
    assert selection.welfare == 0


def test_a_bundle_on_tasks_that_are_not_being_cleared_is_ignored():
    selection = CVcgSolver().solve(values(100), [bid("a", ([uuid.uuid4()], 1))])
    assert selection.winners == {}


def test_random_auctions_never_award_a_task_twice():
    rng = random.Random(3)
    solver = CVcgSolver()
    for _ in range(100):
        vs = values(*(rng.randint(1, 100) for _ in range(rng.randint(1, 5))))
        tasks = list(vs)
        bids = [
            bid(f"b{i}", *(
                (rng.sample(tasks, rng.randint(1, len(tasks))), rng.randint(0, 150))
                for _ in range(rng.randint(1, 3))
            ))
            for i in range(rng.randint(1, 3))
        ]
        selection = solver.solve(vs, bids)
        allocated = [task for bundle in selection.winners.values() for task in bundle.tasks]
        assert len(allocated) == len(set(allocated))
        assert selection.welfare >= 0


# --- payments, through the engine -------------------------------------------------

def test_vcg_with_this_solver_is_a_second_price_auction():
    vs = values(100)
    (task,) = vs
    outcome = VcgEngine(CVcgSolver()).clear(vs, [bid("a", ([task], 30)), bid("b", ([task], 50))])
    assert paid(outcome) == {"a": 50}


def test_vcg_payment_is_capped_at_the_value_of_the_task():
    vs = values(100)
    (task,) = vs
    outcome = VcgEngine(CVcgSolver()).clear(vs, [bid("a", ([task], 30)), bid("b", ([task], 120))])
    assert paid(outcome) == {"a": 100}


def test_vcg_pays_a_winning_bundle_its_marginal_contribution():
    vs = values(100, 90)
    t1, t2 = vs
    # With a: 190 - 20 = 170. Without a, b takes both tasks: 190 - 60 = 130. So a is paid 20 + 40.
    outcome = VcgEngine(CVcgSolver()).clear(vs, [bid("a", ([t1, t2], 20)), bid("b", ([t1, t2], 60))])
    assert paid(outcome) == {"a": 60}


def test_vcg_payments_with_alternative_bundles():
    vs = values(100, 90)
    t1, t2 = vs
    outcome = VcgEngine(CVcgSolver()).clear(vs, [bid("a", ([t1], 10), ([t2], 10)), bid("b", ([t2], 50))])
    # a: 10 + 130 - 40 (b alone takes t2). b: 50 + 130 - 90 (a alone takes t1).
    assert paid(outcome) == {"a": 100, "b": 90}