import datetime

from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI()


class ResourcesRequirement(BaseModel):
    single_thread: bool
    gpu_vram: int
    gpu_need: bool
    ram: int
    flops: int
    storage: int


class Location(BaseModel):
    city: str | None = Field(
        None, description="City where the task giver is located"
    )
    state: str | None = Field(None, description="region")
    country: str | None = Field(None, description="country code")
    coordinates: list[float] | None = Field(
        None, description="[Latitude, Longitude]"
    )


class AuctionTask(BaseModel):
    task_type: str
    deadline: datetime.time
    playload_tag: str
    max_money_budget: int
    resources_requirement: ResourcesRequirement
    validation_method: str
    location: Location


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.post("/task")
async def ingest_task(task: AuctionTask):
    return task
