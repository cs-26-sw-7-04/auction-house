import ctypes
import pathlib

def parent(path):
    return pathlib.Path(path).parent.resolve()

so_file = f"{parent(__file__)}/build/lib/libvcg.so"
MAX_AGENTS = 512

vcglib = ctypes.CDLL(so_file)


class VCG_allocation_python(ctypes.Structure):
    _fields_ = [("rows",ctypes.c_int),
                ("cols",ctypes.c_int),
                ("quantity",(ctypes.c_int * MAX_AGENTS) * MAX_AGENTS)]
class VCG_buyers_python(ctypes.Structure):
    _fields_ = [("count",ctypes.c_size_t),
                ("demand",ctypes.c_int * MAX_AGENTS),
                ("value",(ctypes.c_double * MAX_AGENTS))]
class VCG_sellers_python(ctypes.Structure):
    _fields_ = [("count",ctypes.c_size_t),
                ("capacity",ctypes.c_int * MAX_AGENTS),
                ("cost",(ctypes.c_double * MAX_AGENTS))]
vcglib.vcg_auction.argtypes = [VCG_buyers_python, VCG_sellers_python]
vcglib.vcg_auction.restype = VCG_allocation_python
vcglib.print_allocation.argtypes = [VCG_allocation_python]
vcglib.print_allocation.restype = None

