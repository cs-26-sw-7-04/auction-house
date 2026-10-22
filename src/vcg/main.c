#include <stdio.h>
#include <stdbool.h>
#include <stdlib.h>

void assign_agent_types(da_Buyer_t* B, da_Seller_t* S, Allocation* x);
bool allocation_is_feasible(da_Buyer_t* B, da_Seller_t* S, Allocation* x);
int vcg_social_welfare(da_Buyer_t* B, da_Seller_t* S, Allocation* x);
Allocation* vcg_optimal_welfare(da_Buyer_t* B, da_Seller_t* S, da_Allocation_t* xs);
int net_traded_quantity(Buyer* B, Seller* S, Allocation x);

int main(void)
{
	printf("Hello, World!\n");
	return 0;
}


void Auction (da_Buyer_t B, da_Seller_t S, da_Allocation_t a, Valuations *v)
{
	da_Allocation_t allo = {0};
	da_foreach(Allocation, A, &a){
		if (allocation_is_feasible(&B, &S, A)) da_append(&allo, *A);
	}
}

/*allocation_is_feasible

  returns wheather or not an allocation is feasible.

  @param B Array of Buyers
  @param S Array of Sellers
  @param x pointer to allocation matrix to be checked
  @return bool
*/
bool allocation_is_feasible(da_Buyer_t* B, da_Seller_t* S, Allocation* x)
{
	for (int j = 0; j < B->count; j++)
	{
		for (int i = 0; i < S->count; i++){
			if (x->matrix[x->rows*i + j] > S->items[i].s) return false;
		}
	}

	for (int i = 0; i < S->count; i++)
	{
		for (int j = 0; j < B->count; j++){
			if (x->matrix[x->rows*i + j] > B->items[i].d) return false;
		}
	}

	return true;
}

/*vcg_social_welfare

  returns the social welfare calulated using the method in VCG.

  @param B da_Buyer_t Dynamic array of buyers
  @param S da_Seller_t Dynamic array of sellers
  @param x Allocation* Pointer to the allocation to calculate welfare for.
*/
int vcg_social_welfare(da_Buyer_t* B, da_Seller_t* S, Allocation* x)
{
	int rhs;
	int lhs;
	for (int j = 0; j < B->count; j++){
		int tmp = 0;
		for (int i = 0; i < S->count; i++){
			tmp += x->matrix[x->rows*i + j];
		}
		rhs += B->items[j].v * tmp;
	}
	for (int i = 0; i < S->count; i++){
		int tmp = 0;
		for (int j = 0; j < B->count; j++){
			tmp += x->matrix[x->rows*i + j];
		}
		lhs += S->items[i].c * tmp;
	}
	return rhs - lhs;
}


/*vcg_optimal_welfare

  Computes the optimal social welfare for VCG auction using the method
  from VCG.

  @param xs Dynamic array of feasible allocations.
  @return Pointer to allocation.
*/
Allocation* vcg_optimal_welfare(da_Buyer_t* B, da_Seller_t* S, da_Allocation_t* xs)
{
	int prev_max, max_index, max;
	prev_max = max_index = max = 0;
	for (int i = 0; i < xs->count; i++){
		prev_max = max;
		int tmp = vcg_social_welfare(B, S, &xs->items[i]);
		if (tmp > max) {max = tmp; max_index = i;}
	}
	return &xs->items[max_index];
}

/*net_traded_quantity

  returns the net traded quantity of an agent k

  @param B buyer if agent is buyer otherwise set to NULL
  @param S seller if agent is seller otherwise set to NULL
  @param x Relavent allocation matrix

  @return integer of the net traded quantity.
*/
int net_traded_quantity(Buyer* B, Seller* S, Allocation x)
{
	int h = x.rows;
	int w = x.cols;
	int tmp = 0;

	if (B != NULL){
		for (int i = 0; i < x.rows; i++){
			tmp += x.matrix[x.rows*i + B->id];
		}
	}
	if (S != NULL){
		for (int i = 0; i < x.cols; i++){
			tmp += x.matrix[x.rows*S->id + i];
		}
	}
	return tmp;
}

void assign_agent_types(da_Buyer_t* B, da_Seller_t* S, Allocation* x)
{
	/* x->matix[x->rows*i + j]; /\* i is seller *\/ */
	for (int i = 0; i < B->count; i++){
	        B->items[i].theta = net_traded_quantity(&B->items[i], NULL, *x);
	}
	for (int i = 0; i < S->count; i++){
		S->items[i].theta = net_traded_quantity(NULL, &S->items[i], *x);
	}	
}
