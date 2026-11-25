/* Combinatorial VCG auction: a C port of clearing.py, plus faster solvers that give the same answers.
 *
 * ==== The auction ====================================================================================================
 *
 * It is a *reverse* auction: the house has tasks it wants run and pays bidders to run them.
 *
 *   - Every task t has a value, values[t]: the most its submitter will pay to have it run (its budget).
 *   - A bidder places bids. A bid names a set of tasks (a "bundle") and a price: "I will run all of these for this
 *     much". Bundles matter because running one task can change what another costs the bidder.
 *   - Bids are XOR: a bidder wins at most one of its bids. Its bids on {A}, {B} and {A, B} are alternatives, each
 *     priced as if it were the only work the bidder takes on.
 *
 * ==== Welfare ========================================================================================================
 *
 * The welfare of a winning bid is what it creates for everyone together: the value of its tasks less the price the
 * bidder asks,
 *
 *     welfare(bid) = sum of values[t] over the bid's tasks  -  price
 *
 * Any number of bids may name the same task: that is how bidders compete for it. But only some bids win, and the set
 * of bids that win together (an "allocation") must be one the house can actually carry out. It is "feasible" when:
 *   - no task is in two of its bids, since each task is run once, by one bidder. If X bids on {A, B} and Y on {A},
 *     both bids take part in the auction, but they cannot both win, as that would pay twice for running A;
 *   - no bidder has two of its bids in it (bids are XOR).
 * The welfare of an allocation is the sum over its bids. The auction picks the feasible allocation with the most
 * welfare; call that welfare W*.
 *
 * ==== VCG payments ===================================================================================================
 *
 * Paying each winner its asked price would invite bidders to ask more than their cost. VCG instead pays each winner
 * its price plus what its participation adds to the welfare (the "Clarke pivot"):
 *
 *     payment = price + W* - W*_without
 *
 * where W*_without is the best welfare possible if that bidder had not taken part at all (all of its bids removed).
 *
 * Example: tasks A and B are worth 50 each. X asks 20 for {A, B}, Y asks 30 for {A}, Z asks 30 for {B}.
 *     welfare: X = 100 - 20 = 80, Y = 50 - 30 = 20, Z = 50 - 30 = 20.
 *     Best allocation: X alone (80). Y + Z only reaches 40. So W* = 80, and X wins both tasks.
 *     Without X the best is Y + Z: W*_without = 40.
 *     X is paid 20 + 80 - 40 = 60: its ask of 20, plus the 40 its bid adds over the next best allocation.
 *
 * Why this makes asking your true cost the best strategy: W* contains X's own `- price`, so the price cancels out of
 * the payment, and X's profit (payment less its true cost) works out to the *true* welfare of the chosen allocation
 * less W*_without. X cannot change W*_without (it does not take part there), so X does best when the auction picks
 * the allocation with the most true welfare, which it does when X asks its true cost.
 *
 * Two guarantees follow, and the tests check both:
 *   - payment >= price: removing a bidder can only lower the best welfare, so W* >= W*_without.
 *   - payment <= value of the bid's tasks: the best allocation less X's bid is still feasible without X, so
 *     W*_without >= W* - welfare(X's bid), and so payment <= price + welfare(X's bid) = value. No submitter pays more
 *     than its budget.
 *
 * Payments are per bid, but the house pays per task, so each payment is split over the bid's tasks in proportion to
 * their values (comb_split). With the guarantee above, no task's share exceeds its value.
 *
 * ==== Ties ===========================================================================================================
 *
 * Several allocations can have the same, best, welfare. clearing.py prefers the one running more tasks (so a bid of
 * welfare 0 still gets its tasks run), and of those the first one its search tries. The search tries allocations in a
 * fixed order (see brute_extend), so "first tried" is well defined. Every solver here picks that same allocation;
 * that is what lets the tests demand identical outcomes from all of them.
 *
 * We compare allocations by their "key": the pair (welfare, number of tasks run), compared welfare first. "Best"
 * always means the greatest key.
 *
 * ==== How the file is laid out =======================================================================================
 *   Used for splitting payments to different submitters, since VCG only pays per bid, but the house pays per task.
 *   1. comb_split            splitting a bid's payment over its tasks.
 *   For efficiency
 *   2. build_candidates      dropping bids that can never win, and turning the rest into a compact form.
 * 
 *   3. brute_extend          the brute-force search: try every feasible allocation (COMB_BRUTE_FORCE).
 *   
 *   Splits the search into branches, and prunes branches that cannot beat the best allocation found so far. 
 *   The pruning uses precomputed upper bounds on how much welfare can be added by the candidates still available, and stops the search as soon as it finds an allocation that reaches a known best key (COMB_BRANCH_AND_BOUND).
 *   It does this via calculating the max welfare of a given bid, then overestimating welfare of candidates.
 *   If they still dont have a larger welfare than the best allocation found so far, then it prunes that branch and moves on to the next candidate.   
 * 
 *   4. bounds, bnb_extend    the same search, skipping parts that cannot win (COMB_BRANCH_AND_BOUND).
 * 
 *   
 *   5. best_key, completes,  find the best key quickly, then rebuild the allocation brute force would have picked
 *      first_with_key        (COMB_FAST_PIVOTS).
 *   6. welfare_without,      W*_without for every winner, optionally on several threads (COMB_PARALLEL_PIVOTS).
 *      pivots
 *   7. vcg_comb_clear        putting it together: allocation, payments, awards.
 *
 * ==== Sets of tasks as bits ==========================================================================================
 *
 * A set of tasks is stored as a 64 bit number whose bit t is 1 when task t is in the set (which is why an auction
 * has at most COMB_MAX_TASKS = 64 tasks). That makes the set operations the search needs single instructions:
 *
 *     a & b            the tasks in both a and b; non-zero means the two bids overlap and cannot both win
 *     a | b            the tasks in either (the union)
 *     a & ~b           the tasks in a but not in b
 *     __builtin_popcountll(a)   how many tasks are in a
 *     __builtin_ctzll(a)        the lowest task in a
 *     a &= a - 1               remove the lowest task from a; looping on it visits every task in a
 */
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "vcg_combinatorial.h"

