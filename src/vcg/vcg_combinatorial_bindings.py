import ctypes
import pathlib
from dataclasses import dataclass

def parent(path):
    return pathlib.Path(path).parent.resolve()

so_file = f"{parent(__file__)}/build/lib/libvcg_combinatorial.so"
vcglib = ctypes.CDLL(so_file)
# typedef struct {
# 	const int *tasks;  /* task indices; the order decides how the payment is split on ties */
# 	size_t task_count;
# 	int bidder;        /* any int identifying the bidder */
# 	int64_t price;     /* what the bidder asks to run all of `tasks` */
# } comb_bid;


class comb_bid_c(ctypes.Structure):
    _fields_ = [ ("tasks", ctypes.POINTER(ctypes.c_int)),
                 ("task_count", ctypes.c_size_t),
                 ("bidder", ctypes.c_int),
                 ("price", ctypes.c_int64)]

class comb_award_c(ctypes.Structure):
    _fields_ = [("task", ctypes.c_int),
                ("bidder", ctypes.c_int),
                ("bid", ctypes.c_size_t),
                ("payment",ctypes.c_int64)]
class comb_outcome_c(ctypes.Structure):
    _fields_ = [("ok", ctypes.c_bool),
                ("awards",ctypes.POINTER(comb_award_c)),
                ("award_count", ctypes.c_size_t),
                ("unallocated", ctypes.POINTER(ctypes.c_int)),
                ("unallocated_count", ctypes.c_size_t),
                ("welfare", ctypes.c_int64)]
# comb_outcome vcg_comb_clear(const int64_t *values, size_t task_count, const comb_bid *bids, size_t bid_count, comb_solver solver);

vcglib.vcg_comb_clear.argtypes = [ctypes.POINTER(ctypes.c_int64),ctypes.c_size_t, ctypes.POINTER(comb_bid_c), ctypes.c_size_t, ctypes.c_int]
vcglib.vcg_comb_clear.restype = comb_outcome_c