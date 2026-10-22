#include <stdio.h>

#define MAX_AGENTS 8

typedef struct {
	int rows;
	int cols;
	double value[MAX_AGENTS][MAX_AGENTS];
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


