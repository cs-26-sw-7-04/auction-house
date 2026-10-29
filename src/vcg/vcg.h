#define MAX_AGENTS 32
#include <stddef.h>

typedef struct {
	int rows;
	int cols;
	int quantity[MAX_AGENTS][MAX_AGENTS];
} Allocation;

typedef struct {
	size_t count;
	int demand[MAX_AGENTS];
	double value[MAX_AGENTS];
} Buyers;

typedef struct {
	size_t count;
	int capacity[MAX_AGENTS];
	double cost[MAX_AGENTS];
} Sellers;

typedef struct {
	double *buyer_payments;
	Allocation allocation;
} auction_results;


auction_results vcg_auction(Buyers buyers, Sellers sellers);
auction_results vcg_auction_multithreaded(Buyers buyers, Sellers sellers);
auction_results vcg_auction_approximation(Buyers buyers, Sellers sellers, float alpha);
void print_allocation(Allocation x);
