from fastapi import APIRouter, Depends
from ..models.biddersmodel import bidder as Bidder
from ..state import get_subscribers_list

router = APIRouter(
    prefix="/annoucement",
    tags=["Annoucement"]
)

@router.post("/annoucement")
def annoucement_subscribers():
    pass

@router.post("/subscribe")
def subscribe(bidder: Bidder, subscibers: list = Depends(get_subscribers_list)):
    subscibers.append(bidder)
    return{"message": "Bidder subscribed successfully", "current_count": len(get_subscribers_list)}

@router.get("/subscribers")
def subscripbers(subscribers: list = Depends(get_subscribers_list)):
    return subscribers