/* How many threads COMB_PARALLEL_PIVOTS may use. The makefile sets it from the number of cores. */
#ifndef PROCS
#define PROCS 1
#endif

/* A 128 bit integer. The payment split multiplies a payment by a task value, and the product of two 64 bit numbers
 * can need up to 128 bits. (__extension__ keeps -pedantic from rejecting the non-standard type.) */
__extension__ typedef __int128 wide;

/* A bid that can win: it is valid and asks no more than its tasks are worth. The searches work on these only. */
typedef struct {
	size_t bid;       /* index of the bid in the caller's `bids`, to find it again for the awards */
	uint64_t tasks;   /* the bid's tasks, as bits (bit t set when the bid names task t) */
	int ntasks;       /* how many tasks it names */
	int bidder;       /* the bidder, renumbered 0..nbidders-1 so it can index an array */
	int64_t welfare;  /* value of its tasks less its price; >= 0, as bids with less are dropped */
} candidate;

/* Precomputed upper bounds used by branch and bound (see bnb_extend) to skip parts of the search.
 *
 * The search adds candidates in index order, so at any point only candidates from some position k onwards can still
 * be added. Each table answers, for every position k: "using only candidates k, k+1, ..., n-1, at most how much more
 * welfare (or how many more tasks) could we get?". The answers never grow as k grows (fewer candidates are left),
 * which the search relies on to stop early. Row n (no candidates left) is all zero. */
typedef struct {
	/* cover[k]: every task named by some candidate from k on. Tasks outside it can no longer be run, so at most
	 * popcount(cover[k] & tasks still free) more tasks can be. */
	uint64_t *cover;

	/* share[k * COMB_MAX_TASKS + t]: the most welfare *per task* of any candidate from k on that names task t,
	 * rounded up. A candidate of welfare 10 over 3 tasks gives each of its tasks a share of 4 (10/3 rounded up).
	 * In any allocation each task is in at most one bid, and a bid's welfare is at most the sum of its tasks' shares,
	 * so the welfare candidates from k on can add is at most the sum of the shares of the tasks still free. Rounding
	 * up keeps that true with whole numbers. */
	int64_t *share;

	/* bidder_best[k * nbidders + b]: the most welfare of any one candidate of bidder b from k on. A bidder wins at
	 * most one bid, so the welfare to be added is also at most the sum of these over the bidders not yet used.
	 * NULL when the table would be too large (BIDDER_BOUND_MAX_ENTRIES); the search then uses the share bound only. */
	int64_t *bidder_best;

	/* bidder_sum[k]: bidder_best[k * nbidders + b] summed over all bidders b, so the bound for "all bidders except the
	 * few already used" is this sum less the used ones, without looping over every bidder. */
	int64_t *bidder_sum;

	size_t nbidders;
} bounds;

#define BIDDER_BOUND_MAX_ENTRIES ((size_t) 1 << 22)  /* 32 MiB of int64_t */

/* One search for the best allocation. The searches are recursive: they build an allocation one candidate at a time,
 * and this holds what has been chosen so far and the best allocation found so far. */
typedef struct {
	const candidate *c;    /* the candidates to choose from, in the order the search tries them */
	size_t n;
	size_t nbidders;
	const bounds *bounds;  /* the pruning tables; NULL for brute force */

	/* What the search is for. The default (after search_init) is the best allocation, by key. */
	bool keep_set;         /* remember which candidates make up the best allocation; when false only its key
	                        * (welfare, tasks) is wanted, which saves copying */
	bool welfare_only;     /* the key is welfare alone, ignoring the number of tasks (implies !keep_set). Enough
	                        * for W*_without, which is only a number in the payment formula */
	bool has_goal;         /* the best key is already known to be (goal_welfare, goal_tasks). The search then skips
	                        * anything that cannot reach it, and stops as soon as it finds an allocation that does */
	int64_t goal_welfare;
	int goal_tasks;
	bool done;             /* set once the goal is reached, to unwind the recursion */

	/* The allocation being built */
	unsigned char *used;   /* used[b] is 1 when bidder b already has a bid in it (bids are XOR) */
	size_t *chosen;        /* its candidates (indices into c), in the order they were added */
	size_t nchosen;

	/* The best allocation found so far */
	size_t *best;          /* its candidates, if keep_set */
	size_t nbest;
	int64_t best_welfare;  /* its key. Starts as the empty allocation's, (0, 0), or as a "seed": a welfare known to */
	int best_tasks;        /* be reachable, so that the search only looks for better */
} search;

