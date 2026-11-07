/* Combinatorial reverse auction cleared with VCG; a C port of clearing.py.
 *
 * Tasks are indices 0..task_count-1, each worth values[t] to the house. Bidders ask a price to run a set of tasks.
 * Bids are XOR: a bidder wins at most one of its bids. Clearing picks the set of bids with the most welfare (task
 * values less the winning asks), preferring, on equal welfare, the set running more tasks and then the set found
 * first. Each winner is paid its ask plus what it adds to that welfare: price + W* - W*_without_its_bidder, split
 * over its tasks in proportion to their values. The top of vcg_combinatorial.c explains this with a worked example.
 *
 * Ties go to the bids that come first in `bids`. clearing.py sorts bids by (placed_at, bidder_id, task_ids, price)
 * before clearing, so the outcome does not depend on their arrival order; callers wanting the same must sort first.
 *
 * Every solver returns the same outcome; they differ only in how fast they find it:
 *   COMB_BRUTE_FORCE       tries every set of bids, as clearing.py does. The reference the others are tested against.
 *   COMB_BRANCH_AND_BOUND  the same search, skipping subtrees whose bound cannot beat the best set found so far.
 *   COMB_FAST_PIVOTS       finds the best (welfare, tasks run) by branch and bound over the densest bids first, then
 *                          rebuilds the set brute force would pick from it one bid at a time. Pivot searches only
 *                          look for the welfare value, seeded with a known feasible welfare.
 *   COMB_PARALLEL_PIVOTS   COMB_FAST_PIVOTS with the pivot searches spread over threads.
 */
#ifndef VCG_COMBINATORIAL_H
#define VCG_COMBINATORIAL_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define COMB_MAX_TASKS 64 /* task sets are 64 bit masks */

typedef enum {
	COMB_BRUTE_FORCE,
	COMB_BRANCH_AND_BOUND,
	COMB_FAST_PIVOTS,
	COMB_PARALLEL_PIVOTS,
	COMB_SOLVER_COUNT
} comb_solver;

typedef struct {
	const int *tasks;  /* task indices; the order decides how the payment is split on ties */
	size_t task_count;
	int bidder;        /* any int identifying the bidder */
	int64_t price;     /* what the bidder asks to run all of `tasks` */
} comb_bid;

typedef struct {
	int task;
	int bidder;
	size_t bid;        /* index of the winning bid in `bids` */
	int64_t payment;   /* this task's share of the bid's payment */
} comb_award;

typedef struct {
	bool ok;                  /* false if the auction could not be cleared (too many tasks, out of memory) */
	comb_award *awards;       /* by winning bid in `bids` order, then in the bid's task order */
	size_t award_count;
	int *unallocated;         /* tasks nobody won, in increasing order */
	size_t unallocated_count;
	int64_t welfare;          /* W*: value of the tasks run less the asks of the winning bids */
} comb_outcome;

/* Clear an auction of `task_count` (at most COMB_MAX_TASKS) tasks.
 *
 * Bids naming no tasks, a task twice or a task outside the auction are left out, as are bids asking more than
 * their tasks are worth, since those can never win. Free the result with comb_outcome_free.
 */
comb_outcome vcg_comb_clear(const int64_t *values, size_t task_count,
                            const comb_bid *bids, size_t bid_count, comb_solver solver);

void comb_outcome_free(comb_outcome *outcome);

/* Split `total` in proportion to `weights` into `out`, in whole units that add up to it (largest remainders get the
 * rest, earlier weights first on equal remainders). No part exceeds its weight when total <= sum(weights). */
void comb_split(int64_t total, const int64_t *weights, size_t n, int64_t *out);

const char *comb_solver_name(comb_solver solver);

#endif
