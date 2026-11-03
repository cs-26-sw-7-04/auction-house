"""Clearing engines: turn a solver's allocation into awards and payments."""
import uuid
from collections import defaultdict
from collections.abc import Mapping, Sequence

from auction_house import plugins
from auction_house.domain import Award, Bid, Outcome
from auction_house.ports import Solver


def _awards(
    values: Mapping[uuid.UUID, int], bids: Sequence[Bid], solver: Solver, *, pivot: bool,
) -> Outcome:
    selection = solver.solve(values, bids)
    won: dict[str, list[uuid.UUID]] = defaultdict(list)
    for task_id, bidder_id in selection.assignment.items():
        won[bidder_id].append(task_id)

    price_of = {b.bidder_id: b.unit_price for b in bids}
    awards = []
    for bidder_id, task_ids in won.items():
        asked = price_of[bidder_id] * len(task_ids)
        payment = asked
        if pivot:  # Clarke pivot: the bidder's marginal contribution to welfare
            without = solver.solve(values, [b for b in bids if b.bidder_id != bidder_id])
            payment += selection.welfare - without.welfare
        awards.append(Award(
            bidder_id=bidder_id, task_ids=tuple(sorted(task_ids)),
            unit_price=price_of[bidder_id], payment=payment,
        ))
    return Outcome(
        awards=tuple(sorted(awards, key=lambda a: a.bidder_id)),
        unallocated=tuple(sorted(set(values) - selection.assignment.keys())),
        welfare=selection.welfare,
    )


@plugins.engines.register("vcg")
class VcgEngine:
    """Winners are paid  price_i + W(everyone) - W(everyone but i).

    A winner's profit is then its marginal contribution to welfare, whatever it
    bid, so asking its true cost is a dominant strategy. This holds only if the
    solver is exact; with an approximate solver the result is approximate VCG
    without that guarantee."""

    def __init__(self, solver: Solver):
        self.solver = solver

    def clear(self, values: Mapping[uuid.UUID, int], bids: Sequence[Bid]) -> Outcome:
        """:3"""
        return _awards(values, bids, self.solver, pivot=True)


@plugins.engines.register("pay-as-bid")
class PayAsBidEngine:
    """Same allocation, but winners are paid what they asked. Not truthful;
    the baseline for comparing against VCG."""

    def __init__(self, solver: Solver):
        self.solver = solver

    def clear(self, values: Mapping[uuid.UUID, int], bids: Sequence[Bid]) -> Outcome:
        """:3"""
        return _awards(values, bids, self.solver, pivot=False)
