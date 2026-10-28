""":3"""
from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def root():
    """:3"""
    return {"message": "Hello World"}

@router.get("/health")
async def health():
    """:3"""
    return {"status": "ok"}

@router.get("/ping")
async def ping():
    """:3"""
    return {"message": "pong"}