const char *comb_solver_name(comb_solver solver)
{
	switch (solver) {
	case COMB_BRUTE_FORCE:      return "brute force";
	case COMB_BRANCH_AND_BOUND: return "branch and bound";
	case COMB_FAST_PIVOTS:      return "fast pivots";
	case COMB_PARALLEL_PIVOTS:  return "parallel pivots";
	default:                    return "unknown";
	}
}

/* ==== 1. Splitting a payment over a bid's tasks =================================================================== */

/* Python's // and %, which this must match exactly: the quotient rounds down (towards minus infinity), and the
 * remainder has the sign of the divisor. C's / and % round towards zero instead, which differs for negative numbers. */
static wide floor_div(wide a, wide b)
{
	wide q = a / b;
	if (a % b != 0 && ((a < 0) != (b < 0))) q--;
	return q;
}

static wide floor_mod(wide a, wide b)
{
	return a - b * floor_div(a, b);
}

/* The order in which leftover units are handed out: larger remainder first, and on equal remainders the earlier
 * task first. (clearing.py sorts by remainder with Python's sort, which keeps equal items in their original order.)
 * True when (remainder ri, index i) comes before (rj, j). */
static bool remainder_before(wide ri, size_t i, wide rj, size_t j)
{
	return ri > rj || (ri == rj && i < j);
}

/* Split `total` into whole units, in proportion to `weights` (the task values).
 *
 * Each part first gets its exact share rounded down; the units this leaves over go one each to the parts that lost
 * the most to rounding (the largest remainders). Example: 7 split by 2, 3, 5 is exactly 1.4, 2.1 and 3.5; rounded
 * down that is 1, 2, 3 = 6, so 1 unit is left, and it goes to the part that lost .5: the split is 1, 2, 4. */
void comb_split(int64_t total, const int64_t *weights, size_t n, int64_t *out)
{
	if (n == 0) return;
	for (size_t i = 0; i < n; i++) out[i] = 0;
	if (total == 0) return;

	wide whole = 0;
	for (size_t i = 0; i < n; i++) whole += weights[i];
	if (whole == 0) {  /* clearing.py raises here; task values are positive in practice */
		out[0] = total;
		return;
	}

	/* The exact share of part i is total * weights[i] / whole; round it down */
	wide sum = 0;
	for (size_t i = 0; i < n; i++) {
		out[i] = (int64_t) floor_div((wide) total * weights[i], whole);
		sum += out[i];
	}

	/* How many parts get a leftover unit. clearing.py writes this as by_remainder[:total - sum(parts)], so this copies
	 * what a Python slice does with that number (negative counts from the end, too large means everything). With
	 * positive weights it is simply total - sum. */
	wide left = total - sum;
	size_t count;
	if (left >= 0) count = left > (wide) n ? n : (size_t) left;
	else count = -left >= (wide) n ? 0 : (size_t) ((wide) n + left);

	/* Hand out the units: each round finds the next part in remainder order after the one picked last round.
	 * (Re-scanning instead of sorting avoids allocating; a bid has at most 64 tasks.) */
	bool have_prev = false;
	wide prev_r = 0;
	size_t prev_i = 0;
	for (size_t k = 0; k < count; k++) {
		bool found = false;
		wide next_r = 0;
		size_t next_i = 0;
		for (size_t i = 0; i < n; i++) {
			wide r = floor_mod((wide) total * weights[i], whole);  /* what part i lost to rounding (times whole) */
			if (have_prev && !remainder_before(prev_r, prev_i, r, i)) continue;  /* already got its unit */
			if (!found || remainder_before(r, i, next_r, next_i)) {
				found = true;
				next_r = r;
				next_i = i;
			}
		}
		out[next_i]++;
		have_prev = true;
		prev_r = next_r;
		prev_i = next_i;
	}
}

/* ==== 2. Candidates: the bids that can win ======================================================================== */
// Function for comparing two integers, used for sorting and searching bidder IDs.
static int compare_int(const void *a, const void *b)
{
	int x = *(const int *) a, y = *(const int *) b;
	return (x > y) - (x < y);
}

/* Turn the bids into candidates, keeping their order (the order decides ties) and leaving out bids that:
 *   - name no tasks, name a task twice or name a task outside the auction (invalid), or
 *   - ask more than their tasks are worth (negative welfare). Such a bid can never be in the best allocation:
 *     dropping it from any allocation would raise the welfare.
 * Bidder ids can be any ints; they are renumbered 0..nbidders-1 (in increasing order of id) so the search can keep
 * "has this bidder won already" in a plain array. */
