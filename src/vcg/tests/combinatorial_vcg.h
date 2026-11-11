#ifndef _POSIX_C_SOURCE
#define _POSIX_C_SOURCE 199309L
#endif
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include "test_utils.h"
#include "../build/include/vcg_combinatorial.h"

/* Tests of vcg_combinatorial.c. Expected outcomes follow clearing.py; tests/compare_with_python.py checks the
 * library against clearing.py itself. Every solver must give the same outcome as COMB_BRUTE_FORCE. */

#define BID(bidder, price, ...) \
	((comb_bid){(const int[]){__VA_ARGS__}, sizeof((int[]){__VA_ARGS__}) / sizeof(int), (bidder), (price)})
#define COUNT(xs) (sizeof(xs) / sizeof((xs)[0]))

typedef struct {
	int task;
	int bidder;
	int64_t payment;
} expected_award;

static void comb_print_outcome(const char *label, comb_outcome o)
{
	printf("  %s: ok %d, welfare %lld, awards", label, o.ok, (long long) o.welfare);
	for (size_t i = 0; i < o.award_count; i++)
		printf(" (task %d bidder %d bid %zu pays %lld)", o.awards[i].task, o.awards[i].bidder, o.awards[i].bid,
		       (long long) o.awards[i].payment);
	printf(", unallocated");
	for (size_t i = 0; i < o.unallocated_count; i++) printf(" %d", o.unallocated[i]);
	printf("\n");
}

static bool comb_same_outcome(comb_outcome a, comb_outcome b)
{
	if (a.ok != b.ok || a.welfare != b.welfare || a.award_count != b.award_count
	    || a.unallocated_count != b.unallocated_count) return false;
	for (size_t i = 0; i < a.award_count; i++)
		if (a.awards[i].task != b.awards[i].task || a.awards[i].bidder != b.awards[i].bidder
		    || a.awards[i].bid != b.awards[i].bid || a.awards[i].payment != b.awards[i].payment) return false;
	for (size_t i = 0; i < a.unallocated_count; i++)
		if (a.unallocated[i] != b.unallocated[i]) return false;
	return true;
}

/* Clear with every solver and check each against the expected welfare, awards (in order) and unallocated tasks. */
static bool comb_expect(const char *name, const int64_t *values, size_t task_count, const comb_bid *bids,
                        size_t bid_count, int64_t welfare, const expected_award *awards, size_t award_count,
                        const int *unallocated, size_t unallocated_count)
{
	bool result = true;
	for (int s = 0; s < COMB_SOLVER_COUNT; s++) {
		comb_outcome o = vcg_comb_clear(values, task_count, bids, bid_count, (comb_solver) s);
		bool good = o.ok && o.welfare == welfare && o.award_count == award_count
		            && o.unallocated_count == unallocated_count;
		for (size_t i = 0; good && i < award_count; i++)
			good = o.awards[i].task == awards[i].task && o.awards[i].bidder == awards[i].bidder
			       && o.awards[i].payment == awards[i].payment;
		for (size_t i = 0; good && i < unallocated_count; i++)
			good = o.unallocated[i] == unallocated[i];
		if (!good) {
			printf("%s: unexpected outcome from %s\n", name, comb_solver_name((comb_solver) s));
			comb_print_outcome("got", o);
			result = false;
		}
		comb_outcome_free(&o);
	}
	return result;
}

TEST comb_one_task_is_a_second_price_auction()
{
	int64_t values[] = {100};
	comb_bid bids[] = {BID(0, 30, 0), BID(1, 50, 0)};
	expected_award awards[] = {{0, 0, 50}};
	return comb_expect(__func__, values, 1, bids, 2, 70, awards, 1, NULL, 0);
}

TEST comb_payment_is_capped_at_the_task_value()
{
	int64_t values[] = {100};
	comb_bid bids[] = {BID(0, 30, 0), BID(1, 120, 0)};
	expected_award awards[] = {{0, 0, 100}};
	return comb_expect(__func__, values, 1, bids, 2, 70, awards, 1, NULL, 0);
}

TEST comb_a_bundle_beats_dearer_singles()
{
	int64_t values[] = {50, 50};
	comb_bid bids[] = {BID(0, 20, 0, 1), BID(1, 30, 0), BID(2, 30, 1)};
	/* W* = 80; without bidder 0 it is 40, so it is paid 20 + 80 - 40 = 60, split by task value */
	expected_award awards[] = {{0, 0, 30}, {1, 0, 30}};
	return comb_expect(__func__, values, 2, bids, 3, 80, awards, 2, NULL, 0);
}

