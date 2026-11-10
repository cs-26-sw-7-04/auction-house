#include <stdio.h>
#include <stdbool.h>
#include <pthread.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#include "vcg.h"

#ifndef PROCS
#define PROCS 1
#endif

typedef struct {
	Allocation allocation;
	double welfare;
	bool found;
	size_t tasks_count[MAX_AGENTS];
	size_t tasks_cap[MAX_AGENTS];
	int* allocated_tasks[MAX_AGENTS];
} Optimum;


double welfare(Buyers* buyers, Sellers* sellers, Allocation *x, Agent *excluded)
{
	double total = 0.0;
	for (size_t i = 0; i < sellers->count; i++){
		for (size_t j = 0; j < buyers->count; j++){
			int q = x->quantity[i][j];

			bool exclude_buyer  = excluded != NULL && excluded->type == AGENT_BUYER  && excluded->index == j;			
			if (!exclude_buyer && buyers->value[j] != NULL) total  += q > 0 ? buyers->value[j][q-1] : 0;

		}
	}
	for (size_t i = 0; i < sellers->count; i++){
		for (size_t j = 0; j < buyers->count; j++){
			int q = x->quantity[i][j];
			bool exclude_seller = excluded != NULL && excluded->type == AGENT_SELLER && excluded->index == i;
		
			if (!exclude_seller) total -= q*sellers->cost[i];
		}
	}
	return total;
}

typedef struct {
	Buyers* buyers;
	Sellers *sellers;
	Agent *excluded;

	Allocation x;
	int buyers_used[MAX_AGENTS];
	int sellers_used[MAX_AGENTS];

	Optimum best;
} Search;

void clone_buyer_attr(Optimum *best, Buyers *buyers)
{
	for (size_t i = 0; i < MAX_AGENTS; i++){
		size_t tmp = best->tasks_cap[i];
		best->tasks_count[i] = buyers->tasks_count[i];
		best->tasks_cap[i] = buyers->tasks_cap[i];
		for (size_t j = 0; j < best->tasks_cap[i]; j++){
			if (best->allocated_tasks[i] == NULL){
				best->allocated_tasks[i] = malloc(sizeof(int*) * best->tasks_cap[i]);
			} else if (best->tasks_cap[i] > tmp){
				best->allocated_tasks[i] = realloc(best->allocated_tasks[i], sizeof(int*) * best->tasks_cap[i]);
			}
			if (buyers->allocated_tasks[i] != NULL)
				best->allocated_tasks[i][j] = buyers->allocated_tasks[i][j];
		}
	}
}