static candidate *build_candidates(const int64_t *values, size_t task_count, const comb_bid *bids, size_t bid_count,
                                   size_t *ncandidates, size_t *nbidders)
{
	candidate *c = malloc(sizeof(candidate) * (bid_count ? bid_count : 1));
	int *ids = malloc(sizeof(int) * (bid_count ? bid_count : 1));
	if (c == NULL || ids == NULL) {
		free(c);
		free(ids);
		return NULL;
	}

	// First pass: filter bids for invalidity and compute welfare, while collecting bidder IDs.
	size_t n = 0;
	for (size_t b = 0; b < bid_count; b++) {
		const comb_bid *bid = &bids[b];
		if (bid->task_count == 0 || bid->tasks == NULL) continue;
		uint64_t tasks = 0;
		int64_t value = 0;
		bool valid = true;
		for (size_t k = 0; k < bid->task_count && valid; k++) {
			int t = bid->tasks[k];
			if (t < 0 || (size_t) t >= task_count || (tasks >> t) & 1) {  /* outside the auction, or seen before */
				valid = false;
			} else {
				tasks |= (uint64_t) 1 << t;
				value += values[t];
			}
		}

		// if the bid is valid and its welfare is non-negative, add it to the candidates list.
		if (!valid || value - bid->price < 0) continue;
		c[n].bid = b;
		c[n].tasks = tasks;
		c[n].ntasks = (int) bid->task_count;
		c[n].bidder = bid->bidder;  /* the caller's id for now; renumbered below */
		c[n].welfare = value - bid->price;
		ids[n] = bid->bidder;
		n++;
	}

	/* Renumber bidders: sort the ids and drop repeats, then each bidder's new number is its position in that list */
	qsort(ids, n, sizeof(int), compare_int);
	size_t unique = 0;
	for (size_t i = 0; i < n; i++)
		if (unique == 0 || ids[unique - 1] != ids[i]) ids[unique++] = ids[i];
	for (size_t i = 0; i < n; i++)
		c[i].bidder = (int) ((int *) bsearch(&c[i].bidder, ids, unique, sizeof(int), compare_int) - ids);

	free(ids);
	*ncandidates = n;
	*nbidders = unique;
	return c;
}

/* The candidates with every bid of `bidder` removed, in the same order: the auction as it would have been had that
 * bidder not taken part. Searching it gives W*_without for the bidder's payment. */
static candidate *without_bidder(const candidate *c, size_t n, int bidder, size_t *out_n)
{
	candidate *out = malloc(sizeof(candidate) * (n ? n : 1));
	if (out == NULL) return NULL;
	size_t m = 0;
	for (size_t i = 0; i < n; i++)
		if (c[i].bidder != bidder) out[m++] = c[i];
	*out_n = m;
	return out;
}

/* ==== 3. Brute force: try every feasible allocation =============================================================== */

/* Prepare a search over candidates c. By default it looks for the best allocation and remembers it. */
static bool search_init(search *s, const candidate *c, size_t n, size_t nbidders)
{
	/* An allocation has at most 64 bids, since each runs at least one task and no task is run twice */
	size_t depth = (n < COMB_MAX_TASKS ? n : COMB_MAX_TASKS) + 1;
	memset(s, 0, sizeof(*s));
	s->c = c;
	s->n = n;
	s->nbidders = nbidders;
	s->keep_set = true;
	s->used = calloc(nbidders ? nbidders : 1, 1);
	s->chosen = malloc(sizeof(size_t) * depth);
	s->best = malloc(sizeof(size_t) * depth);
	return s->used != NULL && s->chosen != NULL && s->best != NULL;
}

static void search_free(search *s)
{
	free(s->used);
	free(s->chosen);
	free(s->best);
}

/* clearing.py's `extend`. The candidates chosen so far (s->chosen) run `tasks` (ntasks of them) for `welfare`; try
 * adding each candidate from `start` on, and from each, recursively, every way to continue.
 *
 * Only candidates after the last one added are tried, so every allocation is built exactly once, with its candidates
 * in increasing index order. With 3 candidates the allocations are tried in this order:
 *
 *     {0}, {0,1}, {0,1,2}, {0,2}, {1}, {1,2}, {2}
 *
 * (each allocation right before its extensions; a candidate is skipped when it overlaps one already chosen, by task
 * or by bidder). An allocation replaces the best only if its key is strictly greater, so on a tie the one tried first
 * stays: this order is what defines the tie-break that every other solver has to reproduce.
 *
 * The number of allocations grows exponentially with the number of bids, which is why the other solvers exist. */
static void brute_extend(search *s, size_t start, uint64_t tasks, int ntasks, int64_t welfare)
{
	for (size_t k = start; k < s->n; k++) {
		const candidate *c = &s->c[k];
		if (s->used[c->bidder] || (c->tasks & tasks)) continue;  /* bidder already won, or a task already taken */

		/* Add candidate k, and see whether that beats the best so far */
		s->chosen[s->nchosen++] = k;
		int64_t w = welfare + c->welfare;
		int n = ntasks + c->ntasks;
		if (w > s->best_welfare || (w == s->best_welfare && n > s->best_tasks)) {
			s->best_welfare = w;
			s->best_tasks = n;
			memcpy(s->best, s->chosen, sizeof(size_t) * s->nchosen);
			s->nbest = s->nchosen;
		}

		/* Try every way to continue with k in, then take k out again and move on to k + 1 */
		s->used[c->bidder] = 1;
		brute_extend(s, k + 1, tasks | c->tasks, n, w);
		s->used[c->bidder] = 0;
		s->nchosen--;
	}
}

/* ==== 4. Branch and bound: skip what cannot win =================================================================== */

static void bounds_free(bounds *b)
{
	free(b->cover);
	free(b->share);
	free(b->bidder_best);
	free(b->bidder_sum);
}

