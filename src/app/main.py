""":3"""
import os

import uvicorn
from fastapi import FastAPI

from app.routes import assignments, auctions, bidders, miscellaneous, tasks, annoucement
from .state import *

from vcg.vcg_bindings import VCG_buyers_python, VCG_sellers_python, vcglib

app = FastAPI(title="Auction House")

app.include_router(assignments.router)#, prefix="/api/v1")
app.include_router(auctions.router)#, prefix="/api/v1")
app.include_router(tasks.router)#, prefix="/api/v1")
app.include_router(miscellaneous.router)#, prefix="/api/v1")
app.include_router(bidders.router)#, prefix="/api/v1")

def main():
    """:3"""
    app.include_router(assignments.router)#, prefix="/api/v1")
    app.include_router(auctions.router)#, prefix="/api/v1")
    app.include_router(tasks.router)#, prefix="/api/v1")
    app.include_router(miscellaneous.router)#, prefix="/api/v1")
    app.include_router(bidders.router)#, prefix="/api/v1")
    app.include_router(annoucement.router)
    
    #Run an auction:

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
    vcglib.print_allocation(allo)


    # Inside a Kubernetes pod the API needs to bind to 0.0.0.0.
    # Read host and port from the environment
    uvicorn.run(
        "app.main:app",
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8000")),
    )


if __name__ == "__main__":
    main()
