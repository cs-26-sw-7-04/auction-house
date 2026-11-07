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
	B.value[0] = malloc(sizeof(double) * 2);
	B.value[0][0]  = 5;
	B.value[0][1]  = 10;
	B.value[1] = malloc(sizeof(double) * 2);
	B.value[1][0]  = 2;
	B.value[1][1]  = 4;
	B.value[2] = malloc(sizeof(double) * 2);
	B.value[2][0]  = -4000;
	B.value[2][1]  = 6;

	Sellers S = {0};
	S.count       = 1;
	S.capacity[0] = 2;
	S.tasks[0]       = malloc(sizeof(Task) * S.capacity[0]);
	S.tasks[0][0].id = 1;
	S.tasks[0][1].id = 2;
	S.tasks[0][0].flops = 1;
	S.tasks[0][1].flops = 1;
	S.cost[0]     = 1;





	auction_results ar = {0};
	ar = vcg_auction(B,S);
	print_allocation(ar.allocation);
	if (ar.allocation.rows == 0 || ar.allocation.cols == 0)
		result = false;
	if (ar.allocation.rows != 1 || ar.allocation.cols != 3)
		result = false;
	if (ar.allocation.quantity[0][0] != ar.allocation.quantity[0][1]
	    || ar.allocation.quantity[0][1] != 1)
		result = false;
	if (ar.allocated_tasks[0] != NULL && (ar.allocated_tasks[0][0] != 1 || ar.allocated_tasks[1][0] != 2)){
		for (size_t i = 0; i < B.count; i++){
			printf("-----%zu-----\n", i);
			for (size_t j = 0; j < ar.tasks_count[i]; j++){
				printf("%d\n", ar.allocated_tasks[i][j]);
			}
			
		}
		printf("ERROR: %d, %d expected 1, 2\n",ar.allocated_tasks[0][0],ar.allocated_tasks[1][0]);
		result = false;
	}

	int i = 0;
	while (B.value[i] != NULL){
		free(B.value[i]);
		i++;
	}
	free(ar.buyer_payments);
	free(ar.seller_payments);
	for (int k = 0; k < MAX_AGENTS; k++){
		if(ar.allocated_tasks[k] != NULL)
			free(ar.allocated_tasks[k]);
	}
	
		
	free(S.tasks[0]);
	return result;
}

TEST welfare_test()
{
	bool result = true;

	Buyers B = {0};
	B.count     = 3;
	B.demand[0] = 1;
	B.demand[1] = 1;
	B.demand[2] = 2;
	B.value[0] = malloc(sizeof(double) * 2);
	B.value[0][0]  = 5;
	B.value[0][1]  = 10;
	B.value[1] = malloc(sizeof(double) * 2);
	B.value[1][0]  = 2;
	B.value[1][1]  = 4;
	B.value[2] = malloc(sizeof(double) * 2);
	B.value[2][0]  = 3;
	B.value[1][1]  = 6;

	Sellers S = {0};
	S.count       = 1;
	S.capacity[0] = 2;
	S.tasks[0]       = malloc(sizeof(Task) * S.capacity[0]);
	S.tasks[0][0].id = 0;
	S.tasks[0][1].id = 1;
	S.tasks[0][0].flops = 1;
	S.tasks[0][1].flops = 1;
	S.cost[0]     = 1;
	S.capacity[1] = 2;
	S.tasks[1]       = malloc(sizeof(Task) * S.capacity[1]);
	S.tasks[1][0].id = 0;
	S.tasks[1][1].id = 1;
	S.tasks[1][0].flops = 1;
	S.tasks[1][1].flops = 1;
	S.cost[1]     = 0;
	

	auction_results ar = vcg_auction(B,S);
	print_allocation(ar.allocation);
	double expected_welfare = 6.0;
	double computed_welfare = welfare(&B, &S, &ar.allocation, NULL);
	printf("expected welfare: %lf computed welfare: %lf\n", expected_welfare, computed_welfare);
	if (computed_welfare < expected_welfare)
		result = false;
	if (ar.allocated_tasks[0]!= NULL && (ar.allocated_tasks[0][0] != 0 || ar.allocated_tasks[2][0] != 1)){
		printf("ERROR: %d, %d expected 0, 1\n",ar.allocated_tasks[0][0],ar.allocated_tasks[2][0]);
		result = false;
	}
	int i = 0;
	while (B.value[i] != NULL){
		free(B.value[i]);
		i++;
	}

	i = 0;
	while (B.allocated_tasks[i] != NULL){
		free(B.allocated_tasks[i]);
		i++;
	}
	return result;
}

