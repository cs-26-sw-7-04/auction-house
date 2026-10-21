from fastapi import FastAPI
from pydantic import BaseModel, Field
import datetime
import geocoder

app = FastAPI()


class resources_requirement(BaseModel):
    single_thread: bool
    gpu_vram: int
    gpu_need: bool
    ram: int
    flops: int
    storage: int

class location(BaseModel):
    city: str | None = Field(
        None, description="City wher the task giver is located"
    )
    state: str | None = Field(None, description="region")
    country: str | None = Field(None, description="country code")
    coordinates: list[float] | None = Field(
        None, description="[Latitude, Longitude]"
    )



class Auctiontask(BaseModel):
    task_type: str
    deadline: datetime.time
    playload_tag: str
    max_money_budget: int
    resources_requirement
    validation_method: str
    location


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.post("/task")
async def ingest_task(task: Auctiontask):
    return task