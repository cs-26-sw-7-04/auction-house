"""Application factory.

    uvicorn auction_house.api:create_app --factory

Passing `house` (or `settings`) in makes the app easy to test: nothing is global.
"""
import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from auction_house.api import routes
from auction_house.bootstrap import build_house
from auction_house.config import Settings
from auction_house.domain import (
    AuctionHouseError,
    Conflict,
    Forbidden,
    Invalid,
    NotFound,
    Unavailable,
)
from auction_house.house import AuctionHouse

log = logging.getLogger(__name__)

STATUS_FOR = {
    NotFound: status.HTTP_404_NOT_FOUND,
    Conflict: status.HTTP_409_CONFLICT,
    Invalid: 422,
    Forbidden: status.HTTP_403_FORBIDDEN,
    Unavailable: status.HTTP_503_SERVICE_UNAVAILABLE,
}


async def _run_on_timer(house: AuctionHouse, seconds: float) -> None:
    """:3"""
    while True:
        try:
            await asyncio.to_thread(house.tick) # We run baby, ticking the clock of the house
        except Exception:  # keep the timer alive whatever one round does
            log.exception("auction round failed")
        await asyncio.sleep(seconds)


def create_app(settings: Settings | None = None, house: AuctionHouse | None = None) -> FastAPI:
    """:3"""
    settings = settings or Settings()

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = settings
        app.state.house = house or build_house(settings)
        timer = (asyncio.create_task(_run_on_timer(app.state.house, settings.tick.total_seconds()))
                 if settings.auto_run else None)
        try:
            yield
        finally:
            if timer:
                timer.cancel()

    app = FastAPI(title="Auction House", lifespan=lifespan)

    @app.exception_handler(AuctionHouseError)
    async def house_error(_: Request, error: AuctionHouseError) -> JSONResponse:
        code = next((c for kind, c in STATUS_FOR.items() if isinstance(error, kind)), status.HTTP_400_BAD_REQUEST)
        return JSONResponse(status_code=code, content={"detail": str(error) or type(error).__name__})

    for router in (routes.submitters, routes.bidders, routes.operators, routes.health):
        app.include_router(router)
    return app
