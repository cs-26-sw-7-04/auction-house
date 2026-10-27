""":3"""
import uvicorn

from app.tasks import app


def main():
    """:3"""
    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
