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
			if (!exclude_seller) total += q*seller[i]->value;
		}
	}
	return total;
}
