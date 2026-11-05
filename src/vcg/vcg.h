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
	bool assigned;
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


Sellers assign_tasks(Sellers s, int index, int* id, int* flops, int count){
	s.tasks[index]		= malloc(sizeof(Task) * count);
	for (int i = 0; i < count; i++){
		s.tasks[index][i].id	= id[i];
		s.tasks[index][i].flops	= flops[i];
	}
	return s;
}

void print_sellers(Sellers ss){
	printf("Sellers, count %zu:\n", ss.count);
	for(size_t i = 0; i < ss.count; i++){
		printf("\t%02zu: capacity %d; cost %lf\n", i, ss.capacity[i], ss.cost[i]);
		for(int j = 0; j < ss.capacity[i]; j++){
			printf("\t\tTask %d: id %d; flops %d, assigned %s\n", j, ss.tasks[i][j].id, ss.tasks[i][j].flops, ss.tasks[i][j].assigned?"true":"false");
		}
	}

}
void print_buyers(Buyers bs){
	printf("Buyers, count %zu:\n", bs.count);
	for(size_t i = 0; i < bs.count; i++){
		printf("\t%02zu: demand %d; used demand %d\n", i, bs.demand[i], bs.used_demand[i]);
		for(int j = 0; j < bs.demand[i]; j++)
			printf("\t\tValue %02d: %lf\n", j, bs.value[i][j]);
	}
}


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
