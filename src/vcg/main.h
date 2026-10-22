#define MAX_AGENTS 8
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
	int buyer_index;
	int seller_index;
	double price;
} auction_results;


Allocation vcg_auction(Buyers buyers, Sellers sellers);

void print_allocation(Allocation x);
