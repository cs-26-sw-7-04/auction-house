"""Clearing engines: turn a solver's allocation into awards and payments."""
import uuid
from collections.abc import Mapping, Sequence

from auction_house import plugins
from auction_house.domain import Award, Bid, Outcome
from auction_house.ports import Solver


def _awards(
    values: Mapping[uuid.UUID, int], bids: Sequence[Bid], solver: Solver, *, pivot: bool,
) -> Outcome:
    selection = solver.solve(values, bids)
    ask = {(b.task_id, b.bidder_id): b.price for b in bids}
    awards = []
    for task_id, bidder_id in selection.assignment.items():
        payment = ask[(task_id, bidder_id)]
        if pivot:  # Clarke pivot: the winning bid's marginal contribution to welfare
            without = solver.solve(
                values, [b for b in bids if (b.task_id, b.bidder_id) != (task_id, bidder_id)],
            )
            payment += selection.welfare - without.welfare
        awards.append(Award(task_id=task_id, bidder_id=bidder_id, payment=payment))
    return Outcome(
        awards=tuple(sorted(awards, key=lambda a: (a.bidder_id, a.task_id))),
        unallocated=tuple(sorted(set(values) - selection.assignment.keys())),
        welfare=selection.welfare,
    )


@plugins.engines.register("vcg")
class VcgEngine:
    """Each winning bid is paid  ask + W(everyone) - W(everyone without that bid).

    A winner's profit on a task is then its marginal contribution to welfare,
    whatever it asked, so asking its true cost is a dominant strategy. With one
    task this is a second-price auction, capped at the task's value. This holds
    only if the solver is exact; with an approximate solver the result is
    approximate VCG without that guarantee."""

    def __init__(self, solver: Solver):
        self.solver = solver

    def clear(self, values: Mapping[uuid.UUID, int], bids: Sequence[Bid]) -> Outcome:
        """Allocate with the solver and pay each winning bid its Clarke pivot payment."""
        return _awards(values, bids, self.solver, pivot=True)


@plugins.engines.register("pay-as-bid")
class PayAsBidEngine:
    """Same allocation, but winners are paid what they asked. Not truthful;
    the baseline for comparing against VCG."""

    def __init__(self, solver: Solver):
        self.solver = solver

    def clear(self, values: Mapping[uuid.UUID, int], bids: Sequence[Bid]) -> Outcome:
        """Allocate with the solver and pay each winning bid its ask."""
        return _awards(values, bids, self.solver, pivot=False)