/* Fill the tables of `bounds` (see its definition) for candidates c. */
static bool bounds_init(bounds *b, const candidate *c, size_t n, size_t nbidders)
{
	memset(b, 0, sizeof(*b));
	b->nbidders = nbidders;
	b->cover = malloc(sizeof(uint64_t) * (n + 1));
	b->share = malloc(sizeof(int64_t) * (n + 1) * COMB_MAX_TASKS);
	b->bidder_sum = malloc(sizeof(int64_t) * (n + 1));
	if (nbidders > 0 && (n + 1) <= BIDDER_BOUND_MAX_ENTRIES / nbidders) {
		b->bidder_best = malloc(sizeof(int64_t) * (n + 1) * nbidders);
		if (b->bidder_best == NULL) goto fail;
	}
	if (b->cover == NULL || b->share == NULL || b->bidder_sum == NULL) goto fail;

	/* Fill from the back. Row n (no candidates left) is all zero; row k is row k+1 with candidate k taken into
	 * account. */
	b->cover[n] = 0;
	b->bidder_sum[n] = 0;
	memset(&b->share[n * COMB_MAX_TASKS], 0, sizeof(int64_t) * COMB_MAX_TASKS);
	if (b->bidder_best != NULL) memset(&b->bidder_best[n * nbidders], 0, sizeof(int64_t) * nbidders);
	for (size_t k = n; k-- > 0;) {
		const candidate *ck = &c[k];
		b->cover[k] = b->cover[k + 1] | ck->tasks;

		int64_t *share = &b->share[k * COMB_MAX_TASKS];
		memcpy(share, share + COMB_MAX_TASKS, sizeof(int64_t) * COMB_MAX_TASKS);
		int64_t per_task = (ck->welfare + ck->ntasks - 1) / ck->ntasks;  /* welfare / ntasks, rounded up */
		for (uint64_t f = ck->tasks; f; f &= f - 1) {  /* for each task t of candidate k */
			int t = __builtin_ctzll(f);
			if (per_task > share[t]) share[t] = per_task;
		}

		b->bidder_sum[k] = b->bidder_sum[k + 1];
		if (b->bidder_best != NULL) {
			int64_t *row = &b->bidder_best[k * nbidders];
			memcpy(row, row + nbidders, sizeof(int64_t) * nbidders);
			if (ck->welfare > row[ck->bidder]) {  /* a new best for this bidder: the sum grows by the difference */
				b->bidder_sum[k] += ck->welfare - row[ck->bidder];
				row[ck->bidder] = ck->welfare;
			}
		}
	}
	return true;

fail:
	bounds_free(b);
	return false;
}

/* At most how much welfare candidates from k on can add to the ones already chosen, if they may only use the tasks
 * in `open` (the ones not taken yet). Two independent limits; the smaller is the better one:
 *   - by task: the sum of the free tasks' shares;
 *   - by bidder: each bidder not yet used adds at most its best remaining candidate. */
static int64_t welfare_bound(const search *s, size_t k, uint64_t open)
{
	const bounds *b = s->bounds;
	const int64_t *share = &b->share[k * COMB_MAX_TASKS];
	int64_t by_task = 0;
	for (uint64_t f = open; f; f &= f - 1) by_task += share[__builtin_ctzll(f)];
	if (b->bidder_best == NULL) return by_task;

	const int64_t *row = &b->bidder_best[k * b->nbidders];
	int64_t by_bidder = b->bidder_sum[k];
	for (size_t i = 0; i < s->nchosen; i++) by_bidder -= row[s->c[s->chosen[i]].bidder];  /* used bidders add 0 */
	return by_task < by_bidder ? by_task : by_bidder;
}

/* brute_extend with "pruning": before trying candidate k, work out the best key any allocation continuing from here
 * with candidates k, k+1, ... could possibly have. If even that cannot beat the best allocation found so far, nothing
 * from here on can, so the whole rest of the loop (and everything it would have recursed into) is skipped.
 *
 * It tries allocations in the same order as brute_extend, and finds the same allocation, including on ties: a part
 * of the search whose best possible key only *equals* the best so far is skipped too, but everything in it comes later
 * in the order, and on a tie the earlier allocation is kept anyway.
 *
 * The same function serves the other searches, through the flags in `search`:
 *   - welfare_only: compare by welfare alone;
 *   - has_goal: the best key is known; also skip what cannot reach it, and stop at the first allocation that does
 *     (s->done). */
static void bnb_extend(search *s, size_t start, uint64_t tasks, int ntasks, int64_t welfare)
{
	for (size_t k = start; k < s->n && !s->done; k++) {
		/* The best key reachable from here: (most, most_tasks). The bounds only shrink as k grows, so once they fail
		 * for this k they fail for every later k too, and the loop can end (return) rather than move on. */
		uint64_t open = s->bounds->cover[k] & ~tasks;  /* free tasks that some remaining candidate could run */
		int64_t most = welfare + welfare_bound(s, k, open);
		int most_tasks = ntasks + __builtin_popcountll(open);
		if (s->has_goal && (most < s->goal_welfare || (most == s->goal_welfare && most_tasks < s->goal_tasks)))
			return;  /* cannot reach the known best key */
		if (most < s->best_welfare) return;  /* cannot beat the best so far */
		if (most == s->best_welfare && (s->welfare_only || most_tasks <= s->best_tasks)) return;  /* at best a tie */

		/* From here on it is brute_extend */
		const candidate *c = &s->c[k];
		if (s->used[c->bidder] || (c->tasks & tasks)) continue;
		s->chosen[s->nchosen++] = k;
		int64_t w = welfare + c->welfare;
		int n = ntasks + c->ntasks;
		if (w > s->best_welfare || (!s->welfare_only && w == s->best_welfare && n > s->best_tasks)) {
			s->best_welfare = w;
			s->best_tasks = n;
			if (s->keep_set) {
				memcpy(s->best, s->chosen, sizeof(size_t) * s->nchosen);
				s->nbest = s->nchosen;
			}
			if (s->has_goal && w == s->goal_welfare && n == s->goal_tasks) s->done = true;
		}
		if (!s->done) {
			s->used[c->bidder] = 1;
			bnb_extend(s, k + 1, tasks | c->tasks, n, w);
			s->used[c->bidder] = 0;
		}
		s->nchosen--;
	}
}

