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
	Agent buyer;
	Agent seller;
} Optimum;


double welfare(Buyers* buyers, Sellers* sellers, Allocation *x, Agent *excluded)
{
	double total = 0.0;

	for (size_t i = 0; i < sellers->count; i++){
		for (size_t j = 0; j < buyers->count; j++){
			int q = x->quantity[i][j];

			bool exclude_buyer  = excluded != NULL && excluded->type == AGENT_BUYER  && excluded->index == j;

			
			if (!exclude_buyer && buyers->value[j] != NULL) total  += buyers->value[j][q-1];

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
				if (search->buyers->tasks_count[j] + 1 >= search->buyers->tasks_cap[j]) {
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
	search.sellers = sellers;
	search.excluded = excluded;
	search.x.rows = sellers->count;
	search.x.cols = buyers->count;

	enumerate(&search, 0);
	return search.best;
}

double pivot_transfer(Buyers* buyers, Sellers *sellers, Allocation *chosen, Agent removed)
{
	double wo = welfare(buyers, sellers, chosen, &removed);
	Optimum agentless = optimize(buyers, sellers, &removed);

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

	for (size_t i = 0; i < buyers.count; i++){
		buyers.tasks_cap[i] = 4;
		buyers.tasks_count[i] = 0;
		buyers.allocated_tasks[i] = malloc(sizeof(int) * buyers.tasks_cap[i]);
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
	ar.allocation = result.allocation;
	memcpy(ar.tasks_count, buyers.tasks_count, sizeof(ar.tasks_count));
	memcpy( ar.tasks_cap, buyers.tasks_cap, sizeof(ar.tasks_cap));
	memcpy( ar.allocated_tasks, buyers.allocated_tasks,sizeof(ar.allocated_tasks));
	//For debug:
	//printf("Welfare: %lf\n", welfare(&buyers, &sellers, &ar.allocation, NULL));

	return ar;
}


void print_allocation(Allocation x)
{
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
		memcpy(&searches[p], search, sizeof(Search));
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
			if (k > 0)
				search->sellers->tasks[i][available_task_index].assigned = true;
			enumerate(search, cell + 1);
			search->sellers->tasks[i][available_task_index].assigned = false;
		}

		search->sellers_used[i] -= k;
		search->buyers_used[j] -= search->sellers->tasks[i][available_task_index].flops;
	}
	search->x.quantity[i][j] = 0;
	return (void *) 1;
}
Optimum optimize_multithreaded (Buyers* buyers, Sellers *sellers, Agent *excluded)
{
	Search search = {0};
	search.buyers = buyers;
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

	return ar;
}

auction_results vcg_auction_approximation(Buyers buyers, Sellers sellers, float alpha)
{
	(void) buyers;
	(void) sellers;
	(void) alpha;
	auction_results ar = {0};
	return ar;
}
