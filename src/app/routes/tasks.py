""":3"""
import uuid

from fastapi import APIRouter, HTTPException

from app.models import *

router = APIRouter(
    prefix="/tasks",
    tags=["tasks"]
)


@router.post("/", status_code=201)
async def ingest_task(task: Task) -> TaskRecord:
    """Submit a single task for auction :3"""
    return store_task(task)


@router.post("/batch", status_code=201)
async def ingest_tasks(batch: list[Task]) -> list[TaskRecord]:
    """Submit several tasks at once :3"""
    return [store_task(task) for task in batch]


@router.get("/{id}")
async def get_task(id: uuid.UUID) -> TaskRecord:
    """Get the status of a task :3"""
    return get_record(id)


@router.get("/{id}/result")
async def get_task_result(id: uuid.UUID) -> TaskRecord:
    """Get the result of a completed task :DDDD"""
    record = get_record(id)
    if record.status != TaskStatus.COMPLETED:
        raise HTTPException(status_code=409, detail="Task is not completed")
    # TODO: return the stored result once result storage exists in some form.
    return record