void enumerate(Search *search, size_t cell)
{
	
	size_t cols = search->buyers->count;
	size_t rows = search->sellers->count;

	if (cols == 0) return;

	size_t cell_count = cols * rows;

	if (cell == cell_count){
		double w = welfare(search->buyers, search->sellers, &search->x, search->excluded);
		if (!search->best.found || w > search->best.welfare){
			search->best.found = true;
			search->best.welfare = w;
			search->best.allocation = search->x;
			clone_buyer_attr(&search->best, search->buyers);
		}
		return;
	}
	size_t i = cell / cols;
	size_t j = cell % cols;

       

	bool exclude_buyer  = search->excluded != NULL && 
	                      search->excluded->type == AGENT_BUYER  && 
						  search->excluded->index == j;
	bool exclude_seller = search->excluded != NULL && 
	                      search->excluded->type == AGENT_SELLER && search->excluded->index == i;

	int remaining_buyer = search->buyers->demand[j] - search->buyers_used[j];
	int remaining_seller = search->sellers->capacity[i] - search->sellers_used[i];


	int limit = remaining_buyer < remaining_seller ? remaining_buyer : remaining_seller;
	
	if (exclude_buyer || exclude_seller) limit = 0;

	for (int k = 0; k <= limit; k++){


		bool task_available = true;
		int available_task_index = -1;

		for (int l = 0; l < search->sellers->capacity[i]; l++){
			if (search->sellers->tasks[i][l].assigned
			    || search->sellers->tasks[i][l].flops
			    > search->buyers->demand[j] - search->buyers->used_demand[j]){
				task_available = false;
			}else
			{
				task_available = true;
				available_task_index = l;
				break;
			}
		}
		if (!task_available){
			search->x.quantity[i][j] = k;
			enumerate(search, cell + 1);
			break;
		}
		search->x.quantity[i][j] = k;
		search->sellers_used[i] += k;
		search->buyers_used[j] += search->sellers->tasks[i][available_task_index].flops;
		if (search->buyers_used[j] <= search->buyers->demand[j]
		    && search->sellers_used[i] <= search->sellers->capacity[i]){
			if (k > 0){
				search->sellers->tasks[i][available_task_index].assigned = true;
				if (search->buyers->allocated_tasks[j] == NULL || search->buyers->tasks_count[j] + 1 >= search->buyers->tasks_cap[j]) {
					search->buyers->tasks_cap[j] += 4;
					search->buyers->allocated_tasks[j] = realloc(search->buyers->allocated_tasks[j], sizeof(int) * search->buyers->tasks_cap[j]);
					search->buyers->allocated_tasks[j][search->buyers->tasks_count[j]] = search->sellers->tasks[i][available_task_index].id;
					search->buyers->tasks_count[j]++;
				}else{
					search->buyers->allocated_tasks[j][search->buyers->tasks_count[j]] = search->sellers->tasks[i][available_task_index].id;
					search->buyers->tasks_count[j]++;
				}
			}
			enumerate(search, cell + 1);
			search->sellers->tasks[i][available_task_index].assigned = false;

			if (k > 0){
				search->buyers->allocated_tasks[j][search->buyers->tasks_count[j]] = 0;
				search->buyers->tasks_count[j]--;
			}
		}

		search->sellers_used[i] -= k;
		search->buyers_used[j] -= search->sellers->tasks[i][available_task_index].flops;
	}

	search->x.quantity[i][j] = 0;
}

Optimum optimize (Buyers* buyers, Sellers *sellers, Agent *excluded)
{
	Search search = {0};
	search.buyers = buyers;
	for (size_t i = 0; i < MAX_AGENTS; i++){
		search.buyers->allocated_tasks[i] = NULL;
	}
	search.sellers = sellers;
	search.excluded = excluded;
	search.x.rows = sellers->count;
	search.x.cols = buyers->count;

	enumerate(&search, 0);
	for (size_t i = 0; i < MAX_AGENTS; i++){
		if(search.buyers->allocated_tasks[i] != NULL && search.buyers->allocated_tasks[i] != buyers->allocated_tasks[i]){
			free(search.buyers->allocated_tasks[i]);
		}
	}
	return search.best;
}

double pivot_transfer(Buyers* buyers, Sellers *sellers, Allocation *chosen, Agent removed)
{
	double wo = welfare(buyers, sellers, chosen, &removed);
	Optimum agentless = optimize(buyers, sellers, &removed);
	for (size_t i = 0; i < MAX_AGENTS; i++){
		if(agentless.allocated_tasks[i] != NULL && agentless.allocated_tasks[i] != buyers->allocated_tasks[i]){
			free(agentless.allocated_tasks[i]);
		}
	}
	if (!agentless.found) return 0.0;

	return  agentless.welfare - wo;
}

