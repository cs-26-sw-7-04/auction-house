""":3"""
from fastapi import APIRouter

router = APIRouter(
    prefix="/auctions",
    tags=["Auctions"]
)


@router.post("/{auction_id}/bids")
def submit_bid(auction_id: str):
    """:3"""
    pass


@router.get("/{auction_id}")
def get_auction(auction_id: str):
    """:3"""
    pass
