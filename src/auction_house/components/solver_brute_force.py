"""Solvers: choose the welfare-maximising allocation.

The model: each task is worth its submitter's budget. A bid lists bundles of
tasks, each with a price asked to run the whole bundle. A bidder wins at most
one of their bundles (XOR), and each task goes to at most one bidder. Welfare is
the values of the tasks covered less the prices of the winning bundles.
"""
import uuid
from collections.abc import Mapping, Sequence

from auction_house import plugins
from auction_house.domain import Bid, BundleBid, Selection


def bundle_surplus(values: Mapping[uuid.UUID, int], bundle: BundleBid) -> int:
    """What the bundle adds to welfare: its tasks' values less its price."""
    return sum(values[t] for t in bundle.tasks) - bundle.price


def welfare_of(values: Mapping[uuid.UUID, int], winners: Mapping[str, BundleBid]) -> int:
    """The welfare of an allocation. Useful for checking a solver's answer in tests."""
    return sum(bundle_surplus(values, b) for b in winners.values())


@plugins.solvers.register("brute-force")
class BruteForceSolver:
    """Exact, by depth-first search over every combination of bundles.

    Exponential in the number of bidders, so only for small auctions and as the
    reference the ILP solver is tested against. Pruning by an optimistic bound
    helps, but does not change the worst case.
    """

    def solve(
        self,
        values: Mapping[uuid.UUID, int],
        bids: Sequence[Bid],
        *,
        exclude: str | None = None,
    ) -> Selection:
        """Pick the welfare-maximising set of non-overlapping bundles, at most one per bidder.

        Bundles with a task outside `values` are ignored, as are bundles that
        would not raise welfare (surplus <= 0). With `exclude`, that bidder's bid
        is dropped. Ties go to the allocation found first: bidders are visited in
        id order, and "not winning" is tried before any bundle, so the allocation
        with fewer winners is preferred.
        """
        # Per bidder, the bundles worth considering, best surplus first.
        options: list[tuple[str, list[tuple[BundleBid, int]]]] = []
        for bid in sorted(bids, key=lambda b: b.bidder_id):
            if bid.bidder_id == exclude:
                continue
            usable = []
            for bundle in bid.bundles:
                if not all(t in values for t in bundle.tasks):
                    continue
                surplus = bundle_surplus(values, bundle)
                if surplus > 0:
                    usable.append((bundle, surplus))
            usable.sort(key=lambda x: (-x[1], sorted(map(str, x[0].tasks))))
            if usable:
                options.append((bid.bidder_id, usable))

        # bound[i]: the most the bidders from i onwards could add, ignoring overlaps.
        bound = [0] * (len(options) + 1)
        for i in range(len(options) - 1, -1, -1):
            bound[i] = bound[i + 1] + options[i][1][0][1]

        best_welfare = 0
        best_winners: dict[str, BundleBid] = {}
        picked: dict[str, BundleBid] = {}

        def search(i: int, taken: frozenset[uuid.UUID], welfare: int) -> None:
            nonlocal best_welfare, best_winners
            if welfare + bound[i] <= best_welfare:
                return  # cannot beat what is already found
            if i == len(options):
                best_welfare, best_winners = welfare, dict(picked)
                return
            search(i + 1, taken, welfare)  # this bidder does not win
            bidder_id, usable = options[i]
            for bundle, surplus in usable:
                if taken.isdisjoint(bundle.tasks):
                    picked[bidder_id] = bundle
                    search(i + 1, taken | bundle.tasks, welfare + surplus)
                    del picked[bidder_id]

        search(0, frozenset(), 0)
        return Selection(winners=best_winners, welfare=best_welfare)
