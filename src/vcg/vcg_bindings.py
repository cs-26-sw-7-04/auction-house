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
                ("value",(ctypes.POINTER(ctypes.c_double) * MAX_AGENTS)),
                ("tasks_count",ctypes.c_size_t*MAX_AGENTS),
                ("tasks_cap",ctypes.c_size_t*MAX_AGENTS),
                ("allocated_tasks",ctypes.POINTER(ctypes.c_int)*MAX_AGENTS)]
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
                ("allocation", Allocation_C),
                ("tasks_count", ctypes.c_size_t * MAX_AGENTS),
                ("tasks_cap", ctypes.c_size_t*MAX_AGENTS),
                ("allocated_tasks", ctypes.POINTER(ctypes.c_int)*MAX_AGENTS)]
    def __repr__(self):
        return f"Auction_Results_C(buyer_payments: {self.buyer_payments}, seller_payments: {self.seller_payments}, allocation: {self.allocation})"

vcglib.vcg_auction.argtypes = [Buyers_C, Sellers_C]
vcglib.vcg_auction.restype = Auction_Results_C
vcglib.print_allocation.argtypes = [Allocation_C]
vcglib.print_allocation.restype = None
vcglib.assign_tasks.argtypes = [Sellers_C, ctypes.POINTER(ctypes.c_int),ctypes.POINTER(ctypes.c_int), ctypes.c_int]
vcglib.print_allocation.restype = Sellers_C
vcglib.welfare.argtypes = [
    ctypes.POINTER(Buyers_C),
    ctypes.POINTER(Sellers_C),
    ctypes.POINTER(Allocation_C),
    ctypes.c_voidp]
vcglib.welfare.restype = ctypes.c_double;

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


class AuctionResults:
    c_allocation: Allocation_C
    welfare: float
    mappings: Dict[int, int]

    def __init__(self, c_b: Buyers_C, c_s: Sellers_C, c_auct: Auction_Results_C):
        self.c_allocation = c_auct.allocation
        self.welfare = vcglib.welfare(c_b, c_s, c_auct.allocation, None)

    def print_allocation(self):
        vcglib.print_allocation(self.c_allocation)

class AuctionBuilder:
    def __init__(self, sellers=None, buyers=None):
        self.sellers = sellers if sellers is not None else []
        self.buyers = buyers if buyers is not None else []

    def __repr__(self):
        return f"Auction({self.sellers}, {self.buyers})"
    
    def add_buyer(self, buyer):
        self.buyers.append(buyer)

    def add_seller(self, seller):
        self.sellers.append(seller)

    def run(self) -> AuctionResults:
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
                ss.tasks[i][j].assigned = 0

        return AuctionResults(
            bs, ss,
            vcglib.vcg_auction(bs, ss)
            )
    