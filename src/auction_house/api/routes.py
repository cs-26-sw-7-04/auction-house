"""The HTTP surface, one router per role."""
import asyncio
import uuid

from fastapi import APIRouter, Response, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from auction_house.api.deps import Announcer, Bidder, House, Operator, Submitter
from auction_house.domain import (
    Assignment,
    Auction,
    AuctionView,
    Bid,
    BidRequest,
    Sha256,
    Task,
    TaskSpec,
)

submitters = APIRouter(prefix="/tasks", tags=["Submitters"])
bidders = APIRouter(tags=["Bidders"])
operators = APIRouter(prefix="/operator", tags=["Operator"], dependencies=[Operator])
health = APIRouter(tags=["Health"])

# --- submitters --------------------------------------------------------------

@submitters.post("", status_code=status.HTTP_201_CREATED)
def submit_task(spec: TaskSpec, owner: Submitter, house: House) -> Task:
    """Submit a task. It waits as `pending` until the next auction picks it up."""
    return house.submit_task(owner, spec)


@submitters.get("")
def my_tasks(owner: Submitter, house: House) -> list[Task]:
    """All tasks you have submitted, whatever their status."""
    return house.tasks_of(owner)


@submitters.get("/{task_id}")
def my_task(task_id: uuid.UUID, owner: Submitter, house: House) -> Task:
    """One of your tasks. A task that does not exist and one that belongs to someone else are indistinguishable."""
    return house.get_task(task_id, owner)

# --- bidders -----------------------------------------------------------------

@bidders.get("/auctions")
def list_auctions(house: House) -> list[AuctionView]:
    """What is up for auction. Bids and outcomes are not shown."""
    return house.list_auctions()


@bidders.get("/auctions/{auction_id}")
def get_auction(auction_id: uuid.UUID, house: House) -> AuctionView:
    """One auction as bidders see it: the tasks on offer, without bids or outcome."""
    return house.view(house.get_auction(auction_id))


@bidders.put("/auctions/{auction_id}/bid", status_code=status.HTTP_204_NO_CONTENT)
def place_bid(
    auction_id: uuid.UUID, request: BidRequest, bidder_id: Bidder, house: House
) -> Response:
    """Place or replace your sealed bid on an open auction. The bid lists the bundles
    of tasks you are willing to run, each with its price. Replacing a bid replaces
    all of its bundles."""
    house.submit_bid(auction_id, bidder_id, request)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@bidders.get("/auctions/{auction_id}/bid")
def my_bid(auction_id: uuid.UUID, bidder_id: Bidder, house: House) -> Bid:
    """Read back your own bid in this auction. Nobody else's is readable."""
    return house.own_bid(auction_id, bidder_id)


@bidders.get("/announcements", responses={200: {"content": {"text/event-stream": {}}}})
async def announcements(bidder_id: Bidder, announcer: Announcer) -> StreamingResponse:
    """Server-sent events: an `auction_opened` or `auction_closed` event for each
    auction, as it happens. The event names the auction; fetch its offers from
    `GET /auctions/{auction_id}`. Nothing is replayed, so after (re)connecting,
    list `GET /auctions` to catch up."""
    async def events():
        with announcer.subscribe(bidder_id) as subscription:
            while True:
                try:
                    announcement = await asyncio.wait_for(subscription.get(), timeout=15)
                except TimeoutError:
                    yield ": keep-alive\n\n"  # stops proxies from closing an idle connection
                    continue
                yield f"event: {announcement.event}\ndata: {announcement.model_dump_json()}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")


@bidders.get("/assignments")
def my_assignments(bidder_id: Bidder, house: House) -> list[Assignment]:
    """Tasks you won, grouped by auction, and what you are paid for each group."""
    return house.assignments_of(bidder_id)


class ResultReport(BaseModel):
    result_hash: Sha256 | None = None


@bidders.post("/assignments/{task_id}/result")
def report_result(task_id: uuid.UUID, report: ResultReport, bidder_id: Bidder, house: House) -> Task:
    """Report the result of a task you won. It is verified and the task settled."""
    return house.report_result(bidder_id, task_id, report.result_hash)

# --- operators ---------------------------------------------------------------

@operators.post("/auctions", status_code=status.HTTP_201_CREATED)
def open_auctions(house: House) -> list[Auction]:
    """Group the pending tasks into auctions now, instead of waiting for the timer."""
    return house.open_auctions()


@operators.get("/auctions/{auction_id}")
def inspect_auction(auction_id: uuid.UUID, house: House) -> Auction:
    """Everything about an auction, including its outcome."""
    return house.get_auction(auction_id)


@operators.post("/auctions/{auction_id}/clear")
def clear_auction(auction_id: uuid.UUID, house: House, force: bool = False) -> Auction:
    """Clear an auction. `force` clears before the bidding window has ended."""
    return house.clear(auction_id, force=force)

# --- other ------------------------------------------------------------------

@health.get("/health")
def get_health() -> dict[str, str]:
    """System health. Return ok if successfull"""
    return {"status": "ok"}
