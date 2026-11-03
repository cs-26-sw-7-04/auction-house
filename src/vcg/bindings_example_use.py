from vcg_bindings import *

B = VCG_buyers_python()
B.count = 3
B.demand[0] = 1
B.demand[1] = 1
B.demand[2] = 2
B.value[0]  = 5
B.value[1]  = 2
B.value[2]  = 3

S = VCG_sellers_python()
S.count       = 1
S.capacity[0] = 2
S.cost[0]     = 1

allo = vcglib.vcg_auction(B, S)
exit(not (allo.quantity[0][0] == allo.quantity[0][1] == 1))
