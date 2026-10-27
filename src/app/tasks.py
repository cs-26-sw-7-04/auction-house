""":3"""
import datetime
import enum
import uuid
from typing import Annotated

from fastapi import FastAPI, HTTPException
from pydantic import AfterValidator, BaseModel, Field, field_validator, model_validator

app = FastAPI(title="Auction House API")


def to_utc(value: datetime.datetime) -> datetime.datetime:
    """Normalise to UTC. Naive datetimes are assumed to already be UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=datetime.timezone.utc)
    return value.astimezone(datetime.timezone.utc)

# Any datetime field using this type is converted to UTC on input.
UtcDatetime = Annotated[datetime.datetime, AfterValidator(to_utc)]


class ResourcesRequirement(BaseModel):
    """Resources a bidder needs to execute the task :3"""
    single_thread: bool
    gpu_need: bool
    gpu_vram: int = Field(0, ge=0, description="GPU memory in MB")
    ram: int = Field(ge=0, description="RAM in MB")
    flops: int = Field(gt=0, description="Estimated total floating point operations")
    storage: int = Field(ge=0, description="Storage in MB")

    @model_validator(mode="after")
    def check_gpu(self):
        """:3"""
        if not self.gpu_need and self.gpu_vram > 0:
            raise ValueError("gpu_vram is set but gpu_need is false")
        return self


class Location(BaseModel):
    """Optional locality information about the task :3"""
    city: str | None = Field(None, description="City where the task giver is located")
    state: str | None = Field(None, description="Region")
    country: str | None = Field(None, description="Country code")
    coordinates: tuple[float, float] | None = Field(
        None, description="(Latitude, Longitude)"
    )


class ValidationMethod(str, enum.Enum):
    """How the auction house verifies a completed task."""
    HASH = "hash"
    TIMEOUT_ONLY = "timeout_only"
    #TRUST_ME = "trust_me" #bro


class TaskStatus(str, enum.Enum):
    """Task lifecycle :3"""
    PENDING     = "pending"
    IN_AUCTION  = "in_auction"
    ALLOCATED   = "allocated"
    UNALLOCATED = "unallocated"
    EXECUTING   = "executing"
    VERIFYING   = "verifying"
    COMPLETED   = "completed"
    FAILED      = "failed"


class Task(BaseModel):
    """A task as submitted by the task submitter :3"""
    task_type: str
    deadline: UtcDatetime = Field(description="Converted to UTC, must be in the future")
    payload_tag: str = Field(description="URI or URL for the payload container")
    max_money_budget: int = Field(gt=0, description="Maximum payment")
    resources_requirement: ResourcesRequirement
    validation_method: ValidationMethod
    location: Location

    @field_validator("deadline")
    @classmethod
    def deadline_in_future(cls, value: datetime.datetime):
        """:3"""
        if value <= datetime.datetime.now(datetime.timezone.utc):
            raise ValueError("deadline must be in the future")
        return value


class TaskRecord(BaseModel):
    """A stored task with auction house state :3"""
    task_id: uuid.UUID
    status: TaskStatus
    submitted_at: UtcDatetime
    task: Task


tasks: dict[uuid.UUID, TaskRecord] = {} # in memory, as we have no DB right now


def store_task(task: Task) -> TaskRecord:
    """:3"""
    record = TaskRecord(
        task_id=uuid.uuid4(),
        status=TaskStatus.PENDING,
        submitted_at=datetime.datetime.now(datetime.timezone.utc),
        task=task,
    )
    tasks[record.task_id] = record
    return record


def get_record(task_id: uuid.UUID) -> TaskRecord:
    """.3"""
    record = tasks.get(task_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return record


""" 
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
"""


@app.get("/")
async def root():
    """:3"""
    return {"message": "Hello World"}

@app.get("/health")
async def health():
    """:3"""
    return {"status": "ok"}

@app.get("/ping")
async def ping():
    """:3"""
    return {"message": "pong", "status": "ok"}


@app.post("/tasks", status_code=201)
async def ingest_task(task: Task) -> TaskRecord:
    """Submit a single task for auction :3"""
    return store_task(task)


@app.post("/tasks/batch", status_code=201)
async def ingest_tasks(batch: list[Task]) -> list[TaskRecord]:
    """Submit several tasks at once :3"""
    return [store_task(task) for task in batch]


@app.get("/tasks/{task_id}")
async def get_task(task_id: uuid.UUID) -> TaskRecord:
    """Get the status of a task :3"""
    return get_record(task_id)


@app.get("/tasks/{task_id}/result")
async def get_task_result(task_id: uuid.UUID) -> TaskRecord:
    """Get the result of a completed task :DDDD"""
    record = get_record(task_id)
    if record.status != TaskStatus.COMPLETED:
        raise HTTPException(status_code=409, detail="Task is not completed")
    # TODO: return the stored result once result storage exists in some form.
    return record
