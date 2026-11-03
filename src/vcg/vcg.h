#define MAX_AGENTS 32
#include <stddef.h>

typedef struct {
	int rows;
	int cols;
	int quantity[MAX_AGENTS][MAX_AGENTS];
} Allocation;

typedef struct {
	size_t count;
	int demand[MAX_AGENTS]; //Max amount of flops they can take
	int used_demand[MAX_AGENTS]; //Used during calculation
	double* value[MAX_AGENTS];
} Buyers;

typedef struct {
	int id;
	int flops;
} Task;

typedef struct {
	size_t count;
	Task* tasks[MAX_AGENTS];
	int capacity[MAX_AGENTS]; //Amount of tasks it has
	double cost[MAX_AGENTS]; //Always zero
} Sellers;

typedef struct {
	double *buyer_payments;
	double *seller_payments;
	Allocation allocation;
} auction_results;


auction_results vcg_auction(Buyers buyers, Sellers sellers);
auction_results vcg_auction_multithreaded(Buyers buyers, Sellers sellers);
auction_results vcg_auction_approximation(Buyers buyers, Sellers sellers, float alpha);
void print_allocation(Allocation x);


/* below are functions only exposed for testing */

typedef enum {
	AGENT_BUYER,
	AGENT_SELLER
} Agent_type;

typedef struct {
	Agent_type type;
	size_t index;
} Agent;

double welfare(Buyers* buyers, Sellers* sellers, Allocation *x, Agent *excluded);
