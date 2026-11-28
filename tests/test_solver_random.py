"""Business-logic tests of the random solver: whatever it draws, the allocation must be legal."""
import random
import uuid

from auction_house import components, plugins  # noqa: F401  (registers the built-ins)
from auction_house.components.engines import PayAsBidEngine
from auction_house.components.solver_random import RandomSolver
from auction_house.domain import Bid, BundleBid, Selection, utcnow

AUCTION = uuid.uuid4()


def bid(bidder: str, *bundles) -> Bid:
    """Bid fake: each bundle is (tasks, price); the bidder runs at most one of them."""
    return Bid(auction_id=AUCTION, bidder_id=bidder, placed_at=utcnow(),
               bundles=tuple(BundleBid(tasks=frozenset(tasks), price=price) for tasks, price in bundles))


def values(*vs: int) -> dict[uuid.UUID, int]:
    return {uuid.uuid4(): v for v in vs}


def random_auction(rng: random.Random):
    vs = values(*(rng.randint(1, 100) for _ in range(rng.randint(1, 8))))
    tasks = list(vs)
    bids = [
        bid(f"b{i}", *((rng.sample(tasks, rng.randint(1, min(4, len(tasks)))), rng.randint(0, 200))
                       for _ in range(rng.randint(1, 6))))
        for i in range(rng.randint(0, 6))
    ]
    return vs, bids


def won(selection) -> dict:
    return {bidder: set(bundle.tasks) for bidder, bundle in selection.winners.items()}


def assert_legal(vs, bids, selection, *, profitable_only=True, exclude=None):
    own = {b.bidder_id: set(b.bundles) for b in bids}
    taken: set = set()
    for bidder, bundle in selection.winners.items():
        assert bidder != exclude
        assert bundle in own[bidder], "a winner must win one of its own bundles"
        assert taken.isdisjoint(bundle.tasks), "a task was awarded to two bidders"
        taken |= bundle.tasks
        if profitable_only:
            assert bundle.price < sum(vs[t] for t in bundle.tasks)
    assert selection.welfare == sum(sum(vs[t] for t in b.tasks) - b.price for b in selection.winners.values())
    # Maximal: no losing offer could have been added.
    for b in bids:
        if b.bidder_id in selection.winners or b.bidder_id == exclude:
            continue
        for bundle in b.bundles:
            fits = bundle.tasks.isdisjoint(taken) and all(t in vs for t in bundle.tasks)
            if profitable_only:
                fits = fits and bundle.price < sum(vs[t] for t in bundle.tasks)
            assert not fits, "an offer that fits was left out"


def test_every_random_allocation_is_legal_and_maximal():
    rng = random.Random(3)
    for profitable_only in (True, False):
        solver = RandomSolver(seed=5, profitable_only=profitable_only)
        for _ in range(300):
            vs, bids = random_auction(rng)
            exclude = rng.choice([None, *(b.bidder_id for b in bids)])
            selection = solver.solve(vs, bids, exclude=exclude)
            assert_legal(vs, bids, selection, profitable_only=profitable_only, exclude=exclude)


def test_an_excluded_bidder_cannot_win():
    vs = values(100)
    (task,) = vs
    for seed in range(20):
        assert won(RandomSolver(seed=seed).solve(vs, [bid("a", ([task], 1)), bid("b", ([task], 2))], exclude="a")) == {"b": {task}}


def test_unprofitable_bundles_win_only_when_allowed():
    vs = values(100)
    (task,) = vs
    bids = [bid("a", ([task], 100))]
    assert RandomSolver(seed=1).solve(vs, bids).winners == {}
    selection = RandomSolver(seed=1, profitable_only=False).solve(vs, bids)
    assert won(selection) == {"a": {task}}
    assert selection.welfare == 0


def test_bundles_naming_unknown_tasks_are_ignored():
    vs = values(100)
    (task,) = vs
    assert RandomSolver(seed=1).solve(vs, [bid("a", ([task, uuid.uuid4()], 1))]).winners == {}


def test_nothing_to_allocate():
    assert RandomSolver(seed=1).solve({}, []) == Selection(winners={}, welfare=0)
    assert RandomSolver(seed=1).solve(values(10), []) == Selection(winners={}, welfare=0)


def test_the_same_seed_gives_the_same_allocation_whatever_the_bid_order():
    rng = random.Random(9)
    for _ in range(50):
        vs, bids = random_auction(rng)
        assert RandomSolver(seed=42).solve(vs, bids) == RandomSolver(seed=42).solve(vs, list(reversed(bids)))


def test_the_winner_of_a_contested_task_varies():
    vs = values(100)
    (task,) = vs
    bids = [bid(name, ([task], 10)) for name in "abcd"]
    assert {next(iter(RandomSolver(seed=s).solve(vs, bids).winners)) for s in range(50)} == set("abcd")


def test_pay_as_bid_on_the_random_solver_gives_disjoint_awards():
    rng = random.Random(4)
    engine = PayAsBidEngine(RandomSolver(seed=1))
    for _ in range(100):
        vs, bids = random_auction(rng)
        outcome = engine.clear(vs, bids)
        allocated = [t for a in outcome.awards for t in a.task_ids]
        assert len(allocated) == len(set(allocated))
        assert len({a.bidder_id for a in outcome.awards}) == len(outcome.awards)
        assert set(outcome.unallocated) == set(vs) - set(allocated)


def test_it_is_registered_as_random():
    solver = plugins.solvers.create(plugins.ComponentSpec(name="random", options={"seed": 1}))
    assert isinstance(solver, RandomSolver)
