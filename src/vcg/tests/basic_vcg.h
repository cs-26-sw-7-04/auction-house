#include <stdbool.h>
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