/* Run a search set up with search_init (and its flags set), by brute force or by branch and bound. */
static bool search_run(search *s, bool branch_and_bound)
{
	/* Nothing to find if the starting point already is the goal */
	if (s->has_goal && s->best_welfare == s->goal_welfare && s->best_tasks == s->goal_tasks) s->done = true;
	if (s->done) return true;
	if (!branch_and_bound) {
		brute_extend(s, 0, 0, 0, 0);
		return true;
	}
	bounds b;
	if (!bounds_init(&b, s->c, s->n, s->nbidders)) return false;
	s->bounds = &b;
	bnb_extend(s, 0, 0, 0, 0);
	s->bounds = NULL;
	bounds_free(&b);
	return true;
}

/* ==== 5. Fast: find the best key first, then the allocation ======================================================= */

/* Order for searches that only need the best key, not the tie-break: most welfare per task first ("densest"), and on
 * equal density the original order. Good bids early means a strong "best so far" early, so branch and bound can skip
 * much more. (x->welfare / x->ntasks > y->welfare / y->ntasks is compared multiplied out, to stay in whole numbers.) */
static int by_density(const void *a, const void *b)
{
	const candidate *x = a, *y = b;
	wide lhs = (wide) x->welfare * y->ntasks, rhs = (wide) y->welfare * x->ntasks;
	if (lhs != rhs) return lhs > rhs ? -1 : 1;
	return (x->bid > y->bid) - (x->bid < y->bid);
}

/* The best key over candidates c: the most welfare and, unless `welfare_only`, the most tasks run at that welfare.
 * Not which allocation has it: that would depend on the order, and this search changes the order to densest first.
 * `seed` is a welfare known to be reachable (0, the empty allocation, if none is known); the search only looks for
 * better than it. */
static bool best_key(const candidate *c, size_t n, size_t nbidders, bool welfare_only, int64_t seed,
                     int64_t *welfare, int *tasks)
{
	candidate *sorted = malloc(sizeof(candidate) * (n ? n : 1));
	if (sorted == NULL) return false;
	memcpy(sorted, c, sizeof(candidate) * n);
	qsort(sorted, n, sizeof(candidate), by_density);
	search s;
	bool ok = search_init(&s, sorted, n, nbidders);
	if (ok) {
		s.keep_set = false;
		s.welfare_only = welfare_only;
		s.best_welfare = seed;
		ok = search_run(&s, true);
	}
	*welfare = s.best_welfare;
	if (tasks != NULL) *tasks = s.best_tasks;
	search_free(&s);
	free(sorted);
	return ok;
}

/* Can the candidates from position `from` on, leaving out those that use any of `tasks` or a bidder marked in `used`,
 * make up an allocation whose key is exactly (welfare, ntasks)? Used by first_with_key to ask "if I take these
 * candidates, can the rest still add up to the best key?".
 *
 * There, (welfare, ntasks) is the best key less the key of what has been taken already. No allocation of the
 * remaining candidates can exceed it (together with what was taken, it would beat the best key), so "is it reached"
 * is the same as "is it the best key of the remaining candidates". That is a search with a goal, in densest-first
 * order, which stops at the first allocation reaching it. */
static bool completes(const candidate *c, size_t n, size_t nbidders, size_t from, uint64_t tasks,
                      const unsigned char *used, int64_t welfare, int ntasks, bool *ok)
{
	if (welfare == 0 && ntasks == 0) return true;  /* nothing more needed: the empty allocation does it */
	if (welfare < 0 || ntasks <= 0) return false;  /* candidates only add welfare and tasks */
	candidate *rest = malloc(sizeof(candidate) * (n - from ? n - from : 1));
	if (rest == NULL) {
		*ok = false;
		return false;
	}
	size_t m = 0;
	for (size_t j = from; j < n; j++)
		if (!(c[j].tasks & tasks) && !used[c[j].bidder]) rest[m++] = c[j];
	qsort(rest, m, sizeof(candidate), by_density);

	search s;
	bool found = false;
	if (search_init(&s, rest, m, nbidders)) {
		s.keep_set = false;
		s.has_goal = true;
		s.goal_welfare = welfare;
		s.goal_tasks = ntasks;
		if (search_run(&s, true)) found = s.done;
		else *ok = false;
	} else {
		*ok = false;
	}
	search_free(&s);
	free(rest);
	return found;
}

/* The allocation brute force picks, given the best key (welfare, ntasks).
 *
 * Brute force keeps, of all allocations with the best key, the first one it tries. Its order (see brute_extend) puts
 * allocations with a lower first candidate earlier; among those with the same first candidate, a lower second
 * candidate earlier, and so on. So the allocation it keeps is the one with the lowest possible first candidate, then
 * the lowest possible second candidate, and so on, and it can be built directly, one candidate at a time:
 *
 *     taken = nothing
 *     until taken has the best key:
 *         add the lowest candidate k after the last one taken such that taken + k can still be completed to the
 *         best key with candidates after k (checked by `completes`)
 *
 * Example: candidates 0..3, best key (10, 2). If no allocation with that key contains 0 but one contains 1, the
 * first step takes 1; if one completing {1} contains 3 but none contains 2, the next step takes 3; {1, 3} has the
 * best key, so that is the answer: exactly what brute force would have kept.
 *
 * Each `completes` check is a fast search with a goal, so this needs no search in the slow, fixed order at all. */
