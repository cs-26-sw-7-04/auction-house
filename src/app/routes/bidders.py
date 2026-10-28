from fastapi import APIRouter

router = APIRouter(
    prefix="/bidders",
    tags=["Bidders"]
)


@router.get("/me/assignments")
def get_my_assignments():
    """:3"""
    pass