auction_results vcg_auction(Buyers buyers, Sellers sellers)
{	
	//For debug:
	//print_sellers(sellers);
	//print_buyers(buyers);
	
	auction_results ar = {0};
	if (buyers.count > MAX_AGENTS || sellers.count > MAX_AGENTS) {
		fprintf(stderr, "Too many agents; increase MAX_AGENTS.\n");
		return ar;
	}

	Optimum result = optimize(&buyers, &sellers, NULL);
	if (!result.found) {
		fprintf(stderr, "No feasible allocation found.\n");
		return ar;
	}

	double *prices = malloc(sizeof(double) * buyers.count);
	for (size_t j = 0; j < buyers.count; ++j) {
		prices[j] = 0;
		for (size_t k = 0; k < sellers.count; k++){
			if (result.allocation.quantity[k][j]){
				Agent agent = { .type = AGENT_BUYER, .index = j };
				prices[j] = pivot_transfer(&buyers, &sellers, &result.allocation, agent);
			}
		}
	}

	double *costs = malloc(sizeof(double) * sellers.count);
	for (size_t i = 0; i < sellers.count; ++i) {
		costs[i] = 0;
		for (size_t j = 0; j < buyers.count; ++j){
			if (result.allocation.quantity[i][j]){
				Agent agent = { .type = AGENT_SELLER, .index = i };
				costs[i] = pivot_transfer(&buyers, &sellers, &result.allocation, agent);

			}
		}
	}
	
	ar.buyer_payments  = prices;
	ar.seller_payments = costs;
	memcpy(&ar.allocation, &result.allocation, sizeof(ar.allocation));
	memcpy(ar.tasks_count, result.tasks_count, sizeof(ar.tasks_count));
	memcpy( ar.tasks_cap, result.tasks_cap, sizeof(ar.tasks_cap));
	memcpy( ar.allocated_tasks, result.allocated_tasks,sizeof(ar.allocated_tasks));


	//For debug:
	//printf("Welfare: %lf\n", welfare(&buyers, &sellers, &ar.allocation, NULL));


	return ar;
}


void print_allocation(Allocation x)
{
	if (x.cols < 1 || x.rows < 1) return;
	printf("+");
	for (int i = 0; i < x.cols; i++){
		printf("---");
	}
	printf("+\n");
	for (int i = 0; i < x.rows; i++){
		printf("|");
		for (int j = 0; j < x.cols; j++){
			printf(" %d ", x.quantity[i][j]);
		}
		printf("|\n");
	}
	printf("+");
	for (int i = 0; i < x.cols; i++){
		printf("---");
	}
	printf("+\n");
}

typedef struct {
	Search *search;
	int i;
	int j;
	int start;
	int end;
	size_t cell;
}run_branch;
void* multithreaded_branch(void* arg);

void enumerate_multithreaded(Search *search, size_t cell)
{
	size_t cols = search->buyers->count;
	size_t i = cell / cols;
	size_t j = cell % cols;

	int remaining_buyer = search->buyers->demand[j] - search->buyers_used[j];
	int remaining_seller = search->sellers->capacity[i] - search->sellers_used[i];
	
	int limit = remaining_buyer < remaining_seller ? remaining_buyer : remaining_seller;
	if (remaining_buyer > PROCS || remaining_seller > PROCS){
		enumerate(search, cell);
		return;
	}

	bool exclude_buyer  = search->excluded != NULL && search->excluded->type == AGENT_BUYER  && search->excluded->index == j;
	bool exclude_seller = search->excluded != NULL && search->excluded->type == AGENT_SELLER && search->excluded->index == i;

	
	if (exclude_buyer || exclude_seller) limit = 0;
	pthread_t threads[PROCS];
	run_branch r[PROCS];
	Search *searches = malloc(sizeof(Search)*PROCS);
	for (int p = 0; p < PROCS; p++){
		int count = limit + 1;
		int start = p * count / PROCS;
		int end = (p + 1) * count / PROCS;
		r[p].search = &searches[p];
		r[p].i =i;
		r[p].j =j;
		r[p].start = start;
		r[p].end = end;
		r[p].cell =cell;

	}
		
	for (int p = 0; p < PROCS; p++)
	{
		memcpy(&searches[p], search, sizeof(Search)); /* TODO: this is currently broken and makes the multithreaded vcg have a chance of giving the incorrect answer or segfault */
		pthread_create(&threads[p], NULL, multithreaded_branch, (void*) &r[p]);

	}
	for (int p = 0; p < PROCS; p++)
	{
		pthread_join(threads[p], NULL);
	}
	double best_welfare = searches[0].best.welfare;
	int best_index      = 0;
	for (int p = 1; p < PROCS; p++)
	{
		if (searches[p].best.welfare > best_welfare){
			best_welfare = searches[p].best.welfare;
			best_index   = p;
		}
	}
	memcpy(search, &searches[best_index], sizeof(Search));
	free(searches);

}




