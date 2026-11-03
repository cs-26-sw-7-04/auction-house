"""Solvers: choose the welfare-maximising allocation.

The model: each task is worth its submitter's budget, each bidder offers up to
`capacity` slots at a flat `unit_price`.
"""
import uuid
from collections.abc import Mapping, Sequence

from auction_house import plugins
from auction_house.domain import Bid, Selection


def welfare_of(values: Mapping[uuid.UUID, int], bids: Sequence[Bid], assignment: Mapping[uuid.UUID, str]) -> int:
    """:3"""
    price = {b.bidder_id: b.unit_price for b in bids}
    return sum(values[task] - price[bidder] for task, bidder in assignment.items())


@plugins.solvers.register("sorted")
class SortedSolver:
    """Exact and fast. With unit demand and flat prices, pairing the most
    valuable tasks with the cheapest slots is optimal, so nothing is enumerated."""

    def solve(self, values: Mapping[uuid.UUID, int], bids: Sequence[Bid]) -> Selection:
        """:3"""
        slots = sorted(
            (bid.unit_price, bid.bidder_id)
            for bid in bids
            for _ in range(min(bid.capacity, len(values)))
        )
        tasks = sorted(values, key=lambda t: (-values[t], t))
        assignment: dict[uuid.UUID, str] = {}
        for task, (price, bidder_id) in zip(tasks, slots):
            if values[task] <= price:
                break
            assignment[task] = bidder_id
        return Selection(assignment=assignment, welfare=welfare_of(values, bids, assignment))
