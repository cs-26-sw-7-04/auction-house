import os

import uvicorn


def main() -> None:
    uvicorn.run(
        "auction_house.api:create_app", factory=True,
        host=os.environ.get("HOST", "0.0.0.0"), port=int(os.environ.get("PORT", "7777")),
    )


if __name__ == "__main__":
    main()
