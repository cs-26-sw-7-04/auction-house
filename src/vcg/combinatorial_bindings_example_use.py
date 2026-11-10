from vcg_combinatorial_bindings import *
import ctypes
import sys

# Calls libvcg_combinatorial.so through the bindings with the hand-written cases from tests/combinatorial_vcg.h.
# Every case is cleared with every solver; each must give the expected welfare, awards (in order) and unallocated tasks.

COMB_MAX_TASKS = 64
SOLVERS = ["brute force", "branch and bound", "fast pivots", "parallel pivots"]  # comb_solver, in enum order

vcglib.comb_outcome_free.argtypes = [ctypes.POINTER(comb_outcome_c)]
vcglib.comb_outcome_free.restype = None
vcglib.comb_split.argtypes = [ctypes.c_int64, ctypes.POINTER(ctypes.c_int64), ctypes.c_size_t,
                              ctypes.POINTER(ctypes.c_int64)]
vcglib.comb_split.restype = None


def clear(values, bids, solver):
    """values: task values; bids: (bidder, price, [tasks]) tuples. Returns (ok, welfare, awards, unallocated) with
    awards as (task, bidder, payment) tuples."""
    c_values = (ctypes.c_int64 * len(values))(*values)
    task_arrays = [(ctypes.c_int * len(tasks))(*tasks) for _, _, tasks in bids]  # kept alive for the call
    c_bids = (comb_bid_c * len(bids))()
    for c_bid, (bidder, price, tasks), task_array in zip(c_bids, bids, task_arrays):
        c_bid.tasks = ctypes.cast(task_array, ctypes.POINTER(ctypes.c_int)) if tasks else None
        c_bid.task_count = len(tasks)
        c_bid.bidder = bidder
        c_bid.price = price
    outcome = vcglib.vcg_comb_clear(c_values, len(values), c_bids, len(bids), solver)
    awards = [(outcome.awards[i].task, outcome.awards[i].bidder, outcome.awards[i].payment)
              for i in range(outcome.award_count)]
    unallocated = [outcome.unallocated[i] for i in range(outcome.unallocated_count)]
    result = (outcome.ok, outcome.welfare, awards, unallocated)
    vcglib.comb_outcome_free(ctypes.byref(outcome))
    return result


def expect(name, values, bids, welfare, awards, unallocated=()):
    passed = True
    for solver, solver_name in enumerate(SOLVERS):
        got = clear(values, bids, solver)
        if got != (True, welfare, list(awards), list(unallocated)):
            print(f"{name}: unexpected outcome from {solver_name}")
            print(f"  got:      ok {got[0]}, welfare {got[1]}, awards {got[2]}, unallocated {got[3]}")
            print(f"  expected: ok True, welfare {welfare}, awards {list(awards)}, unallocated {list(unallocated)}")
            passed = False
    return passed


def split(total, weights):
    out = (ctypes.c_int64 * len(weights))()
    vcglib.comb_split(total, (ctypes.c_int64 * len(weights))(*weights), len(weights), out)
    return list(out)


def one_task_is_a_second_price_auction():
    return expect("one_task_is_a_second_price_auction", [100], [(0, 30, [0]), (1, 50, [0])],
                  70, [(0, 0, 50)])


def payment_is_capped_at_the_task_value():
    return expect("payment_is_capped_at_the_task_value", [100], [(0, 30, [0]), (1, 120, [0])],
                  70, [(0, 0, 100)])


def a_bundle_beats_dearer_singles():
    # W* = 80; without bidder 0 it is 40, so it is paid 20 + 80 - 40 = 60, split by task value
    return expect("a_bundle_beats_dearer_singles", [50, 50], [(0, 20, [0, 1]), (1, 30, [0]), (2, 30, [1])],
                  80, [(0, 0, 30), (1, 0, 30)])


def cheaper_singles_beat_a_bundle():
    return expect("cheaper_singles_beat_a_bundle", [50, 50], [(0, 60, [0, 1]), (1, 10, [0]), (2, 10, [1])],
                  80, [(0, 1, 50), (1, 2, 50)])