void* multithreaded_branch(void* arg)
{
	if (arg == NULL) return NULL;
	run_branch *data = (run_branch*) arg;
	Search *search = data->search;
	int i = data->i;
	int j = data->j;
	size_t cell = data->cell;
	for (int k = data->start; k < data->end; k++){
		bool task_available = true;
		int available_task_index = -1;

		for (int l = 0; l < search->sellers->capacity[i]; l++){
			if (search->sellers->tasks[i][l].assigned
			    || search->sellers->tasks[i][l].flops
			    > search->buyers->demand[j] - search->buyers->used_demand[j]){
				task_available = false;
			}else
			{
				task_available = true;
				available_task_index = l;
				break;
			}
		}
		if (!task_available){
			search->x.quantity[i][j] = k;
			enumerate(search, cell + 1);
			break;
		}
		search->x.quantity[i][j] = k;
		search->sellers_used[i] += k;
		search->buyers_used[j] += search->sellers->tasks[i][available_task_index].flops;
		bool should_enumerate =
			search->buyers_used[j]<= search->buyers->demand[j]
			&& search->sellers_used[i] <= search->sellers->capacity[i];
		
		if (should_enumerate){
			if (k > 0){
				search->sellers->tasks[i][available_task_index].assigned = true;
				if (search->buyers->allocated_tasks[j] == NULL || search->buyers->tasks_count[j] + 1 >= search->buyers->tasks_cap[j]) {
					search->buyers->tasks_cap[j] += 4;
					search->buyers->allocated_tasks[j] = realloc(search->buyers->allocated_tasks[j], sizeof(int) * search->buyers->tasks_cap[j]);
					search->buyers->allocated_tasks[j][search->buyers->tasks_count[j]] = search->sellers->tasks[i][available_task_index].id;
					search->buyers->tasks_count[j]++;
				}else{
					search->buyers->allocated_tasks[j][search->buyers->tasks_count[j]] = search->sellers->tasks[i][available_task_index].id;
					search->buyers->tasks_count[j]++;
				}
			}
			enumerate(search, cell + 1);
			search->sellers->tasks[i][available_task_index].assigned = false;

			if (k > 0){
				search->buyers->allocated_tasks[j][search->buyers->tasks_count[j]] = 0;
				search->buyers->tasks_count[j]--;
			}
		}

		search->sellers_used[i] -= k;
		if (k > 0){
			search->buyers_used[j] -= search->sellers->tasks[i][available_task_index].flops;
			search->buyers->tasks_count[j]--;
		}
	}
	search->x.quantity[i][j] = 0;
	return (void *) 1;
}
Optimum optimize_multithreaded (Buyers* buyers, Sellers *sellers, Agent *excluded)
{
	Search search = {0};
	search.buyers = buyers;
	for (size_t i = 0; i < MAX_AGENTS; i++){
		search.buyers->allocated_tasks[i] = NULL;
	}
	search.sellers = sellers;
	search.excluded = excluded;
	search.x.rows = sellers->count;
	search.x.cols = buyers->count;

	enumerate_multithreaded(&search, 0);
	return search.best;
}

double pivot_transfer_multithreaded(Buyers* buyers, Sellers *sellers, Allocation *chosen, Agent removed)
{
	double wo = welfare(buyers, sellers, chosen, NULL);
	Optimum agentless = optimize_multithreaded(buyers, sellers, &removed);

	if (!agentless.found) return 0.0;

	return  agentless.welfare - wo;
}