TEST stress_test()
{
	bool result = true;
	

	Buyers B = {0};
	B.count = 9;
	for (int i = 0; i < 9; i++){
		B.demand[i] = (i % 2) +1;
		B.value[i] = malloc(sizeof(double) * 2);
		B.value[i][0] = (i % 7) + 2;
		B.value[i][1] = B.value[i][0]*2;
	}

	Sellers S = {0};
	S.count       = 2;
	S.capacity[0] = 2;
	S.cost[0]     = 1;
	S.tasks[0]       = malloc(sizeof(Task) * S.capacity[0]);
	S.capacity[1] = 2;
	S.cost[1]     = 1;
	S.tasks[1]       = malloc(sizeof(Task) * S.capacity[1]);
	auction_results ar = vcg_auction(B,S);
	if (ar.allocation.rows == 0 || ar.allocation.cols == 0){
		printf("ar.rows: %d ar.cols: %d\n", ar.allocation.rows, ar.allocation.cols);
		result = false;
	}
	if (ar.allocation.rows != 2 || ar.allocation.cols != 9)
		result = false;

	int i = 0;
	while (B.value[i] != NULL){
		free(B.value[i]);
		i++;
	}
	i = 0;
	while (B.allocated_tasks[i] != NULL){
		free(B.allocated_tasks[i]);
		i++;
	}
	return result;
}

bool stress_test_multithreaded()
{
	bool result = true;
	

	Buyers B = {0};
	B.count = 9;
	for (int i = 0; i < 9; i++){
		B.demand[i] = (i % 2) +1;
		B.value[i] = malloc(sizeof(double) * 2);
		B.value[i][0] = (i % 7) + 2;
		B.value[i][1] = B.value[i][0]*2;
	}
	Sellers S = {0};
	S.count       = 2;
	S.capacity[0] = 2;
	S.cost[0]     = 1;
	S.tasks[0]       = malloc(sizeof(Task) * S.capacity[0]);
	S.capacity[1] = 2;
	S.cost[1]     = 1;
	S.tasks[1]       = malloc(sizeof(Task) * S.capacity[0]);
	auction_results ar = vcg_auction_multithreaded(B,S);
	print_allocation(ar.allocation);
	if (ar.allocation.rows == 0 || ar.allocation.cols == 0){
		printf("ar.allocation.rows: %d ar.allocation.cols: %d\n", ar.allocation.rows, ar.allocation.cols);
		result = false;
	}
	if (ar.allocation.rows != 2 || ar.allocation.cols != 9)
		result = false;
	int i = 0;
	while (B.value[i] != NULL){
		free(B.value[i]);
		i++;
	}
	i = 0;
	while (B.allocated_tasks[i] != NULL){
		free(B.allocated_tasks[i]);
		i++;
	}
	return result;
}


static double elapsed_seconds(struct timespec start, struct timespec end)
{
    return (double)(end.tv_sec - start.tv_sec) +
           (double)(end.tv_nsec - start.tv_nsec) / 1e9;
}