def a_bidder_wins_at_most_one_bid():
    # Bidder 0 would take both tasks for 180 welfare, but its bids are XOR: it wins the first, task 1 is left
    return expect("a_bidder_wins_at_most_one_bid", [100, 100], [(0, 10, [0]), (0, 10, [1]), (1, 150, [0, 1])],
                  90, [(0, 0, 50)], [1])


def a_zero_welfare_bid_still_wins():
    return expect("a_zero_welfare_bid_still_wins", [10], [(0, 10, [0])], 0, [(0, 0, 10)])


def on_equal_welfare_more_tasks_win():
    # Both have welfare 5; the bundle runs more tasks. Without bidder 1, W* is still 5: it is paid its ask.
    return expect("on_equal_welfare_more_tasks_win", [10, 10], [(0, 5, [0]), (1, 15, [0, 1])],
                  5, [(0, 1, 8), (1, 1, 7)])


def on_a_full_tie_the_first_bid_wins():
    return expect("on_a_full_tie_the_first_bid_wins", [100], [(7, 40, [0]), (3, 40, [0])], 60, [(0, 7, 40)])


def invalid_bids_are_left_out():
    bids = [
        (0, 0, []),      # no tasks
        (1, 0, [0, 0]),  # a task twice
        (2, 0, [2]),     # a task outside the auction
        (3, 0, [-1]),    # likewise
        (4, 101, [0]),   # asks more than the task is worth
    ]
    return expect("invalid_bids_are_left_out", [100, 100], bids, 0, [], [0, 1])


def no_bids_leave_every_task_unallocated():
    return expect("no_bids_leave_every_task_unallocated", [5, 6, 7], [], 0, [], [0, 1, 2])


def the_64th_task_can_be_auctioned():
    return expect("the_64th_task_can_be_auctioned", [1] * COMB_MAX_TASKS, [(0, 0, [63, 0])],
                  2, [(63, 0, 1), (0, 0, 1)], range(1, COMB_MAX_TASKS - 1))


def too_many_tasks_fail():
    ok = clear([0] * (COMB_MAX_TASKS + 1), [], 0)[0]
    if ok:
        print("too_many_tasks_fail: clearing 65 tasks did not fail")
    return not ok


def split_gives_leftovers_to_the_largest_remainders():
    int64_max = 2**63 - 1
    cases = [
        (10, [1, 1, 1], [4, 3, 3]),
        (7, [2, 3, 5], [1, 2, 4]),
        (2, [1, 1, 1, 1], [1, 1, 0, 0]),
        (0, [3, 4], [0, 0]),
        (5, [5], [5]),
        # Payments times values beyond 64 bits
        (int64_max // 2, [int64_max // 2, int64_max // 2], [int64_max // 4 + 1, int64_max // 4]),
    ]
    passed = True
    for total, weights, expected in cases:
        got = split(total, weights)
        if got != expected:
            print(f"comb_split({total}, {weights}): got {got}, expected {expected}")
            passed = False
    return passed


TESTS = [
    one_task_is_a_second_price_auction,
    payment_is_capped_at_the_task_value,
    a_bundle_beats_dearer_singles,
    cheaper_singles_beat_a_bundle,
    a_bidder_wins_at_most_one_bid,
    a_zero_welfare_bid_still_wins,
    on_equal_welfare_more_tasks_win,
    on_a_full_tie_the_first_bid_wins,
    invalid_bids_are_left_out,
    no_bids_leave_every_task_unallocated,
    the_64th_task_can_be_auctioned,
    too_many_tasks_fail,
    split_gives_leftovers_to_the_largest_remainders,
]

if __name__ == "__main__":
    failed = 0
    for test in TESTS:
        passed = test()
        print(f"{'PASS' if passed else 'FAIL'} {test.__name__}")
        failed += not passed
    print(f"{len(TESTS) - failed}/{len(TESTS)} passed")
    sys.exit(1 if failed else 0)
