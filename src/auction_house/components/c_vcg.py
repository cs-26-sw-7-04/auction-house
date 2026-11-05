"""ctypes bridge to our C VCG library"""
import uuid
from collections.abc import Mapping, Sequence
from pathlib import Path

from auction_house import plugins
from auction_house.domain import Bid, Selection, SolverError

DEFAULT_LIBRARY = Path(__file__).resolve().parents[2] / "vcg" / "build" / "lib" / "libvcg.so" # TODO: Define actual path instead og this nonsense


@plugins.solvers.register("c")
class CVcgSolver:
    """Tasks are buyers (demand 1, value = budget), bidders are sellers."""

    def __init__(self, library: Path | str = DEFAULT_LIBRARY):
        try:
            from vcg import vcg_bindings
        except OSError as error:
            raise SolverError(f"cannot load the VCG library at {DEFAULT_LIBRARY}; build it first") from error
        self._vcg = vcg_bindings
        # Single source of truth for the limit: the bindings, not a copy of the constant.
        self.max_agents = vcg_bindings.MAX_AGENTS

    def solve(self, values: Mapping[uuid.UUID, int], bids: Sequence[Bid]) -> Selection:
        """:3 Allocate tasks to bidders for maximal welfare with our C library.
        
        A task goes to at most one bidder, and to none if every bid on it is above its value.
        """

        # Sorted tasks making their order deterministic
        by_task: dict[uuid.UUID, list[Bid]] = {}
        for bid in sorted(bids, key=lambda b: b.bidder_id):
            if bid.task_id in values:
                by_task.setdefault(bid.task_id, []).append(bid)


        assignment: dict[uuid.UUID, str] = {}
        welfare = 0
        for task_id, task_bids in by_task.items():
            if len(task_bids) > self.max_agents:
                raise SolverError(f"the C solver handles at most {self.max_agents} bids per task")
            winner = self._best_bid(values[task_id], task_bids)
            if winner is not None:
                assignment[task_id] = winner.bidder_id
                welfare += values[task_id] - winner.price
        return Selection(assignment=assignment, welfare=welfare)

    def _best_bid(self, value: int, bids: Sequence[Bid]) -> Bid | None:
        """The bid the library picks for one task, or None if no bid is worth taking."""
        vcg = self._vcg
        auction = vcg.Auction(
            # One buyer wanting one unit. The bindings index `values` by amount, so for
            # one unit that is a one-element list.
            buyers=[vcg.Buyer(max_flops=1, values=[value])],
            # The bindings take a seller's capacity from its number of tasks; the house
            # has no notion of flops, so a seller is a single placeholder task of one flop.
            sellers=[vcg.Seller(tasks=[vcg.Task(0, 1)], cost=-bid.price) for bid in bids],
        )
        allocation = auction.allocate().allocation
        if (allocation.rows, allocation.cols) != (len(bids), 1):
            raise SolverError("the C solver returned no allocation")
        # quantity[i][0]: whether seller i (the i-th bid) supplies the task.
        return next((bid for i, bid in enumerate(bids) if allocation.quantity[i][0] > 0), None)