static bool first_with_key(const candidate *c, size_t n, size_t nbidders, int64_t welfare, int ntasks,
                           size_t **best, size_t *nbest)
{
	size_t depth = (n < COMB_MAX_TASKS ? n : COMB_MAX_TASKS) + 1;
	size_t *set = malloc(sizeof(size_t) * depth);
	unsigned char *used = calloc(nbidders ? nbidders : 1, 1);
	bool ok = set != NULL && used != NULL;
	size_t count = 0, next = 0;
	uint64_t tasks = 0;            /* tasks of the candidates taken */
	int64_t have_welfare = 0;      /* and their key */
	int have_tasks = 0;
	while (ok && (have_welfare != welfare || have_tasks != ntasks)) {
		/* Find the lowest candidate k that can be taken next */
		size_t k = next;
		for (; k < n && ok; k++) {
			const candidate *ck = &c[k];
			if (used[ck->bidder] || (ck->tasks & tasks)) continue;
			used[ck->bidder] = 1;
			bool fits = completes(c, n, nbidders, k + 1, tasks | ck->tasks, used, welfare - have_welfare - ck->welfare,
			                      ntasks - have_tasks - ck->ntasks, &ok);
			if (fits) break;
			used[ck->bidder] = 0;
		}
		if (!ok) break;
		if (k == n) {  /* cannot happen when the key is right */
			fprintf(stderr, "vcg_comb_clear: no set reaches the best key\n");
			ok = false;
			break;
		}
		/* Take it */
		set[count++] = k;
		tasks |= c[k].tasks;
		have_welfare += c[k].welfare;
		have_tasks += c[k].ntasks;
		next = k + 1;
	}
	free(used);
	if (!ok) {
		free(set);
		return false;
	}
	*best = set;
	*nbest = count;
	return true;
}

/* The winning allocation (indices into c, increasing) and its welfare W*, by the given solver. All solvers give the
 * same answer. */
static bool best_allocation(const candidate *c, size_t n, size_t nbidders, comb_solver solver,
                            size_t **best, size_t *nbest, int64_t *welfare)
{
	if (solver == COMB_FAST_PIVOTS || solver == COMB_PARALLEL_PIVOTS) {
		/* Searching in a good order finds the best key quickly; then rebuild from it the allocation that brute
		 * force, searching in the fixed order, would have kept */
		int ntasks;
		return best_key(c, n, nbidders, false, 0, welfare, &ntasks)
		       && first_with_key(c, n, nbidders, *welfare, ntasks, best, nbest);
	}

	/* Brute force or branch and bound: one search in the fixed order */
	search s;
	bool ok = search_init(&s, c, n, nbidders) && search_run(&s, solver != COMB_BRUTE_FORCE);
	if (ok) {
		*welfare = s.best_welfare;
		*nbest = s.nbest;
		*best = s.best;
		s.best = NULL;  /* handed to the caller, so search_free must not free it */
	}
	search_free(&s);
	return ok;
}

/* ==== 6. Pivots: W*_without for each winner ======================================================================= */

/* W*_without: the most welfare possible with every bid of `bidder` left out.
 *
 * `seed` is the best allocation's welfare less the welfare of this bidder's winning bid. Taking that bid out of the
 * best allocation leaves an allocation without the bidder, so at least `seed` is reachable, and the fast solvers
 * search only for something better. */
static bool welfare_without(const candidate *c, size_t n, size_t nbidders, comb_solver solver, int bidder,
                            int64_t seed, int64_t *welfare)
{
	size_t m;
	candidate *rest = without_bidder(c, n, bidder, &m);
	if (rest == NULL) return false;
	bool ok;
	if (solver == COMB_BRUTE_FORCE || solver == COMB_BRANCH_AND_BOUND) {
		/* The same search as for W*, as clearing.py does */
		size_t *best = NULL, nbest;
		ok = best_allocation(rest, m, nbidders, solver, &best, &nbest, welfare);
		free(best);
	} else {
		/* Only the number goes into the payment, not which allocation reaches it, and ties do not change it: a
		 * welfare-only search in the fastest order will do */
		ok = best_key(rest, m, nbidders, true, seed, welfare, NULL);
	}
	free(rest);
	return ok;
}

/* The work of one thread for COMB_PARALLEL_PIVOTS: the winners first, first + step, first + 2 * step, ... */
typedef struct {
	const candidate *c;
	size_t n, nbidders;
	const size_t *winners;
	size_t nwinners;
	int64_t welfare;   /* W* */
	int64_t *without;  /* results: W*_without per winner */
	size_t first, step;
	bool ok;
} pivot_job;

/* The pivot searches are independent of each other. The threads only read the shared candidates, and each writes
 * only its own entries of `without`, so they need no locks. */
static void *pivot_worker(void *arg)
{
	pivot_job *job = arg;
	job->ok = true;
	for (size_t w = job->first; w < job->nwinners && job->ok; w += job->step) {
		const candidate *win = &job->c[job->winners[w]];
		job->ok = welfare_without(job->c, job->n, job->nbidders, COMB_FAST_PIVOTS, win->bidder,
		                          job->welfare - win->welfare, &job->without[w]);
	}
	return NULL;
}

