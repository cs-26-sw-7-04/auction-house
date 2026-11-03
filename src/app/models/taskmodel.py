""":3"""
import datetime
import enum
import uuid
from typing import Annotated

from fastapi import HTTPException
from pydantic import AfterValidator, BaseModel, Field, field_validator, model_validator


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


class VerificationMethod(enum.StrEnum):
    """How the auction house verifies a completed task :3"""
    NO_VERIFICATION = "no"
    HASH = "hash"
    TIMEOUT_ONLY = "timeout_only"
    #TRUST_ME = "trust_me" #bro


class TaskType(enum.StrEnum):
    DETERMINISTIC_SODUKU = "sudoku"


class TaskStatus(enum.StrEnum):
    """Task lifecycle :3"""
    PENDING     = "pending"
    IN_AUCTION  = "in_auction"
    ALLOCATED   = "allocated"
    UNALLOCATED = "unallocated"
    EXECUTING   = "executing"
    VERIFYING   = "verifying"
    COMPLETED   = "completed"
    FAILED      = "failed"


class TaskSpec(BaseModel):
    """The task definition, without time-dependent checks"""
    task_type: TaskType
    deadline: UtcDatetime = Field(description="Converted to UTC, must be in the future")
    payload_tag: str = Field(description="URI or URL for the payload container")
    max_money_budget: int = Field(gt=0, description="Maximum payment")
    resources_requirement: ResourcesRequirement
    verification_method: VerificationMethod
    expected_result_hash: str | None = Field(None, pattern=r"^[0-9a-f]{64}$")


class Task(TaskSpec):
    """What the submitter sends. Only this is checked against 'now' :3"""
    @field_validator("deadline")
    @classmethod
    def deadline_in_future(cls, value: datetime.datetime):
        """:3"""
        if value <= datetime.datetime.now(datetime.timezone.utc):
            raise ValueError("deadline must be in the future")
        return value

    @model_validator(mode="after")
    def check_verification(self):
        """:3"""
        if (self.verification_method is VerificationMethod.HASH
                and self.expected_result_hash is None):
            raise ValueError("expected_result_hash is required for hash verification")
        return self


class TaskRecord(BaseModel):
    """A stored task with auction house state :3"""
    task_id: uuid.UUID
    status: TaskStatus
    submitted_at: UtcDatetime
    task: TaskSpec

tasks_store: dict[uuid.UUID, TaskRecord] = {} # in memory, as we have no DB right now


def store_task(task: Task) -> TaskRecord:
    """:3"""
    record = TaskRecord(
        task_id=uuid.uuid4(),
        status=TaskStatus.PENDING,
        submitted_at=datetime.datetime.now(datetime.timezone.utc),
        task=task,
    )
    tasks_store[record.task_id] = record
    return record


def get_record(task_id: uuid.UUID) -> TaskRecord:
    """.3"""
    record = tasks_store.get(task_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return record