auction_results vcg_auction_multithreaded(Buyers buyers, Sellers sellers)
{
	int procs = (int) PROCS;
	printf("PROCS: %d\n",procs);
	auction_results ar = {0};
	if (buyers.count > MAX_AGENTS || sellers.count > MAX_AGENTS) {
		fprintf(stderr, "Too many agents; increase MAX_AGENTS.\n");
		return ar;
	}

	for (size_t i = 0; i < buyers.count; i++){
		buyers.tasks_cap[i] = 4;
		buyers.tasks_count[i] = 0;
		buyers.allocated_tasks[i] = malloc(sizeof(int) * buyers.tasks_cap[i]);
	}

	Optimum result = optimize_multithreaded(&buyers, &sellers, NULL);
	if (!result.found) {
		fprintf(stderr, "No feasible allocation found.\n");
		return ar;
	}

	double *prices = malloc(sizeof(double) * buyers.count);
	for (size_t j = 0; j < buyers.count; ++j) {
		prices[j] = 0;
		for (size_t k = 0; k < sellers.count; k++){
			if (result.allocation.quantity[k][j]){
				Agent agent = { .type = AGENT_BUYER, .index = j };
				prices[j] = pivot_transfer_multithreaded(&buyers, &sellers, &result.allocation, agent);
			}
		}
	}

	double *costs = malloc(sizeof(double) * sellers.count);
	for (size_t i = 0; i < sellers.count; ++i) {
		for (size_t j = 0; j < buyers.count; ++j){
			if (result.allocation.quantity[i][j]){
				Agent agent = { .type = AGENT_SELLER, .index = i };
				costs[i] = pivot_transfer_multithreaded(&buyers, &sellers, &result.allocation, agent);

			}
		}
	}
	
	ar.buyer_payments = prices;
	ar.seller_payments = costs;
	ar.allocation = result.allocation;
	memcpy(ar.tasks_count, buyers.tasks_count, sizeof(ar.tasks_count));
	memcpy( ar.tasks_cap, buyers.tasks_cap, sizeof(ar.tasks_cap));
	memcpy( ar.allocated_tasks, buyers.allocated_tasks,sizeof(ar.allocated_tasks));
	return ar;
}



/* --------------------Approximation Implementation-------------------- */


typedef struct{
	bool join_successful;
	Allocation A;
	double welfare;
	struct combined_buyer{
		int demand;
		int used_demand;
		double* value;
		size_t tasks_count;
		size_t tasks_cap;
		int* allocated_tasks;
	} combined_buyer;
	Optimum O;
} join_result;


join_result* join(Buyers *B, size_t index, Sellers *S, join_result *jr, Agent *excluded)
{
	if (index > B->count) {
		fprintf(stderr, "./%s:%d:%d: index out of bounds in join() \n", __FILE__, __LINE__, 0);
		return jr;
	}
	if (jr == NULL){
		jr = calloc(1, sizeof(*jr));
		if (jr == NULL){
			fprintf(stderr, "./%s:%d:%d: failed to allocate join_result \n", __FILE__, __LINE__, 0);
			return jr;
		}
	}
	
	Buyers B2 = {0};
	Optimum O = {0};
	if (index == 0){
		B2 = *B;
		for (size_t i = 1; i < MAX_AGENTS; i++){
			B2.demand[i] = 0;
			
		}
		O = optimize(&B2, S, excluded);
	}else{


		B2 = *B;

		B2.value[0] = malloc(sizeof(B2.value[0]) * jr->combined_buyer.demand);
		B2.allocated_tasks[0] = malloc(sizeof(*B2.allocated_tasks[0]) * jr->combined_buyer.tasks_cap);

		B2.demand[0] = jr->combined_buyer.demand;
		B2.used_demand[0] = jr->combined_buyer.used_demand;

		for (int i = 0; i < jr->combined_buyer.demand; i++){
			B2.value[0][i] = jr->combined_buyer.value[i];
		}

		B2.tasks_count[0] = jr->combined_buyer.tasks_count;
		B2.tasks_cap[0] = jr->combined_buyer.tasks_cap;
		
		for (size_t i = 0; i < jr->combined_buyer.tasks_count; i++){
			B2.allocated_tasks[0][i] = jr->combined_buyer.allocated_tasks[i];
		}

		for (size_t i = 1; i < MAX_AGENTS; i++){
			if (i == index) continue;
			B2.demand[i] = 0;
		}
		O = optimize(&B2, S, excluded);
	
		free(B2.value[0]);	
		free(B2.allocated_tasks[0]);

	}

	
	int prev_demand = jr->combined_buyer.demand;

	if (jr->combined_buyer.tasks_cap < B->tasks_cap[index]){
		jr->combined_buyer.allocated_tasks = realloc(jr->combined_buyer.allocated_tasks, sizeof(jr->combined_buyer.allocated_tasks) * B->tasks_cap[index]);
	}

	jr->combined_buyer.demand = jr->combined_buyer.demand > B->demand[index] ? jr->combined_buyer.demand : B->demand[index];
	jr->combined_buyer.used_demand = jr->combined_buyer.used_demand > B->used_demand[index] ? jr->combined_buyer.used_demand : B->used_demand[index];
	if (B->demand[index] > 0){
		jr->combined_buyer.value = realloc(jr->combined_buyer.value, sizeof(jr->combined_buyer.value) * jr->combined_buyer.demand);
	}
	double prev = 0;
	for (int i = prev_demand; i < jr->combined_buyer.demand; i++){
		if (i - prev_demand < B->demand[index]){
			jr->combined_buyer.value[i] = B->value[index][i - prev_demand] + prev;
		}
		prev = jr->combined_buyer.value[i];
	}

	int prev_task_count = jr->combined_buyer.tasks_count;
	jr->combined_buyer.tasks_count += B->tasks_count[index];
	jr->combined_buyer.tasks_cap += B->tasks_cap[index];

	for (size_t i = prev_task_count; i < jr->combined_buyer.tasks_count; i++){
		jr->combined_buyer.allocated_tasks[i] = B->allocated_tasks[index][i - prev_task_count];
	}
	
	for (size_t i = 0; i < MAX_AGENTS; i++){
		B->tasks_count[i] = O.tasks_count[i];
		B->tasks_cap[i] = O.tasks_cap[i];
		B->allocated_tasks[i] = O.allocated_tasks[i];
	}
	if (O.welfare > jr->welfare){
		jr->A = O.allocation;
		jr->welfare = O.welfare;
		jr->O = O;
	}


	return jr;
}

