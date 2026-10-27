""":3"""
import os

import uvicorn


def main():
    """:3"""
    # Inside a Kubernetes pod the API needs to bind to 0.0.0.0.
    # Read host and port from the environment
    uvicorn.run(
        "auction_house.main:app",
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8000")),
    )


if __name__ == "__main__":
    main()
