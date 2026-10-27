#include <stdbool.h>
#include <stdio.h>
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

	Allocation ar = vcg_auction(B,S);
	if (ar.rows == 0 || ar.cols == 0)
		result = false;
	if (ar.rows != 1 || ar.cols != 3)
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

	Allocation ar = vcg_auction(B,S);
	if (ar.rows == 0 || ar.cols == 0){
		printf("ar.rows: %d ar.cols: %d\n", ar.rows, ar.cols);
		result = false;
	}
	if (ar.rows != 1 || ar.cols != 9)
		result = false;

	print_allocation(ar);
	return result;
}
