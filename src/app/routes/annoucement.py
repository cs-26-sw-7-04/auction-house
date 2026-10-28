from fastapi import APIRouter

router = APIRouter(
    prefix="/annoucement",
    tags=["Annoucement"]
)

@router.post("/annoucement")
def annoucement_subscribers():
    pass

@router.post("/subscribe")
def subscribe():
    pass 