TEST randomized_testing()
{
	bool result = true;
	Buyers B1 = {0};
	Sellers S1 = {0};
	auction_results ar1;
	auction_results ar2;
	//auction_results ar3;

	srand((unsigned)time(NULL));
	
	for (int i = 0; i < MAX_AGENTS; i++) {
		S1.capacity[i] = 1 + rand() % 9;
		S1.cost[i]     = 0; //1 + rand() % 9;
		S1.tasks[i] = malloc(sizeof(Task) * S1.capacity[i]);
		B1.demand[i] = rand() % 50 + 1;
		B1.value[i] = malloc(sizeof(double) * B1.demand[i]);
		B1.value[i][0] = (rand() % 7) + 2;
		for (int j = 0; j < B1.demand[i]-1; j++){
			B1.value[i][j+1] = B1.value[i][j]*2;
		}
	}
	int id = 1;
	for (int k = 1; k < 5; k ++){
		B1.count = rand() % k + 1;
		S1.count = rand() % k + 1;

		for (size_t i = 0; i < S1.count; i++){
			for (int j = 0; j < S1.capacity[i]; j++){
				S1.tasks[i][j].id = id++;
				S1.tasks[i][j].flops = rand() % 30 + 1;
			}
		}

		ar1 = vcg_auction(B1, S1);
		ar2 = vcg_auction(B1, S1);
		if (ar1.buyer_payments == ar2.buyer_payments) continue;
		
	for (size_t i = 0; i < B1.count; i++){

		for (size_t j = 0; j < ar1.tasks_count[i] && j < ar2.tasks_count[i]; j++){
			/* if(ar.allocated_tasks[i][j] != ar2.allocated_tasks[i][j] */
			/*    || ar2.allocated_tasks[i][j] != ar3.allocated_tasks[i][j]) */
			if(ar1.allocated_tasks[i][j] != ar2.allocated_tasks[i][j]){
				printf("mismatched ids %d %d\n", ar1.allocated_tasks[i][j], ar2.allocated_tasks[i][j]);
				result = false;
			}
		}
		for (size_t j = 0; j < S1.count; j++){
			if (ar1.allocation.quantity[j][i] != ar2.allocation.quantity[j][i]){
				printf("error in implementation in [%zu][%zu] expected %d got %d\n",
					j, i, ar1.allocation.quantity[j][i], ar2.allocation.quantity[j][i]);
				result = false;
		
			}
		}	
	}
	}
	for (int i = 0; i < MAX_AGENTS; i++) {
		free(S1.tasks[i]);
		free(B1.value[i]);
	}
	int i = 0;
	while (B1.allocated_tasks[i] != NULL){
		free(B1.allocated_tasks[i]);
		i++;
	}
	free(ar1.buyer_payments);
	free(ar1.seller_payments);
	free(ar2.buyer_payments);
	free(ar2.seller_payments);
	return result;
}

TEST approximation_basic_test()
{
	bool result = true;
	
	Buyers B = {0};
	B.count     = 3;
	B.demand[0] = 1;
	B.demand[1] = 1;
	B.demand[2] = 2;
	B.value[0] = malloc(sizeof(double) * 2);
	B.value[0][0]  = 5;
	B.value[0][1]  = 10;
	B.value[1] = malloc(sizeof(double) * 2);
	B.value[1][0]  = 2;
	B.value[1][1]  = 4;
	B.value[2] = malloc(sizeof(double) * 2);
	B.value[2][0]  = -4000;
	B.value[2][1]  = 6;

	Sellers S = {0};
	S.count       = 1;
	S.capacity[0] = 2;
	S.tasks[0]       = malloc(sizeof(Task) * S.capacity[0]);
	S.tasks[0][0].id = 1;
	S.tasks[0][1].id = 2;
	S.tasks[0][0].flops = 1;
	S.tasks[0][1].flops = 1;
	S.cost[0]     = 1;





	auction_results ar = vcg_auction_approximation(B,S);
	print_allocation(ar.allocation);
	if (ar.allocation.rows == 0 || ar.allocation.cols == 0)
		result = false;
	if (ar.allocation.rows != 1 || ar.allocation.cols != 3)
		result = false;
	if (ar.allocation.quantity[0][0] != ar.allocation.quantity[0][1]
	    || ar.allocation.quantity[0][1] != 1)
		result = false;
	if ((ar.allocated_tasks[0] != NULL && ar.allocated_tasks[1] != NULL) && (ar.allocated_tasks[0][0] != 1 || ar.allocated_tasks[1][0] != 2)){
		for (size_t i = 0; i < B.count; i++){
			printf("-----%zu-----\n", i);
			for (size_t j = 0; j < ar.tasks_count[i]; j++){
				printf("%d\n", ar.allocated_tasks[i][j]);
			}
			
		}
		printf("ERROR: %d, %d expected 1, 2\n",ar.allocated_tasks[0][0],ar.allocated_tasks[1][0]);
		result = false;
	}


	for (int i = 0; i < MAX_AGENTS; i++) {
		free(S.tasks[i]);
		free(B.value[i]);
	}
	int i = 0;
	while (B.allocated_tasks[i] != NULL){
		free(B.allocated_tasks[i]);
		i++;
	}

	return result;
}



