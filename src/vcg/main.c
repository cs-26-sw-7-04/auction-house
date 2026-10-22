#include <stdio.h>

#define MAX_AGENTS 8

typedef struct {
	int rows;
	int cols;
	int quantity[MAX_AGENTS][MAX_AGENTS];
} Allocation;

typedef struct {
	int count;
	int demand[MAX_AGENTS];
	double value[MAX_AGENTS];
} Buyers;

typedef struct {
	int count;
	int capacity[MAX_AGENTS];
	double cost[MAX_AGENTS];
} Sellers;

typedef enum {
	AGENT_BUYER,
	AGENT_SELLER
} Agent_type;

typedef struct {
	Agent_type type;
	int index;
} Agent;

typedef struct {
	Allocation allocation;
	double welfare;
	bool found;
} Optimum;


double welfare(Buyers *buyers, Sellers* sellers, Allocation *x, Agent *excluded)
{
	double total = 0.0;

	for (size_t i = 0; i < sellers->count; i++){
		for (size_t j = 0; j < buyers->count; j++){
			int q = x->quantity[i][j];

			bool exclude_buyer  = excluded != NULL && excluded->type == AGENT_BUYER  && excluded->index == j;
			bool exclude_seller = excluded != NULL && excluded->type == AGENT_SELLER && excluded->index == i;

			if (!exclude_buyer) total  += q*buyers[j]->value;
			if (!exclude_seller) total += q*sellers[i]->value;
		}
	}
	return total;
}

typedef struct {
	Buyers* buyers;
	Sellers *sellers;
	Agent *excluded;

	Alloccation x;
	int buyers_used[MAX_AGENETS];
	int sellers_used[MAX_AGENETS];

	Optimum best;
} Search;

void enumerate(Search *search, size_t cell)
{
	int cols = search->buyers->count;
	int rows = search->sellers->count;
	int cell_count = cols * rows;

	if (cell == cell_count){
		double w = welfare(search->buyers, search->sellers, search->x, search->excluded);
		if (!search->best.found == false || w > search->best.welfare){
			search->best.fount = true;
			search->best.welfare = w;
			search->best.allocation = search->x;
		}
		return;
	}
       
	int i = cell / cols;
	int j = cell % cols;
	bool exclude_buyer  = search->excluded != NULL && search->excluded->type == AGENT_BUYER  && search->excluded->index == j;
	bool exclude_seller = search->excluded != NULL && search->excluded->type == AGENT_SELLER && search->excluded->index == i;

	int remaining_buyer = search->buyers[i] - search->buyers_used[i];
	int remaining_seller = search->sellers[i] - search->sellers_used[i];

	int limit = remaining_buyer > remaining_seller ? remaining_buyer : remaining_seller;
	
	if (exclude_buyer || exclude_seller) limit = 0;

	for (int k = 0; k <= limit; k++){
		search->x.quantity[i][j] = k;
		search->sellers_used[i] += k;
		search->buyers_used[j] += k;

		enumerate(search, cell + 1);

		search->sellers_used[i] -= k;
		search->buyers_used[j] -= k;
	}

	search->x.quantity[i][j] = 0;
}
