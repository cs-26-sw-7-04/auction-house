import datetime

from fastapi import FastAPI, Request
from pydantic import BaseModel, Field
import geocoder


app = FastAPI()


class ResourcesRequirement(BaseModel):
    single_thread: bool | None = None
    gpu_vram: int | None = Field(None, ge=0, description="GPU VRAM in GB")
    gpu_need: bool = False
    ram: int | None  = Field(None, ge=0, description="Ram in GB")
    flops: int | None = Field(None, ge=0, description="Need flops")
    storage: int | None = Field(None, ge=0, description="Storage in GB")


def loopup_location(ip:str ) -> Location | None:
    g = geocoder.ip(ip)
    if not g.ok:
        return None
    return Location(
        city = g.city,
        state = g.state,
        country = g.country,
        coordinates = g.coordinates,
    )


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
    deadline: datetime.datetime
    playload_tag: str
    max_money_budget: int = None
    resources_requirement: ResourcesRequirement = None
    validation_method: str
    location: Location = None


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.post("/task")
async def ingest_task(task: AuctionTask, request: Request):
    ip = request.client.host
    task.location = loopup_location(ip)
    return task
