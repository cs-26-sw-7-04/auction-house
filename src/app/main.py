""":3"""
import os

import uvicorn
from fastapi import FastAPI

from app.routes import assignments, auctions, bidders, miscellaneous, tasks

app = FastAPI(title="Auction House")

app.include_router(assignments.router)#, prefix="/api/v1")
app.include_router(auctions.router)#, prefix="/api/v1")
app.include_router(tasks.router)#, prefix="/api/v1")
app.include_router(miscellaneous.router)#, prefix="/api/v1")
app.include_router(bidders.router)#, prefix="/api/v1")

def main():
    """:3"""
    # Inside a Kubernetes pod the API needs to bind to 0.0.0.0.
    # Read host and port from the environment
    uvicorn.run(
        "app.main:app",
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8000")),
    )


if __name__ == "__main__":
    main()
