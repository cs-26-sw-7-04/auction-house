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

typedef struct {
	size_t rows;
	size_t cols;
	int* matrix; //stored continously in memory index into field (i,j) by A.matix[A.rows*i + j] where j > cols obviously.
} Allocation;

typedef struct {
	int d; // demand bounds
} Buyer;

typedef struct {
	int s; // capacity
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
	da_foreach(Allocation, A, &a)
	{
		if (allocation_is_feasible(B, S, A)) da_append(&allo, A);
	}
	
}

/*
  @param B Array of Buyers
  @param S Array of Sellers
  @param x pointer to allocation matrix to be checked
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