double pivot_transfer_approximation(Buyers* buyers, Sellers *sellers, double welfare, Agent removed)
{
	join_result *jr = NULL;
	for (size_t i = 0; i < buyers->count; i++){
		jr = join(buyers, i, sellers, jr, &removed);
	}

	if (!jr->O.found) {
		free(jr->combined_buyer.value);
		free(jr);
		return 0.0;
	}
	double welfare2 = jr->O.welfare;
	for (size_t i = 0; i < MAX_AGENTS; i++){
		if(jr->O.allocated_tasks[i] != NULL && jr->O.allocated_tasks[i] != buyers->allocated_tasks[i]){
			free(jr->O.allocated_tasks[i]);
		}
	}
	free(jr->combined_buyer.allocated_tasks);
	free(jr->combined_buyer.value);
	free(jr);
	return   welfare2 - welfare;
}

auction_results vcg_auction_approximation(Buyers buyers, Sellers sellers)
{
	join_result *jr = NULL;
	for (size_t i = 0; i < buyers.count; i++){
		jr = join(&buyers, i, &sellers, jr, NULL);
	}

	auction_results ar = {0};
	double *prices = malloc(sizeof(double) * buyers.count);
	for (size_t j = 0; j < buyers.count; ++j) {
		prices[j] = 0;
		for (size_t k = 0; k < sellers.count; k++){
			if (jr->O.allocation.quantity[k][j]){
				Agent agent = { .type = AGENT_BUYER, .index = j };
				prices[j] = pivot_transfer_approximation(&buyers, &sellers, jr->welfare, agent);
			}
		}
	}

	double *costs = malloc(sizeof(double) * sellers.count);
	for (size_t i = 0; i < sellers.count; ++i) {
		costs[i] = 0;
		for (size_t j = 0; j < buyers.count; ++j){
			if (jr->O.allocation.quantity[i][j]){
				Agent agent = { .type = AGENT_SELLER, .index = i };
				costs[i] = pivot_transfer_approximation(&buyers, &sellers, jr->welfare, agent);

			}
		}
	}
	
	ar.buyer_payments  = prices;
	ar.seller_payments = costs;
	memcpy(&ar.allocation, &jr->A, sizeof(jr->A));
	memcpy(ar.tasks_count, jr->O.tasks_count, sizeof(ar.tasks_count));
	memcpy(ar.tasks_cap, jr->O.tasks_cap, sizeof(ar.tasks_cap));
	memcpy(ar.allocated_tasks, jr->O.allocated_tasks,sizeof(ar.allocated_tasks));

	
	free(jr->combined_buyer.value);
	free(jr);
	
	return ar;
}
