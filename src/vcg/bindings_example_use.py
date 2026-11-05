from vcg_bindings import *
import ctypes

libc = ctypes.CDLL(None)
libc.malloc.restype = ctypes.c_void_p
libc.malloc.argtypes = [ctypes.c_size_t]
libc.free.argtypes = [ctypes.c_void_p]

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

B = Buyers_C();
B.count     = 3;
B.demand[0] = 1;
B.demand[1] = 1;
B.demand[2] = 2;
ptr = libc.malloc(ctypes.sizeof(ctypes.c_double) * 2);
B.value[0] = ctypes.cast(ptr, ctypes.POINTER(ctypes.c_double))
B.value[0][0]  = 5;
B.value[0][1]  = 10;
ptr = libc.malloc(ctypes.sizeof(ctypes.c_double) * 2);
B.value[1] = ctypes.cast(ptr, ctypes.POINTER(ctypes.c_double))
B.value[1][0]  = 2;
B.value[1][1]  = 4;
ptr = libc.malloc(ctypes.sizeof(ctypes.c_double) * 2);
B.value[2] = ctypes.cast(ptr, ctypes.POINTER(ctypes.c_double))
B.value[2][0]  = -4000;
B.value[2][1]  = 6;

S = Sellers_C();
S.count       = 1;
S.capacity[0] = 2;
ptr = libc.malloc(ctypes.sizeof(Task_C) * S.capacity[0]);
S.tasks[0]       = ctypes.cast(ptr, ctypes.POINTER(Task_C))
S.tasks[0][0].flops = 1;
S.tasks[0][1].flops = 1;
S.cost[0]     = 1;
ptr = libc.malloc(ctypes.sizeof(Task_C) * S.capacity[1]);
S.tasks[1]       = ctypes.cast(ptr, ctypes.POINTER(Task_C))
S.tasks[1][1].flops = 1;

allo = vcglib.vcg_auction(B, S)
vcglib.print_allocation(allo.allocation)


auction = Auction(
        [Seller([Task(0, 1), Task(1, 1)], 1)],
        [Buyer(1, [5, 10]), Buyer(1, [2, 4]), Buyer(2, [-4000, 6])]
        )

auction.print_allocation()
