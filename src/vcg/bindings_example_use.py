from vcg_bindings import *
'''
B = VCG_buyers_python()
B.count = 3
B.demand[0] = 1
B.demand[1] = 1
B.demand[2] = 20
B.value[0]  = 5
B.value[1]  = 2
B.value[2]  = 3

S = VCG_sellers_python()
S.count       = 4
for i in range(0,5):
    S.capacity[i] = 2
    S.cost[i]     = 1

allo = vcglib.vcg_auction(B, S)
vcglib.print_allocation(allo)
#exit(not (allo.quantity[0][0] == allo.quantity[0][1] == 1))
'''

auction = Auction(
        [Seller([Task(0, 1), Task(1, 1)])],
        [Buyer(1, [5, 10]), Buyer(1, [2, 4]), Buyer(1, [-4000, 6])]
        )

auction.print_allocation()