TEST comb_cheaper_singles_beat_a_bundle()
{
	int64_t values[] = {50, 50};
	comb_bid bids[] = {BID(0, 60, 0, 1), BID(1, 10, 0), BID(2, 10, 1)};
	expected_award awards[] = {{0, 1, 50}, {1, 2, 50}};
	return comb_expect(__func__, values, 2, bids, 3, 80, awards, 2, NULL, 0);
}

TEST comb_a_bidder_wins_at_most_one_bid()
{
	int64_t values[] = {100, 100};
	comb_bid bids[] = {BID(0, 10, 0), BID(0, 10, 1), BID(1, 150, 0, 1)};
	/* Bidder 0 would take both tasks for 180 welfare, but its bids are XOR: it wins the first, task 1 is left */
	expected_award awards[] = {{0, 0, 50}};
	int unallocated[] = {1};
	return comb_expect(__func__, values, 2, bids, 3, 90, awards, 1, unallocated, 1);
}

TEST comb_a_zero_welfare_bid_still_wins()
{
	int64_t values[] = {10};
	comb_bid bids[] = {BID(0, 10, 0)};
	expected_award awards[] = {{0, 0, 10}};
	return comb_expect(__func__, values, 1, bids, 1, 0, awards, 1, NULL, 0);
}

TEST comb_on_equal_welfare_more_tasks_win()
{
	int64_t values[] = {10, 10};
	comb_bid bids[] = {BID(0, 5, 0), BID(1, 15, 0, 1)};
	/* Both have welfare 5; the bundle runs more tasks. Without bidder 1, W* is still 5: it is paid its ask. */
	expected_award awards[] = {{0, 1, 8}, {1, 1, 7}};
	return comb_expect(__func__, values, 2, bids, 2, 5, awards, 2, NULL, 0);
}

TEST comb_on_a_full_tie_the_first_bid_wins()
{
	int64_t values[] = {100};
	comb_bid bids[] = {BID(7, 40, 0), BID(3, 40, 0)};
	expected_award awards[] = {{0, 7, 40}};
	return comb_expect(__func__, values, 1, bids, 2, 60, awards, 1, NULL, 0);
}

TEST comb_invalid_bids_are_left_out()
{
	int64_t values[] = {100, 100};
	comb_bid bids[] = {
		{NULL, 0, 0, 0},  /* no tasks */
		BID(1, 0, 0, 0),  /* a task twice */
		BID(2, 0, 2),     /* a task outside the auction */
		BID(3, 0, -1),    /* likewise */
		BID(4, 101, 0),   /* asks more than the task is worth */
	};
	int unallocated[] = {0, 1};
	return comb_expect(__func__, values, 2, bids, COUNT(bids), 0, NULL, 0, unallocated, 2);
}

TEST comb_no_bids_leave_every_task_unallocated()
{
	int64_t values[] = {5, 6, 7};
	int unallocated[] = {0, 1, 2};
	return comb_expect(__func__, values, 3, NULL, 0, 0, NULL, 0, unallocated, 3);
}

TEST comb_the_64th_task_can_be_auctioned()
{
	int64_t values[COMB_MAX_TASKS];
	int unallocated[COMB_MAX_TASKS - 2];
	for (int t = 0; t < COMB_MAX_TASKS; t++) values[t] = 1;
	for (int t = 1; t < COMB_MAX_TASKS - 1; t++) unallocated[t - 1] = t;
	comb_bid bids[] = {BID(0, 0, 63, 0)};
	expected_award awards[] = {{63, 0, 1}, {0, 0, 1}};
	return comb_expect(__func__, values, COMB_MAX_TASKS, bids, 1, 2, awards, 2, unallocated, COMB_MAX_TASKS - 2);
}

TEST comb_too_many_tasks_fail()
{
	int64_t values[COMB_MAX_TASKS + 1] = {0};
	comb_outcome o = vcg_comb_clear(values, COMB_MAX_TASKS + 1, NULL, 0, COMB_BRUTE_FORCE);
	bool result = !o.ok;
	comb_outcome_free(&o);
	return result;
}

static bool comb_split_is(int64_t total, const int64_t *weights, size_t n, const int64_t *expected)
{
	int64_t out[16];
	comb_split(total, weights, n, out);
	for (size_t i = 0; i < n; i++) {
		if (out[i] != expected[i]) {
			printf("comb_split(%lld): part %zu is %lld, expected %lld\n", (long long) total, i,
			       (long long) out[i], (long long) expected[i]);
			return false;
		}
	}
	return true;
}

