"""Solver backed by the combinatorial VCG library.

The ctypes layer lives in `vcg.vcg_combinatorial_bindings`. This module only translates
between house types and the library's arrays, and returns the library's allocation.
The library also computes VCG payments; they are ignored here, because paying is the
clearing engine's job.
"""
import ctypes
import uuid
from collections.abc import Mapping, Sequence
from pathlib import Path

from auction_house import plugins
from auction_house.domain import Bid, BundleBid, Selection, SolverError

# Where the bindings load the library from (src/vcg/build/lib/libvcg_combinatorial.so).
# Only used to check whether it has been built, e.g. to skip tests.
DEFAULT_LIBRARY = Path(__file__).resolve().parents[2] / "vcg" / "build" / "lib" / "libvcg_combinatorial.so"


@plugins.solvers.register("vcg_combinatorial")
class CVcgSolver:
    """Chooses the winning bundles with the C library.

    Each of a bidder's bundles is passed as one library bid, all with the same bidder
    number; the library must treat them as alternatives, so a bidder wins at most one.
    Select it with `AH_SOLVER__NAME=vcg_combinatorial`; `AH_SOLVER__OPTIONS='{"algorithm": 1}'`
    picks the library's own solver."""

    def __init__(self, algorithm: int = 0):
        """`algorithm` is the value of the library's `comb_solver` argument."""
        # Imported here, not at module level: importing the bindings loads the shared
        # library, and this module must stay importable when it has not been built.
        try:
            from vcg import vcg_combinatorial_bindings
        except OSError as error:
            raise SolverError(f"cannot load the VCG library at {DEFAULT_LIBRARY}; build it first") from error
        self._lib = vcg_combinatorial_bindings
        self.algorithm = algorithm


    def solve(self, values: Mapping[uuid.UUID, int], bids: Sequence[Bid], *, exclude: str | None = None) -> Selection:
        """The winning bundle of each winning bidder, and the welfare. `exclude` leaves
        one bidder's bids out. Bundles that name tasks not in `values` are ignored."""
        lib = self._lib
        tasks = sorted(values)
        index = {task: i for i, task in enumerate(tasks)}
        bidders = sorted({bid.bidder_id for bid in bids if bid.bidder_id != exclude})
        bidder_number = {bidder_id: i for i, bidder_id in enumerate(bidders)}

        offers: list[tuple[str, BundleBid]] = [
            (bid.bidder_id, bundle)
            for bid in sorted(bids, key=lambda b: b.bidder_id)
            if bid.bidder_id != exclude
            for bundle in bid.bundles
            if all(task in index for task in bundle.tasks)
        ]
        if not tasks or not offers:  # nothing to choose; do not call the library with empty arrays
            return Selection(winners={}, welfare=0)

        c_values = (ctypes.c_int64 * len(tasks))(*(values[task] for task in tasks))
        task_arrays = []  # the library reads these through pointers: keep them alive until it returns
        c_bids = (lib.comb_bid_c * len(offers))()
        for k, (bidder_id, bundle) in enumerate(offers):
            indices = sorted(index[task] for task in bundle.tasks)
            array = (ctypes.c_int * len(indices))(*indices)
            task_arrays.append(array)
            c_bids[k] = lib.comb_bid_c(
                ctypes.cast(array, ctypes.POINTER(ctypes.c_int)), len(indices), bidder_number[bidder_id], bundle.price,
            )

        result = lib.vcglib.vcg_comb_clear(c_values, len(tasks), c_bids, len(offers), self.algorithm)
        try:
            if not result.ok:
                raise SolverError("the C solver failed")
            chosen: dict[str, int] = {}  # bidder -> index of the winning offer
            for i in range(result.award_count):
                k = result.awards[i].bid
                if k >= len(offers):
                    raise SolverError("the C solver returned a bid that does not exist")
                if chosen.setdefault(offers[k][0], k) != k:
                    raise SolverError("the C solver awarded two bundles to one bidder")
            welfare = int(result.welfare)
        finally:
            lib.release(result)

        return Selection(winners={bidder_id: offers[k][1] for bidder_id, k in sorted(chosen.items())}, welfare=welfare)