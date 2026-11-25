import ctypes
import pathlib


def parent(path):
    return pathlib.Path(path).parent.resolve()

so_file = pathlib.Path(__file__).resolve().parent / "build" / "lib" / "libvcg_combinatorial.so"
vcglib = ctypes.CDLL(str(so_file))

# typedef struct {
# 	const int *tasks;  /* task indices; the order decides how the payment is split on ties */
# 	size_t task_count;
# 	int bidder;        /* any int identifying the bidder */
# 	int64_t price;     /* what the bidder asks to run all of `tasks` */
# } comb_bid;


class comb_bid_c(ctypes.Structure):
    _fields_ = [
        ("tasks", ctypes.POINTER(ctypes.c_int)),
        ("task_count", ctypes.c_size_t),
        ("bidder", ctypes.c_int),
        ("price", ctypes.c_int64),
    ]

class comb_award_c(ctypes.Structure):
    _fields_ = [
        ("task", ctypes.c_int),
        ("bidder", ctypes.c_int),
        ("bid", ctypes.c_size_t),
        ("payment", ctypes.c_int64),
    ]

class comb_outcome_c(ctypes.Structure):
    _fields_ = [
        ("ok", ctypes.c_bool),
        ("awards", ctypes.POINTER(comb_award_c)),
        ("award_count", ctypes.c_size_t),
        ("unallocated", ctypes.POINTER(ctypes.c_int)),
        ("unallocated_count", ctypes.c_size_t),
        ("welfare", ctypes.c_int64),
    ]

vcglib.vcg_comb_clear.argtypes = [
    ctypes.POINTER(ctypes.c_int64),
    ctypes.c_size_t,
    ctypes.POINTER(comb_bid_c),
    ctypes.c_size_t,
    ctypes.c_int,
]
vcglib.vcg_comb_clear.restype = comb_outcome_c

libc = ctypes.CDLL(None)
libc.free.argtypes = [ctypes.c_void_p]
libc.free.restype = None

def release(outcome: comb_outcome_c) -> None:
    """Free the two arrays the library allocated for an outcome.
 
    Assumes the library allocated them with malloc; if it has its own function for
    this, call that here instead. Freeing a null pointer is harmless."""
    libc.free(ctypes.cast(outcome.awards, ctypes.c_void_p))
    libc.free(ctypes.cast(outcome.unallocated, ctypes.c_void_p))