TEST comb_split_gives_leftovers_to_the_largest_remainders()
{
	bool result = true;
	result &= comb_split_is(10, (int64_t[]){1, 1, 1}, 3, (int64_t[]){4, 3, 3});
	result &= comb_split_is(7, (int64_t[]){2, 3, 5}, 3, (int64_t[]){1, 2, 4});
	result &= comb_split_is(2, (int64_t[]){1, 1, 1, 1}, 4, (int64_t[]){1, 1, 0, 0});
	result &= comb_split_is(0, (int64_t[]){3, 4}, 2, (int64_t[]){0, 0});
	result &= comb_split_is(5, (int64_t[]){5}, 1, (int64_t[]){5});
	/* Payments times values beyond 64 bits */
	result &= comb_split_is(INT64_MAX / 2, (int64_t[]){INT64_MAX / 2, INT64_MAX / 2}, 2,
	                        (int64_t[]){INT64_MAX / 4 + 1, INT64_MAX / 4});
	return result;
}

/* ---- random auctions ------------------------------------------------------------------------------------------ */

typedef struct {
	int64_t values[COMB_MAX_TASKS];
	size_t task_count;
	comb_bid bids[512];
	int tasks[512][COMB_MAX_TASKS];
	size_t bid_count;
} comb_auction;

static uint64_t comb_rng;

static uint64_t comb_next(void)  /* xorshift64*, so runs repeat on every platform */
{
	comb_rng ^= comb_rng >> 12;
	comb_rng ^= comb_rng << 25;
	comb_rng ^= comb_rng >> 27;
	return comb_rng * 2685821657736338717ULL;
}

static int64_t comb_between(int64_t lo, int64_t hi)
{
	return lo + (int64_t) (comb_next() % (uint64_t) (hi - lo + 1));
}

/* Few distinct values and prices, so there are many ties; bundles of up to `max_bundle` tasks. */
static void comb_random_auction(comb_auction *a, size_t task_count, size_t bid_count, int bidders, int max_bundle)
{
	a->task_count = task_count;
	a->bid_count = bid_count;
	for (size_t t = 0; t < task_count; t++)
		a->values[t] = comb_next() % 2 ? comb_between(1, 12) : comb_between(1, 200);
	for (size_t b = 0; b < bid_count; b++) {
		size_t size = (size_t) comb_between(1, max_bundle < (int) task_count ? max_bundle : (int) task_count);
		uint64_t named = 0;
		int64_t worth = 0;
		for (size_t k = 0; k < size; k++) {
			int t;
			do t = (int) comb_between(0, (int64_t) task_count - 1); while ((named >> t) & 1);
			named |= (uint64_t) 1 << t;
			a->tasks[b][k] = t;
			worth += a->values[t];
		}
		int64_t price;
		switch (comb_next() % 4) {
		case 0:  price = comb_between(0, worth + 5); break;
		case 1:  price = worth; break;
		case 2:  price = comb_between(0, 6); break;
		default: price = comb_between(worth / 2, worth); break;
		}
		comb_bid bid = {a->tasks[b], size, (int) comb_between(0, bidders - 1), price};
		a->bids[b] = bid;
	}
}

/* Properties every VCG outcome here must have. */
static bool comb_check_properties(const comb_auction *a, comb_outcome o)
{
	if (!o.ok) return false;
	uint64_t awarded = 0;
	int64_t welfare = 0;
	for (size_t i = 0; i < o.award_count;) {
		size_t b = o.awards[i].bid;
		const comb_bid *bid = &a->bids[b];
		int64_t paid = 0, worth = 0;
		for (size_t k = 0; k < bid->task_count; k++, i++) {
			const comb_award *aw = &o.awards[i];
			if (i >= o.award_count || aw->bid != b || aw->task != bid->tasks[k] || aw->bidder != bid->bidder)
				return false;
			if ((awarded >> aw->task) & 1) return false;  /* a task awarded twice */
			if (aw->payment < 0 || aw->payment > a->values[aw->task]) return false;  /* over a task's budget */
			awarded |= (uint64_t) 1 << aw->task;
			paid += aw->payment;
			worth += a->values[aw->task];
		}
		if (paid < bid->price || paid > worth) return false;  /* individually rational, within budget */
		welfare += worth - bid->price;
		for (size_t j = 0; j < i - bid->task_count; j++)  /* XOR: one winning bid per bidder */
			if (o.awards[j].bidder == bid->bidder) return false;
	}
	if (welfare != o.welfare) return false;
	size_t u = 0;
	for (size_t t = 0; t < a->task_count; t++)
		if (!((awarded >> t) & 1) && (u >= o.unallocated_count || o.unallocated[u++] != (int) t)) return false;
	return u == o.unallocated_count;
}

/* Clears `rounds` random auctions with every solver from `reference` on and checks each outcome equals the
 * reference's, and that the reference's has the VCG properties. */
