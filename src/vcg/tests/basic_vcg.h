#define _POSIX_C_SOURCE 199309L
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include "test_utils.h"
#include "../build/include/vcg.h"



/*
  The optimal allocation for this case is:
  +---------+
  | 1  1  0 |
  +---------+

  This test case is based on this example
  https://en.wikipedia.org/wiki/Vickrey%E2%80%93Clarke%E2%80%93Groves_auction#Two_items,_three_bidders 
 */
TEST basic_vcg_test_1()
{
	bool result = true;
	
	Buyers B = {0};
	B.count     = 3;
	B.demand[0] = 1;
	B.demand[1] = 1;
	B.demand[2] = 2;
	B.value[0]  = 5;
	B.value[1]  = 2;
	B.value[2]  = 3;

	Sellers S = {0};
	S.count       = 1;
	S.capacity[0] = 2;
	S.cost[0]     = 1;

	auction_results ar = vcg_auction(B,S);
	if (ar.allocation.rows == 0 || ar.allocation.cols == 0)
		result = false;
	if (ar.allocation.rows != 1 || ar.allocation.cols != 3)
		result = false;
	return result;
}

TEST stress_test()
{
	bool result = true;
	

	Buyers B = {0};
	B.count = 9;
	B.demand[0] = 1;
	B.demand[1] = 1;
	B.demand[2] = 2;
	B.demand[3] = 1;
	B.demand[4] = 1;
	B.demand[5] = 1;
	B.demand[6] = 2;
	B.demand[7] = 1;
	B.demand[8] = 2;
	B.value[0]  = 5;
	B.value[1]  = 2;
	B.value[2]  = 3;
	B.value[3]  = 5;
	B.value[4]  = 5;
	B.value[5]  = 2;
	B.value[6]  = 3;
	B.value[7]  = 2;
	B.value[8]  = 3;

	Sellers S = {0};
	S.count       = 1;
	S.capacity[0] = 2;
	S.cost[0]     = 1;

	auction_results ar = vcg_auction(B,S);
	if (ar.allocation.rows == 0 || ar.allocation.cols == 0){
		printf("ar.rows: %d ar.cols: %d\n", ar.allocation.rows, ar.allocation.cols);
		result = false;
	}
	if (ar.allocation.rows != 1 || ar.allocation.cols != 9)
		result = false;

	return result;
}

TEST stress_test_multithreaded()
{
	bool result = true;
	

	Buyers B = {0};
	B.count = 9;
	B.demand[0] = 1;
	B.demand[1] = 1;
	B.demand[2] = 2;
	B.demand[3] = 1;
	B.demand[4] = 1;
	B.demand[5] = 1;
	B.demand[6] = 2;
	B.demand[7] = 1;
	B.demand[8] = 2;
	B.value[0]  = 5;
	B.value[1]  = 2;
	B.value[2]  = 3;
	B.value[3]  = 5;
	B.value[4]  = 5;
	B.value[5]  = 2;
	B.value[6]  = 3;
	B.value[7]  = 2;
	B.value[8]  = 3;

	Sellers S = {0};
	S.count       = 2;
	S.capacity[0] = 2;
	S.cost[0]     = 1;
	S.capacity[1] = 2;
	S.cost[1]     = 1;

	auction_results ar = vcg_auction_multithreaded(B,S);
	print_allocation(ar.allocation);
	if (ar.allocation.rows == 0 || ar.allocation.cols == 0){
		printf("ar.allocation.rows: %d ar.allocation.cols: %d\n", ar.allocation.rows, ar.allocation.cols);
		result = false;
	}
	if (ar.allocation.rows != 2 || ar.allocation.cols != 9)
		result = false;

	return result;
}


static double elapsed_seconds(struct timespec start, struct timespec end)
{
    return (double)(end.tv_sec - start.tv_sec) +
           (double)(end.tv_nsec - start.tv_nsec) / 1e9;
}

TEST time_test()
{
	bool result = true;
	Buyers B = {0};
	Sellers S = {0};
	auction_results ar1;
	auction_results ar2;
	auction_results ar3;
	char* filepath = "Time_test_output.csv";

	FILE * output_data = fopen(filepath, "w");
	if (output_data == NULL){
		fprintf(stderr, "failed to open or create file: %sn\n", filepath);
		return false;
	}

	fprintf(output_data, "Agents, time1, time2, delta1, time3, delta2\n");
	srand((unsigned)time(NULL));
	
	for (int i = 0; i < MAX_AGENTS; i++) {
		S.capacity[i] = 1 + rand() % 9;
		S.cost[i]     = 0; //1 + rand() % 9;
		B.demand[i]   = 1 + rand() % 9; 
		B.value[i]    = 1 + rand() % 9; 
	}

	for (int i = 1; i < 6; i ++){
		B.count = i;
		S.count = i;

		struct timespec start, end;

		clock_gettime(CLOCK_MONOTONIC, &start);
		ar1 = vcg_auction(B, S);
		clock_gettime(CLOCK_MONOTONIC, &end);
		double time1 = elapsed_seconds(start, end);
		print_allocation(ar1.allocation);
		printf("time taken: %lf seconds (agents %d)\n",time1, i);
		clock_gettime(CLOCK_MONOTONIC, &start);
		ar2 = vcg_auction_multithreaded(B, S);
		clock_gettime(CLOCK_MONOTONIC, &end);
		double time2 = elapsed_seconds(start, end);
		print_allocation(ar2.allocation);
		printf("time taken (multithreaded): %lf seconds (agents %d)\n",time2, i);
		clock_gettime(CLOCK_MONOTONIC, &start);
		float approximation_percent = 90.0f;
		ar3 = vcg_auction_approximation(B, S, approximation_percent);
		clock_gettime(CLOCK_MONOTONIC, &end);
		double time3 = elapsed_seconds(start, end);
		printf("time taken (Approximation): %lf seconds (agents %d)\n",time3, i);
		double delta1 = time2-time1;
		double delta2 = time3-time1;

		printf("time delta: %lf seconds\n", delta1);
		fprintf(output_data, "%d,%lf,%lf,%lf,%lf,%lf\n", i, time1, time2, delta1, time3, delta2);
		for (size_t j = 0; j < S.count; j++){
			for (size_t k = 0; k < B.count; k++){
				if (ar1.allocation.quantity[j][k] != ar2.allocation.quantity[j][k]){
					fprintf(stderr, "error in multithreaded implementation in [%zu][%zu] expected %d got %d\n",
						j, k, ar1.allocation.quantity[j][k], ar2.allocation.quantity[j][k]);
					result = false;
				}else if (ar1.allocation.quantity[j][k] != ar3.allocation.quantity[j][k]){
					fprintf(stderr, "error in approximation implementation in [%zu][%zu] expected %d got %d\n",
						j, k, ar1.allocation.quantity[j][k], ar3.allocation.quantity[j][k]);
					result = false;
				}
			}
		}
	}
	fclose(output_data);
	return result;

}
