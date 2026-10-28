""":3"""
from fastapi import APIRouter

router = APIRouter(
    prefix="/assignments",
    tags=["Assignments"]
)


@router.post("/{id}/heartbeat")
def heartbeat(id: str):
    """:3"""
    pass


@router.post("/{id}/result")
def submit_result(id: str):
    """:3"""
    pass