TEST time_test()
{
	bool result = true;
	Buyers B = {0};
	Sellers S = {0};
	auction_results ar1 = {0};
	auction_results ar2 = {0};



	srand((unsigned)time(NULL));
	int id = 1;
	for (int i = 0; i < MAX_AGENTS; i++) {

		S.capacity[i] = 1 + rand() % 9;
		S.cost[i]     = 0; //1 + rand() % 9;
		S.tasks[i] = calloc(S.capacity[i],sizeof(Task));
		if (S.tasks[i] == NULL){
			fprintf(stderr, "failed to allocate S.tasks[%d]\n", i);
			abort();
		}
		B.demand[i] = rand() % 50 + 1;
		B.value[i] = calloc(B.demand[i], sizeof(double));
		if (B.value[i] == NULL){
			fprintf(stderr, "failed to allocate B.value[%d]\n", i);
			abort();
		}
		B.value[i][0] = (rand() % 7) + 2;
		for (int j = 0; j < B.demand[i]-1; j++){
			B.value[i][j+1] = B.value[i][j]*2;
		}
	}

	for (int i = 1; i < 6; i ++){
		B.count = i;
		S.count = i;

		for (size_t i = 0; i < S.count; i++){
			for (int j = 0; j < S.capacity[i]; j++){
				S.tasks[i][j].id = id++;
				S.tasks[i][j].flops = rand() % 30 + 1;
			}
		}
		
		struct timespec start, end;

		clock_gettime(CLOCK_MONOTONIC, &start);
		ar1 = vcg_auction(B, S);
		clock_gettime(CLOCK_MONOTONIC, &end);
		double time1 = elapsed_seconds(start, end);
		print_allocation(ar1.allocation);
		printf("time taken: %lf seconds (agents %d)\n",time1, i);
		clock_gettime(CLOCK_MONOTONIC, &start);
		ar2 = vcg_auction_approximation(B, S);
		clock_gettime(CLOCK_MONOTONIC, &end);
		double time2 = elapsed_seconds(start, end);
		print_allocation(ar2.allocation);
		printf("time taken (approximation): %lf seconds (agents %d)\n",time2, i);
		double delta1 = time2-time1;
		printf("time delta: %lf seconds\n", delta1);
		if (ar1.buyer_payments == NULL) continue;
		for (size_t j = 0; j < S.count; j++){
			for (size_t k = 0; k < B.count; k++){
				if (ar1.allocation.quantity[j][k] != ar2.allocation.quantity[j][k]){
					fprintf(stderr, "error in approximation implementation in [%zu][%zu] expected %d got %d\n",
						j, k, ar1.allocation.quantity[j][k], ar2.allocation.quantity[j][k]);
					result = false;
				}
			}
		}
		free(ar1.buyer_payments);
		free(ar1.seller_payments);
		free(ar2.buyer_payments);
		free(ar2.seller_payments);
	}
	for (int i = 0; i < MAX_AGENTS; i++) {
		free(S.tasks[i]);
		free(B.value[i]);
	}

 	for (int i = 0; i < MAX_AGENTS; i++) {
		if (B.allocated_tasks[i] != NULL){
			free(B.allocated_tasks[i]);
		}

	}
	return result;
}
