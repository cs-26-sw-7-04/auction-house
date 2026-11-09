"""Clearing engines: turn a solver's allocation into awards and payments."""
import uuid
from collections.abc import Mapping, Sequence

from auction_house import plugins
from auction_house.domain import Award, Bid, Outcome
from auction_house.ports import Solver


def _clear(
    values: Mapping[uuid.UUID, int], bids: Sequence[Bid], solver: Solver, *, pivot: bool,
) -> Outcome:
    best = solver.solve(values, bids)
    awards = []
    for bidder_id, bundle in best.winners.items():
        payment = bundle.price

        if pivot:
            # Clarke pivot: the winner's marginal contribution to welfare.
            # The exclusion happens inside the solver, not by filtering `bids` here.
            without = solver.solve(values, bids, exclude=bidder_id)
            payment += best.welfare - without.welfare

        awards.append(Award(
            bidder_id=bidder_id,
            task_ids=tuple(sorted(bundle.tasks)),
            payment=payment,
        ))
        
    allocated = {t for bundle in best.winners.values() for t in bundle.tasks}
    return Outcome(
        awards=tuple(sorted(awards, key=lambda a: a.bidder_id)),
        unallocated=tuple(sorted(set(values) - allocated)),
        welfare=best.welfare,
    )


@plugins.engines.register("vcg")
class VcgEngine:
    """Each winner is paid  ask + W(everyone) - W(everyone without that bidder).

    A winner's profit is then its marginal contribution to welfare, whatever it
    asked, so reporting its true cost for each bundle is a dominant strategy.
    This holds only if the solver is exact; with an approximate solver the result
    is approximate VCG without that guarantee. Costs one extra solve per winner."""

    def __init__(self, solver: Solver):
        self.solver = solver

    def clear(self, values: Mapping[uuid.UUID, int], bids: Sequence[Bid]) -> Outcome:
        """:3  Allocate with the solver and pay each winner its Clarke pivot payment."""
        return _clear(values, bids, self.solver, pivot=True)


@plugins.engines.register("pay-as-bid")
class PayAsBidEngine:
    """Same allocation, but winners are paid what they asked for their bundle.
    Not truthful; the baseline for comparing against VCG."""

    def __init__(self, solver: Solver):
        self.solver = solver

    def clear(self, values: Mapping[uuid.UUID, int], bids: Sequence[Bid]) -> Outcome:
        """:3 Allocate with the solver and pay each winner its ask."""
        return _clear(values, bids, self.solver, pivot=False)