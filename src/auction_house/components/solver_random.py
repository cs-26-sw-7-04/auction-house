"""Random baseline solver: winning bundles are chosen at random, but the allocation is always legal.

The offers (every bundle of every bidder) are shuffled and taken greedily: an offer wins if its bidder has not
won yet and none of its tasks is taken. So no task goes to two bidders, each bidder wins at most one of its
bundles (bids are XOR), and the allocation is maximal: no losing offer could be added to it.

Pair it with the `pay-as-bid` engine. Under `vcg` the Clarke pivot re-solves with fresh random draws, so the
payments it computes mean nothing.

    AH_ENGINE__NAME=pay-as-bid AH_SOLVER__NAME=random AH_SOLVER__OPTIONS='{"seed": 1}'
"""
import random
import uuid
from collections.abc import Mapping, Sequence

from auction_house import plugins
from auction_house.domain import Bid, BundleBid, Selection


@plugins.solvers.register("random")
class RandomSolver:
    def __init__(self, seed: int | None = None, profitable_only: bool = True):
        """`seed` makes a run reproducible; the generator is shared by every solve, so successive auctions
        still get different draws. `profitable_only` leaves out bundles asked at or above their tasks' value."""
        self._rng = random.Random(seed)
        self.profitable_only = profitable_only

    def solve(self, values: Mapping[uuid.UUID, int], bids: Sequence[Bid], *, exclude: str | None = None) -> Selection:
        """A random maximal legal allocation. `exclude` leaves one bidder's bids out. Bundles that name tasks
        not in `values` are ignored."""
        offers: list[tuple[str, BundleBid]] = [
            (bid.bidder_id, bundle)
            for bid in bids
            if bid.bidder_id != exclude
            for bundle in bid.bundles
            if all(task in values for task in bundle.tasks)
            and not (self.profitable_only and bundle.price >= _value(values, bundle))
        ]
        # A canonical order before shuffling, so a seed gives the same result whatever order bids arrive in.
        offers.sort(key=lambda o: (o[0], sorted(o[1].tasks), o[1].price))
        self._rng.shuffle(offers)

        winners: dict[str, BundleBid] = {}
        taken: set[uuid.UUID] = set()
        for bidder_id, bundle in offers:
            if bidder_id in winners or not bundle.tasks.isdisjoint(taken):
                continue
            winners[bidder_id] = bundle
            taken |= bundle.tasks

        welfare = sum(_value(values, bundle) - bundle.price for bundle in winners.values())
        return Selection(winners=dict(sorted(winners.items())), welfare=welfare)


def _value(values: Mapping[uuid.UUID, int], bundle: BundleBid) -> int:
    return sum(values[task] for task in bundle.tasks)
