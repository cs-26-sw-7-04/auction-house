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
			bool exclude_seller = excluded != NULL && excluded->type == AGENT_SELLER && excluded->index == i;

			if (!exclude_buyer) total  += q*buyers->value[j];
			if (!exclude_seller) total += q*sellers->cost[i];
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
	int cols = search->buyers->count;
	int rows = search->sellers->count;
	int cell_count = cols * rows;

	int i = cell / cols;
	int j = cell % cols;
	if (cell == cell_count){
		double w = welfare(search->buyers, search->sellers, &search->x, search->excluded);
		if (!search->best.found == false || w > search->best.welfare){
			search->best.found = true;
			search->best.welfare = w;
			search->best.allocation = search->x;
		        Agent buyer = {.index = j, .type = AGENT_BUYER};
			Agent seller = {.index = i, .type = AGENT_SELLER};
			search->best.buyer = buyer;
			search->best.seller = seller;
		}
		return;
	}
       

	bool exclude_buyer  = search->excluded != NULL && search->excluded->type == AGENT_BUYER  && search->excluded->index == j;
	bool exclude_seller = search->excluded != NULL && search->excluded->type == AGENT_SELLER && search->excluded->index == i;

	int remaining_buyer = search->buyers->value[j] - search->buyers_used[j];
	int remaining_seller = search->sellers->cost[i] - search->sellers_used[i];

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

	return wo - agentless.welfare;
}

typedef struct {
	int buyer_index;
	int seller_index;
	double price;
} auction_results;

auction_results vcg_auction(Buyers buyers, Sellers sellers)
{
	if (buyers.count > MAX_AGENTS || sellers.count > MAX_AGENTS) {
		fprintf(stderr, "Too many agents; increase MAX_AGENTS.\n");
		return (auction_results) {0};
	}

	Optimum result = optimize(&buyers, &sellers, NULL);
	if (!result.found) {
		fprintf(stderr, "No feasible allocation found.\n");
		return (auction_results){0};
	}

	
	for (size_t j = 0; j < buyers.count; ++j) {
		Agent agent = { .type = AGENT_BUYER, .index = j };
		printf("Buyer %zu: %.2f\n",
		       j, pivot_transfer(&buyers, &sellers,
					 &result.allocation, agent));
	}

	for (size_t i = 0; i < sellers.count; ++i) {
		Agent agent = { .type = AGENT_SELLER, .index = i };
		printf("Seller %zu: %.2f\n",
		       i, pivot_transfer(&buyers, &sellers,
					 &result.allocation, agent));
	}

	return (auction_results) {.buyer_index = result.buyer.index,
		.seller_index = result.seller.index,
		.price = result.allocation.quantity[result.seller.index][result.buyer.index]*buyers.value[result.buyer.index]};
}