static bool comb_differential(comb_solver reference_solver, uint64_t first_seed, int rounds, int max_tasks,
                              int min_bids, int max_bids, int max_bidders, int max_bundle)
{
	static comb_auction a;
	bool result = true;
	for (uint64_t seed = first_seed; seed < first_seed + (uint64_t) rounds && result; seed++) {
		comb_rng = seed * 0x9E3779B97F4A7C15ULL;
		size_t tasks = (size_t) comb_between(1, max_tasks);
		size_t bids = (size_t) comb_between(min_bids, max_bids);
		comb_random_auction(&a, tasks, bids, (int) comb_between(1, max_bidders), (int) comb_between(1, max_bundle));

		comb_outcome reference = vcg_comb_clear(a.values, a.task_count, a.bids, a.bid_count, reference_solver);
		if (!comb_check_properties(&a, reference)) {
			printf("seed %llu: %s outcome breaks a VCG property\n", (unsigned long long) seed,
			       comb_solver_name(reference_solver));
			comb_print_outcome(comb_solver_name(reference_solver), reference);
			result = false;
		}
		for (int s = reference_solver + 1; s < COMB_SOLVER_COUNT && result; s++) {
			comb_outcome o = vcg_comb_clear(a.values, a.task_count, a.bids, a.bid_count, (comb_solver) s);
			if (!comb_same_outcome(reference, o)) {
				printf("seed %llu: %s differs from %s\n", (unsigned long long) seed,
				       comb_solver_name((comb_solver) s), comb_solver_name(reference_solver));
				comb_print_outcome(comb_solver_name(reference_solver), reference);
				comb_print_outcome(comb_solver_name((comb_solver) s), o);
				result = false;
			}
			comb_outcome_free(&o);
		}
		comb_outcome_free(&reference);
	}
	if (result) printf("%d random auctions: every solver matches %s\n", rounds, comb_solver_name(reference_solver));
	return result;
}

TEST comb_every_solver_matches_brute_force_on_small_auctions()
{
	return comb_differential(COMB_BRUTE_FORCE, 1, 5000, 12, 0, 18, 7, 4);
}

TEST comb_every_solver_matches_brute_force_on_larger_auctions()
{
	return comb_differential(COMB_BRUTE_FORCE, 100000, 300, 24, 16, 40, 14, 5);
}

/* Too big for brute force: branch and bound, itself checked against brute force above, is the reference. */
TEST comb_faster_solvers_match_branch_and_bound_on_big_auctions()
{
	return comb_differential(COMB_BRANCH_AND_BOUND, 200000, 150, 32, 32, 56, 20, 5);
}

static double comb_seconds(void)
{
	struct timespec ts;
	clock_gettime(CLOCK_MONOTONIC, &ts);
	return (double) ts.tv_sec + (double) ts.tv_nsec / 1e9;
}

/* Prints how long each solver takes as auctions grow; fails only if the solvers disagree. A solver is skipped
 * once it gets slow. */
TEST comb_timing()
{
	static comb_auction a;
	bool result = true;
	bool too_slow[COMB_SOLVER_COUNT] = {false};
	printf("%6s %6s %8s", "tasks", "bids", "bidders");
	for (int s = 0; s < COMB_SOLVER_COUNT; s++) printf(" %18s", comb_solver_name((comb_solver) s));
	printf("%14s", "timestamp");
	printf("\n");
	for (size_t bids = 8; bids <= 512; bids += bids < 128 ? 8 : 32) {
		size_t tasks = bids / 2 < COMB_MAX_TASKS ? bids / 2 : COMB_MAX_TASKS;
		int bidders = (int) bids / 3;
		comb_rng = 0xC0FFEE + bids;
		comb_random_auction(&a, tasks, bids, bidders, 4);
		printf("%6zu %6zu %8d", tasks, bids, bidders);
		comb_outcome reference = {0};
		bool have_reference = false;
		for (int s = 0; s < COMB_SOLVER_COUNT; s++) {
			if (too_slow[s] && s != COMB_SOLVER_COUNT-1 && s != COMB_SOLVER_COUNT -2) {
				printf(" %18s", "skipped");
				continue;
			}
			double start = comb_seconds();
			comb_outcome o = vcg_comb_clear(a.values, a.task_count, a.bids, a.bid_count, (comb_solver) s);
			double took = comb_seconds() - start;
			printf(" %17.6fs", took);
			if (took > 2.0) too_slow[s] = true;
			if (!have_reference) {
				reference = o;
				have_reference = true;
				result &= comb_check_properties(&a, o);
			} else {
				result &= comb_same_outcome(reference, o);
				comb_outcome_free(&o);
			}
		}
		time_t cur_time = time(NULL);
		printf("%30s", ctime(&cur_time));
		comb_outcome_free(&reference);
		fflush(stdout);
	}
	return result;
}
