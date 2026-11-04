import ctypes
import pathlib

def parent(path):
    return pathlib.Path(path).parent.resolve()

so_file = f"{parent(__file__)}/build/lib/libvcg.so"
MAX_AGENTS = 32

vcglib = ctypes.CDLL(so_file)

class Allocation_C(ctypes.Structure):
    _fields_ = [("rows",ctypes.c_int),
                ("cols",ctypes.c_int),
                ("quantity",(ctypes.c_int * MAX_AGENTS) * MAX_AGENTS)]
    def __repr__(self):
        return f"Allocation_C(rows: {self.rows}, cols: {self.cols}, quantity: {self.quantity})"
class Buyers_C(ctypes.Structure):
    _fields_ = [("count",ctypes.c_size_t),
                ("demand",ctypes.c_int * MAX_AGENTS),
                ("used_demand", ctypes.c_int * MAX_AGENTS),
                ("value",(ctypes.POINTER(ctypes.c_double) * MAX_AGENTS))]   
    def __repr__(self):
        return f"Buyers_C(count: {self.count}, demand: {self.demand}, used_demand: {self.used_demand}, value: {self.value})"

class Task_C(ctypes.Structure):
    _fields_ = [("id", ctypes.c_int),
                ("flops", ctypes.c_int),
                ("assigned", ctypes.c_bool)]
    def __repr__(self):
        return f"Task_C(id: {self.id}, flops: {self.flops}, assigned: {self.assigned})"

class Sellers_C(ctypes.Structure):
    _fields_ = [("count",ctypes.c_size_t),
                ("tasks", ctypes.POINTER(Task_C) * MAX_AGENTS),
                ("capacity",ctypes.c_int * MAX_AGENTS),
                ("cost",(ctypes.c_double * MAX_AGENTS))]
    def __repr__(self):
        return f"Sellers_C(count: {self.count}, tasks: {self.tasks}, capacity: {self.capacity}, cost: {self.cost})"

class Auction_Results_C(ctypes.Structure):
    _fields_ = [("buyer_payments", ctypes.POINTER(ctypes.c_double)),
                ("seller_payments", ctypes.POINTER(ctypes.c_double)),
                ("allocation", Allocation_C)]
    def __repr__(self):
        return f"Auction_Results_C(buyer_payments: {self.buyer_payments}, seller_payments: {self.seller_payments}, allocation: {self.allocation})"

vcglib.vcg_auction.argtypes = [Buyers_C, Sellers_C]
vcglib.vcg_auction.restype = Auction_Results_C
vcglib.print_allocation.argtypes = [Allocation_C]
vcglib.print_allocation.restype = None



libc = ctypes.CDLL(None)
libc.malloc.restype = ctypes.c_void_p
libc.malloc.argtypes = [ctypes.c_size_t]
libc.free.argtypes = [ctypes.c_void_p]


class Task:
    def __init__(self, id_, flops):
        self.id_ = id_
        self.flops = flops

    def __repr__(self):
        return f"Task({self.id_}, {self.flops})"

class Buyer:
    # values is a map from flops -> payment
    def __init__(self, max_flops, values):
        self.max_flops = max_flops
        self.values = values

    def __repr__(self):
        return f"Buyer({self.max_flops}, {self.values})"

class Seller:
    def __init__(self, tasks=None, cost=0):
        self.tasks = tasks if tasks is not None else []
        self.cost = cost
    
    def add_task(self, task):
        self.tasks.append(task)

    def __repr__(self):
        return f"Seller({self.tasks}, {self.cost})"

class Auction:
    def __init__(self, sellers=None, buyers=None):
        self.sellers = sellers if sellers is not None else []
        self.buyers = buyers if buyers is not None else []

    def __repr__(self):
        return f"Auction({self.sellers}, {self.buyers})"
    
    def add_buyer(self, buyer):
        self.buyers.append(buyer)

    def add_seller(self, seller):
        self.sellers.append(seller)

    def allocate(self) -> Auction_Results_C:
        bs = Buyers_C()
        bs.count = len(self.buyers)
        for i,b in enumerate(self.buyers):
            bs.demand[i] = b.max_flops
            bsviptr = libc.malloc(ctypes.sizeof( ctypes.c_double ) * len(b.values)) # TODO: free
            bs.value[i] = ctypes.cast(bsviptr, ctypes.POINTER(ctypes.c_double))
            for j,v in enumerate(b.values):
                bs.value[i][j] = v
        ss = Sellers_C()
        ss.count = len(self.sellers)
        for i,s in enumerate(self.sellers):
            ss.cost[i] = s.cost
            ss.capacity[i] = len(s.tasks)
            print(f"Capacity of {i}: {ss.capacity[i]}")
            tiptr = libc.malloc(ctypes.sizeof( Task_C ) * ss.capacity[i]) # TODO: free
            ss.tasks[i] = ctypes.cast(tiptr, ctypes.POINTER(Task_C))
            for j,t in enumerate(s.tasks):
                ss.tasks[i][j].flops = t.flops
                ss.tasks[i][j].id = t.id_
        print(f"Buyers: {[foo.__dict__ for foo in self.buyers]}")
        print(f"Sellers: {[foo.__dict__ for foo in self.sellers]}")
        print(f"")
        print(f"C Buyers: {bs}")
        print(f"C Sellers: {ss}")
        print(f"")

        return vcglib.vcg_auction(bs, ss)

    def print_allocation(self):
        vcglib.print_allocation(self.allocate().allocation)

            
        
        






