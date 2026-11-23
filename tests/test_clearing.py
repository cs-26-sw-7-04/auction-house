"""Business-logic tests of allocation and payments: every solver, and the two clearing engines on top of them.

The exact solvers (brute force, and each algorithm of the C library) must agree on welfare and payments; they differ
only in how fast they get there. `per-task` is the baseline that auctions each task on its own.
"""
import random
import uuid

import pytest

from auction_house.components.engines import PayAsBidEngine, VcgEngine
from auction_house.components.solver_per_task import PerTaskSolver
from auction_house.components.solver_vcg_combinatorial import DEFAULT_LIBRARY, CVcgSolver
from auction_house.domain import Bid, BundleBid, utcnow

AUCTION = uuid.uuid4()
C_LIBRARY = pytest.mark.skipif(not DEFAULT_LIBRARY.exists(), reason="C library not built")

# The C library's algorithms: 0 brute force, 1 branch and bound, 2 fast pivots, 3 parallel pivots
C_ALGORITHMS = [pytest.param(a, id=f"c-algorithm-{a}", marks=C_LIBRARY) for a in range(4)]
EXACT = [*(pytest.param(lambda a=a: CVcgSolver(algorithm=a), id=f"c-algorithm-{a}", marks=C_LIBRARY) for a in range(4))]


def bid(bidder: str, *bundles) -> Bid:
    """Bid fake: each bundle is (tasks, price); the bidder runs at most one of them."""
    return Bid(auction_id=AUCTION, bidder_id=bidder, placed_at=utcnow(),
               bundles=tuple(BundleBid(tasks=frozenset(tasks), price=price) for tasks, price in bundles))


def values(*vs: int) -> dict[uuid.UUID, int]:
    """Value creator"""
    return {uuid.uuid4(): v for v in vs}


def awards(outcome) -> set[tuple[str, tuple, int]]:
    return {(a.bidder_id, a.task_ids, a.payment) for a in outcome.awards}


def random_auction(rng: random.Random):
    """Prices are drawn from a wide range so ties between equally good allocations (which solvers may break
    differently, and which change who is paid what) are practically impossible."""
    vs = values(*(rng.randint(10**5, 10**6) for _ in range(rng.randint(1, 6))))
    tasks = list(vs)
    bids = [
        bid(f"b{i}", *((rng.sample(tasks, rng.randint(1, min(3, len(tasks)))), rng.randint(0, 10**6))
                       for _ in range(rng.randint(1, 5))))
        for i in range(rng.randint(1, 4))
    ]
    return vs, bids


# --- solving ----------------------------------------------------------------------

@pytest.mark.parametrize("solver", EXACT)
def test_each_task_goes_to_its_cheapest_bidder_when_bundles_do_not_help(solver):
    vs = values(100, 90)
    t1, t2 = vs
    bids = [bid("a", ([t1], 10), ([t2], 50)), bid("b", ([t1], 40), ([t2], 20))]
    selection = solver().solve(vs, bids)
    assert {b: set(x.tasks) for b, x in selection.winners.items()} == {"a": {t1}, "b": {t2}}
    assert selection.welfare == (100 - 10) + (90 - 20)


@pytest.mark.parametrize("solver", EXACT)
def test_a_task_is_not_allocated_when_every_bid_is_above_its_value(solver):
    vs = values(100)
    (task,) = vs
    selection = solver().solve(vs, [bid("a", ([task], 120))])
    assert selection.winners == {}
    assert selection.welfare == 0


@pytest.mark.parametrize("solver", EXACT)
def test_a_bidder_wins_at_most_one_of_its_bundles(solver):
    vs = values(100, 90)
    t1, t2 = vs
    selection = solver().solve(vs, [bid("a", ([t1], 10), ([t2], 10)), bid("b", ([t2], 50))])
    assert {b: set(x.tasks) for b, x in selection.winners.items()} == {"a": {t1}, "b": {t2}}


@pytest.mark.parametrize("solver", EXACT)
def test_an_excluded_bidder_cannot_win(solver):
    vs = values(100)
    (task,) = vs
    selection = solver().solve(vs, [bid("a", ([task], 30)), bid("b", ([task], 50))], exclude="a")
    assert set(selection.winners) == {"b"}
    assert selection.welfare == 50


def test_per_task_gives_each_task_to_its_cheapest_bidder_even_if_that_is_one_bidder():
    vs = values(100, 90)
    t1, t2 = vs
    selection = PerTaskSolver().solve(vs, [bid("a", ([t1], 10), ([t2], 10)), bid("b", ([t1], 40), ([t2], 50))])
    assert {b: set(x.tasks) for b, x in selection.winners.items()} == {"a": {t1, t2}}
    assert selection.welfare == (100 - 10) + (90 - 10)


def test_per_task_ignores_bundles_of_several_tasks():
    vs = values(100, 90)
    t1, t2 = vs
    assert PerTaskSolver().solve(vs, [bid("a", ([t1, t2], 1))]).winners == {}


