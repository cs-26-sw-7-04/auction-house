"""The HTTP surface, one router per role."""
import uuid
 
from fastapi import APIRouter, Response, status
from pydantic import BaseModel
 
from auction_house.api.deps import Bidder, House, Operator, Submitter
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


@bidders.put("/auctions/{auction_id}/tasks/{task_id}/bid", status_code=status.HTTP_204_NO_CONTENT)
def place_bid(
    auction_id: uuid.UUID, task_id: uuid.UUID, request: BidRequest, bidder_id: Bidder, house: House
) -> Response:
    """Place or replace your sealed bid on one task of an open auction. You can bid
    on as many of its tasks as you like."""
    house.submit_bid(auction_id, task_id, bidder_id, request)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@bidders.get("/auctions/{auction_id}/bids")
def my_bids(auction_id: uuid.UUID, bidder_id: Bidder, house: House) -> list[Bid]:
    """Read back your own bids in this auction. Nobody else's are readable."""
    return house.own_bids(auction_id, bidder_id)



@bidders.get("/assignments")
def my_assignments(bidder_id: Bidder, house: House) -> list[Assignment]:
    """Tasks you won, what you are paid for them, and the images to run."""
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
    """Bundle the pending tasks and open auctions now, instead of waiting for the timer."""
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