/* W*_without for each winner, into without[0..nwinners-1]: one after another, or for COMB_PARALLEL_PIVOTS spread
 * over up to PROCS threads. */
static bool pivots(const candidate *c, size_t n, size_t nbidders, comb_solver solver, const size_t *winners,
                   size_t nwinners, int64_t welfare, int64_t *without)
{
	size_t threads = solver == COMB_PARALLEL_PIVOTS ? (nwinners < PROCS ? nwinners : PROCS) : 1;
	if (threads <= 1) {
		for (size_t w = 0; w < nwinners; w++) {
			const candidate *win = &c[winners[w]];
			if (!welfare_without(c, n, nbidders, solver, win->bidder, welfare - win->welfare, &without[w]))
				return false;
		}
		return true;
	}

	pthread_t tid[PROCS];
	pivot_job jobs[PROCS];
	bool started[PROCS];
	for (size_t p = 0; p < threads; p++) {
		pivot_job job = {c, n, nbidders, winners, nwinners, welfare, without, p, threads, false};
		jobs[p] = job;
		started[p] = pthread_create(&tid[p], NULL, pivot_worker, &jobs[p]) == 0;
		if (!started[p]) pivot_worker(&jobs[p]);  /* no thread to spare: do it here */
	}
	bool ok = true;
	for (size_t p = 0; p < threads; p++) {
		if (started[p]) pthread_join(tid[p], NULL);
		ok = ok && jobs[p].ok;
	}
	return ok;
}

/* ==== 7. Clearing ================================================================================================= */

static comb_outcome failed(const char *why)
{
	comb_outcome o;
	memset(&o, 0, sizeof(o));
	fprintf(stderr, "vcg_comb_clear: %s\n", why);
	return o;
}

/* Clear the auction (see the header): pick the winning allocation, work out each winner's VCG payment, and turn
 * that into one award per task won. */
comb_outcome vcg_comb_clear(const int64_t *values, size_t task_count,
                            const comb_bid *bids, size_t bid_count, comb_solver solver)
{
	if (task_count > COMB_MAX_TASKS) return failed("too many tasks; at most COMB_MAX_TASKS");
	if ((task_count > 0 && values == NULL) || (bid_count > 0 && bids == NULL)) return failed("missing input");
	if ((unsigned) solver >= COMB_SOLVER_COUNT) return failed("unknown solver");

	/* 1. The bids that can win */
	size_t n, nbidders;
	candidate *c = build_candidates(values, task_count, bids, bid_count, &n, &nbidders);
	if (c == NULL) return failed("out of memory");

	size_t *winners = NULL, nwinners = 0;
	int64_t welfare = 0;
	int64_t *without = NULL;
	comb_outcome o;
	memset(&o, 0, sizeof(o));

	/* 2. The winning allocation and its welfare W* */
	if (!best_allocation(c, n, nbidders, solver, &winners, &nwinners, &welfare)) goto fail;

	/* 3. For each winner, W*_without: the best welfare had its bidder not taken part */
	without = malloc(sizeof(int64_t) * (nwinners ? nwinners : 1));
	if (without == NULL) goto fail;
	if (!pivots(c, n, nbidders, solver, winners, nwinners, welfare, without)) goto fail;

	/* 4. The awards: one per task of each winning bid. Count them, and note which tasks are won. */
	size_t award_count = 0;
	uint64_t won = 0;
	for (size_t w = 0; w < nwinners; w++) {
		award_count += (size_t) c[winners[w]].ntasks;
		won |= c[winners[w]].tasks;
	}
	o.awards = malloc(sizeof(comb_award) * (award_count ? award_count : 1));
	o.unallocated = malloc(sizeof(int) * (task_count ? task_count : 1));
	if (o.awards == NULL || o.unallocated == NULL) goto fail;

	for (size_t w = 0; w < nwinners; w++) {
		const candidate *win = &c[winners[w]];
		const comb_bid *bid = &bids[win->bid];
		/* The VCG payment for the whole bid: its price plus what it adds to the welfare. Awards are per task, so
		 * split it over the bid's tasks in proportion to their values; no task then pays over its budget. A bid
		 * names at most COMB_MAX_TASKS distinct tasks. */
		int64_t weights[COMB_MAX_TASKS], shares[COMB_MAX_TASKS];
		for (size_t k = 0; k < bid->task_count; k++) weights[k] = values[bid->tasks[k]];
		comb_split(bid->price + welfare - without[w], weights, bid->task_count, shares);
		for (size_t k = 0; k < bid->task_count; k++) {
			comb_award *a = &o.awards[o.award_count++];
			a->task = bid->tasks[k];
			a->bidder = bid->bidder;
			a->bid = win->bid;
			a->payment = shares[k];
		}
	}

	/* 5. The tasks nobody won */
	for (size_t t = 0; t < task_count; t++)
		if (!((won >> t) & 1)) o.unallocated[o.unallocated_count++] = (int) t;
	o.welfare = welfare;
	o.ok = true;

	free(without);
	free(winners);
	free(c);
	return o;

fail:
	free(without);
	free(winners);
	free(c);
	comb_outcome_free(&o);
	return failed("out of memory or solver not available");
}

void comb_outcome_free(comb_outcome *outcome)
{
	if (outcome == NULL) return;
	free(outcome->awards);
	free(outcome->unallocated);
	memset(outcome, 0, sizeof(*outcome));
}
