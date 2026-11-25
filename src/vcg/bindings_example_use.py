from vcg_bindings import *
from dataclasses import dataclass
import ctypes

libc = ctypes.CDLL(None)
libc.malloc.restype = ctypes.c_void_p
libc.malloc.argtypes = [ctypes.c_size_t]
libc.free.argtypes = [ctypes.c_void_p]

# Basic VCG Test 1:
print("=== Basic VCG Test 1 ===")
auction = AuctionBuilder(
        [Seller(0, [Task(0, 1), Task(1, 1)], 1)],
        [Buyer(0, 1, [5, 10]), Buyer(1, 1, [2, 4]), Buyer(2, 2, [-4000, 6])]
        )

print("Should be: 1 1 0")
results = auction.run() 
results.print_allocation()
print(results.welfare)
print("")

# Welfare test:
print("=== Welfare test ===")
auction = AuctionBuilder()
auction.add_buyer(Buyer(0, 1, [5]))
auction.add_buyer(Buyer(1, 1, [2]))
auction.add_buyer(Buyer(2, 2, [3,6]))
auction.add_seller(Seller(0, [Task(0, 1), Task(1, 1)], 1))

results = auction.run()
results.print_allocation()
print("Welfare should be 6.0")
print(results.welfare)
print("")

# Stress test:
# print("=== Stress test ===")
# auction = AuctionBuilder()
# for i in range(9):
#     auction.add_buyer(Buyer(i%2+1, [i%7+2, (i%7+2)*2]))
# auction.add_seller(Seller([Task(0, 1), Task(1, 1)], 1))
