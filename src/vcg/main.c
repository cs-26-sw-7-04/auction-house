#include <stdio.h>
#include <stdbool.h>

#define da_append(xs, x)								\
	do {										\
	if ((xs)->count >= (xs)->capacity){						\
	if ((xs)->capacity == 0) (xs)->capacity = 256;					\
	else (xs)->capacity *= 2;							\
	(xs)->items = realloc((xs)->items, (xs)->capacity*sizeof(*(xs)->items));	\
	}										\
	(xs)->items[(xs)->count++] = (x);						\
	} while(0)									
		
#define da_foreach(Type, it, da) for (Type *it = (da)->items; it < (da)->items + (da)->count; ++it)

bool allocation_is_feasible(da_Buyer_t* B, da_Seller_t* S, Allocation* x);
int vcg_social_welfare(da_Buyer_t* B, da_Seller_t* S, Allocation* x);
Allocation* vcg_optimal_welfare(da_Allocation_t xs);
int net_traded_quantity(buyer* B, seller* S, Allocation x);


/* the allocation matrix should look something like this:

      b1  b2  b3
   s1 1   0   2
   s2 4   4   4
   s2 8   1   3
 */
typedef struct {
	size_t rows;
	size_t cols;
	int* matrix; //stored continuously. In memory index into field (i,j) by A.matix[A.rows*i + j] where j > cols obviously.
} Allocation;

typedef struct {
	int id;
	int d; // demand bounds
        int theta; // valuation
} Buyer;

typedef struct {
	int id;
	int s; // capacity
        int theta; // cost
} Seller;

typedef struct {
	Allocation items*;
	size_t count;
	size_t capacity;
} da_Allocation_t

typedef struct {
	Buyer items*;
	size_t count;
	size_t capacity;
} da_Buyer_t

typedef struct {
	Seller items*;
	size_t count;
	size_t capacity;
} da_Seller_t

int main(void)
{
	printf("Hello, World!\n");
	return 0;
}


void Auction (buyer* B, seller* S, da_Allocation_t a, Valuations *v)
{
	da_Allocation_t allo = {0};
	int i = 0;
	da_foreach(Allocation, A, &a)
	{
		if (allocation_is_feasible(B, S, A)) {da_append(&allo, A); a.items[i].id = i; i++;}
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
		for (int i = 0; i < S->count; i++)
		{
			if (x.matix[X.rows*i + j] > S->items[i].s) return false;
		}
	}

	for (int i = 0; i < S->count; i++)
	{
		for (int j = 0; j < B->count; j++)
		{
			if (x.matix[X.rows*i + j] > B->items[i].d) return false;
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
	for (int j = 0; j < B->count; j++)
	{
		int tmp = 0;
		for (int i = 0; i < S->count; i++)
		{
			tmp += x.matix[X.rows*i + j]
		}
		rhs += B->items[j].v * tmp;
	}
	for (int i = 0; i < S->count; i++)
	{
		int tmp = 0;
		for (int j = 0; j < B->count; j++)
		{
			tmp += x.matix[X.rows*i + j];
		}
		lhs += S->items[j].c * tmp;
	}
	return rhs - lhs;
}


/*vcg_optimal_welfare

  Computes the optimal social welfare for VCG auction using the method
  from VCG.

  @param xs Dynamic array of feasible allocations.
  @return Pointer to allocation.
 */
Allocation* vcg_optimal_welfare(da_Allocation_t xs)
{
	int prev_max, max_index, max;
	prev_max = max_index = max = 0;
	for (int i = 0; i < xs.count; i++){
		prev_max = max;
		int tmp = vcg_social_welfare(xs.items[i]);
		if (tmp > max) {max = tmp; max_index = i;}
	}
	return xs.items[max_index];
}

/*net_traded_quantity

  returns the net traded quantity of an agent k

  @param B buyer if agent is buyer otherwise set to NULL
  @param S seller if agent is seller otherwise set to NULL
  @param x Relavent allocation matrix

  @return integer of the net traded quantity.
 */
int net_traded_quantity(buyer* B, seller* S, Allocation x)
{
	int h = x.rows;
	int w = x.cols;
	int tmp = 0;

	if (B != NULL){
		for (int i = 0; i < x.rows; i++){
			tmp += x.matrix[x.rows*i + B->id]
		}
	}
	if (S != NULL){
		for (int i = 0; i < x.cols; i++){
			tmp += x.matrix[x.rows*S->id + i]
		}
	}
	return tmp;
}

int agent_utility(buyer* B, seller* S, Allocation x)
{
	x.matix[x.rows*i + j]; /* i is seller */
}
