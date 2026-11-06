"""Solvers: choose the welfare-maximising allocation.

The model: each task is worth its submitter's budget, and each bid asks a price to
run one task. Bids on different tasks do not interact, so a task's outcome depends
only on the bids for it.
"""
import uuid
from collections.abc import Mapping, Sequence

from auction_house import plugins
from auction_house.domain import Bid, Selection


def welfare_of(values: Mapping[uuid.UUID, int], bids: Sequence[Bid], assignment: Mapping[uuid.UUID, str]) -> int:
    """The welfare of an assignment: each assigned task's value less the price the
    winning bidder asked for it."""
    price = {(b.task_id, b.bidder_id): b.price for b in bids}
    return sum(values[task] - price[(task, bidder)] for task, bidder in assignment.items())


@plugins.solvers.register("sorted")
class SortedSolver:
    """Exact and fast. Tasks do not interact, so the best allocation gives each
    task to its cheapest bid; nothing is enumerated."""

    def solve(self, values: Mapping[uuid.UUID, int], bids: Sequence[Bid]) -> Selection:
        """Give each task to its cheapest bid, if that is below the task's value.
        Ties go to the lowest bidder id. Bids on tasks not in `values` are ignored."""
        cheapest: dict[uuid.UUID, Bid] = {}
        for bid in bids:
            if bid.task_id not in values:
                continue
            current = cheapest.get(bid.task_id)
            if current is None or (bid.price, bid.bidder_id) < (current.price, current.bidder_id):
                cheapest[bid.task_id] = bid
        assignment = {task: bid.bidder_id for task, bid in cheapest.items() if values[task] > bid.price}
        return Selection(assignment=assignment, welfare=welfare_of(values, bids, assignment))
