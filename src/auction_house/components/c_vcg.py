"""ctypes bridge to the C VCG library (`VCG-impl-master`).

The library solves a multi-unit auction by brute-force enumeration and returns
an allocation matrix, but no payments. Two things in it matter here:
- `welfare()` in vcg.c *adds* `cost`, so costs are passed negated.
- `MAX_AGENTS` in vcg.h is 32 and the structs are passed by value, so the
  layouts below must use the same value.
"""
import ctypes
import os
import uuid
from collections.abc import Mapping, Sequence
from pathlib import Path

from auction_house import plugins
from auction_house.components.solvers import welfare_of
from auction_house.domain import Bid, Selection, SolverError

MAX_AGENTS = 32  # must equal MAX_AGENTS in vcg.h
DEFAULT_LIBRARY = Path(os.environ.get("VCG_LIBRARY") or (
    Path(__file__).resolve().parents[4] / "VCG-impl-master" / "build" / "lib" / "libvcg.so"))


class _Allocation(ctypes.Structure):
    _fields_ = [
        ("rows", ctypes.c_int),
        ("cols", ctypes.c_int),
        ("quantity", (ctypes.c_int * MAX_AGENTS) * MAX_AGENTS),
    ]


class _Buyers(ctypes.Structure):
    _fields_ = [
        ("count", ctypes.c_size_t),
        ("demand", ctypes.c_int * MAX_AGENTS),
        ("value", ctypes.c_double * MAX_AGENTS),
    ]


class _Sellers(ctypes.Structure):
    _fields_ = [
        ("count", ctypes.c_size_t),
        ("capacity", ctypes.c_int * MAX_AGENTS),
        ("cost", ctypes.c_double * MAX_AGENTS),
    ]


@plugins.solvers.register("c")
class CVcgSolver:
    """Tasks are buyers (demand 1, value = budget), bidders are sellers."""

    max_agents = MAX_AGENTS

    def __init__(self, library: Path | str = DEFAULT_LIBRARY):
        try:
            self._lib = ctypes.CDLL(str(library))
        except OSError as error:
            raise SolverError(f"cannot load the VCG library at {library}; run `make` in VCG-impl-master") from error
        self._lib.vcg_auction.argtypes = [_Buyers, _Sellers]
        self._lib.vcg_auction.restype = _Allocation

    def solve(self, values: Mapping[uuid.UUID, int], bids: Sequence[Bid]) -> Selection:
        tasks = sorted(values)
        bidders = sorted(bids, key=lambda b: b.bidder_id)
        if not tasks or not bidders:  # the library divides by the number of columns
            return Selection(assignment={}, welfare=0)
        if len(tasks) > MAX_AGENTS or len(bidders) > MAX_AGENTS:
            raise SolverError(f"the C solver handles at most {MAX_AGENTS} tasks and {MAX_AGENTS} bidders")

        buyers = _Buyers(count=len(tasks))
        for j, task_id in enumerate(tasks):
            buyers.demand[j] = 1
            buyers.value[j] = values[task_id]
        sellers = _Sellers(count=len(bidders))
        for i, bid in enumerate(bidders):
            sellers.capacity[i] = min(bid.capacity, len(tasks))
            sellers.cost[i] = -bid.unit_price

        allocation = self._lib.vcg_auction(buyers, sellers)
        if (allocation.rows, allocation.cols) != (len(bidders), len(tasks)):
            raise SolverError("the C solver returned no allocation")

        assignment = {
            task_id: bidders[i].bidder_id
            for j, task_id in enumerate(tasks)
            for i in range(len(bidders))
            if allocation.quantity[i][j] > 0
        }
        return Selection(assignment=assignment, welfare=welfare_of(values, bids, assignment))