@pytest.mark.parametrize("algorithm", C_ALGORITHMS)
def test_every_c_algorithm_agrees_with_brute_force_on_welfare_and_payments(algorithm):
    rng = random.Random(11)
    reference = VcgEngine(CVcgSolver(algorithm=0))  # brute force
    engine = VcgEngine(CVcgSolver(algorithm=algorithm))
    for _ in range(60):
        vs, bids = random_auction(rng)
        expected, got = reference.clear(vs, bids), engine.clear(vs, bids)
        assert got.welfare == expected.welfare
        assert {a.bidder_id: a.payment for a in got.awards} == {a.bidder_id: a.payment for a in expected.awards}


# --- payments ---------------------------------------------------------------------

@pytest.mark.parametrize("solver", EXACT)
def test_vcg_with_one_task_is_a_second_price_auction(solver):
    vs = values(100)
    (task,) = vs
    outcome = VcgEngine(solver()).clear(vs, [bid("a", ([task], 30)), bid("b", ([task], 50))])
    assert awards(outcome) == {("a", (task,), 50)}


@pytest.mark.parametrize("solver", EXACT)
def test_vcg_payment_is_capped_at_the_value_of_the_task(solver):
    vs = values(100)
    (task,) = vs
    outcome = VcgEngine(solver()).clear(vs, [bid("a", ([task], 30)), bid("b", ([task], 120))])
    assert awards(outcome) == {("a", (task,), 100)}


@pytest.mark.parametrize("solver", EXACT)
def test_vcg_pays_a_winning_bundle_its_marginal_contribution(solver):
    vs = values(100, 90)
    t1, t2 = vs
    # With a: 190 - 20 = 170. Without a, b takes both tasks: 190 - 60 = 130. So a is paid 20 + 40.
    outcome = VcgEngine(solver()).clear(vs, [bid("a", ([t1, t2], 20)), bid("b", ([t1, t2], 60))])
    assert [(a.bidder_id, a.payment) for a in outcome.awards] == [("a", 60)]


def test_per_task_under_vcg_is_a_second_price_auction_on_each_task():
    vs = values(100, 90)
    t1, t2 = vs
    bids = [bid("a", ([t1], 10), ([t2], 60)), bid("b", ([t1], 40), ([t2], 20))]
    outcome = VcgEngine(PerTaskSolver()).clear(vs, bids)
    assert awards(outcome) == {("a", (t1,), 40), ("b", (t2,), 60)}
    assert outcome.unallocated == ()


def test_per_task_pays_a_bidder_winning_several_tasks_the_second_price_of_each():
    vs = values(100, 90)
    t1, t2 = vs
    bids = [bid("a", ([t1], 10), ([t2], 10)), bid("b", ([t1], 40), ([t2], 50))]
    outcome = VcgEngine(PerTaskSolver()).clear(vs, bids)
    assert awards(outcome) == {("a", tuple(sorted((t1, t2))), 40 + 50)}


@pytest.mark.parametrize("solver", EXACT)
def test_tasks_without_a_winning_bid_are_unallocated(solver):
    vs = values(100, 5)
    t1, t2 = vs
    outcome = VcgEngine(solver()).clear(vs, [bid("a", ([t1], 10)), bid("b", ([t2], 10))])
    assert [a.task_ids for a in outcome.awards] == [(t1,)]
    assert outcome.unallocated == (t2,)


@pytest.mark.parametrize("solver", EXACT)
def test_pay_as_bid_pays_the_ask(solver):
    vs = values(100)
    (task,) = vs
    (award,) = PayAsBidEngine(solver()).clear(vs, [bid("a", ([task], 30)), bid("b", ([task], 50))]).awards
    assert award.payment == 30


def test_truthful_bidding_is_never_worse_under_vcg():
    rng = random.Random(7)
    engine = VcgEngine(CVcgSolver(algorithm=0))  # brute force
    for _ in range(100):
        vs = values(*(rng.randint(1, 100) for _ in range(rng.randint(2, 5))))
        tasks = list(vs)
        others = [bid(f"o{i}", *(([task], rng.randint(0, 80)) for task in tasks)) for i in range(2)]
        # The cost of every bundle of one or two tasks, which is what a truthful bidder asks
        bundles = [[t] for t in tasks] + [list(p) for p in zip(tasks, tasks[1:])]
        cost = {tuple(sorted(b)): rng.randint(0, 120) for b in bundles}

        def profit(asks: dict) -> int:
            mine = bid("me", *((list(b), asks[b]) for b in cost))
            outcome = engine.clear(vs, [*others, mine])
            return sum(a.payment - cost[a.task_ids] for a in outcome.awards if a.bidder_id == "me")

        truthful = profit(cost)
        for _ in range(5):
            assert truthful >= profit({b: rng.randint(0, 150) for b in cost})
