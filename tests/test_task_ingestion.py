"""
Business-rule tests for task ingestion, run through the HTTP interface.
Made with AI
"""
import datetime
import uuid

import pytest
from fastapi.testclient import TestClient

from app.tasks import app, tasks

client = TestClient(app)

UTC = datetime.timezone.utc

RESOURCES = {
    "single_thread": True,
    "gpu_need": False,
    "gpu_vram": 0,
    "ram": 512,
    "flops": 1_000_000,
    "storage": 100,
}


def in_one_hour() -> datetime.datetime:
    return datetime.datetime.now(UTC) + datetime.timedelta(hours=1)


def parse(value: str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))


def make_task(**overrides) -> dict:
    task = {
        "task_type": "hash",
        "deadline": in_one_hour().isoformat(),
        "payload_tag": "demo:latest",
        "max_money_budget": 100,
        "resources_requirement": dict(RESOURCES),
        "validation_method": "hash",
        "location": {},
    }
    task.update(overrides)
    return task


@pytest.fixture(autouse=True)
def clear_tasks():
    tasks.clear()
    yield
    tasks.clear()


def test_submitted_task_is_stored_as_pending():
    response = client.post("/tasks", json=make_task())

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "pending"
    assert uuid.UUID(body["task_id"]) in tasks


def test_deadline_in_other_timezone_is_converted_to_utc():
    plus_two = datetime.timezone(datetime.timedelta(hours=2))
    local = datetime.datetime.now(plus_two) + datetime.timedelta(hours=1)

    response = client.post("/tasks", json=make_task(deadline=local.isoformat()))

    stored = parse(response.json()["task"]["deadline"])
    assert stored.utcoffset() == datetime.timedelta(0)
    assert stored == local


def test_deadline_without_timezone_is_assumed_utc():
    naive = in_one_hour().replace(tzinfo=None)

    response = client.post("/tasks", json=make_task(deadline=naive.isoformat()))

    assert response.status_code == 201
    stored = parse(response.json()["task"]["deadline"])
    assert stored == naive.replace(tzinfo=UTC)


@pytest.mark.parametrize(
    "overrides",
    [
        {"deadline": "2000-01-01T00:00:00Z"},
        {"max_money_budget": 0},
        {"validation_method": "trust_me"},
        {"resources_requirement": {**RESOURCES, "gpu_vram": 4096}},
    ],
    ids=["deadline_in_past", "zero_budget", "unknown_validation", "vram_without_gpu"],
)
def test_invalid_task_is_rejected_and_not_stored(overrides):
    response = client.post("/tasks", json=make_task(**overrides))

    assert response.status_code == 422
    assert tasks == {}


def test_stored_task_can_be_fetched():
    task_id = client.post("/tasks", json=make_task()).json()["task_id"]

    response = client.get(f"/tasks/{task_id}")

    assert response.status_code == 200
    assert response.json()["task_id"] == task_id


def test_unknown_task_returns_404():
    assert client.get(f"/tasks/{uuid.uuid4()}").status_code == 404


def test_result_is_unavailable_before_completion():
    task_id = client.post("/tasks", json=make_task()).json()["task_id"]

    assert client.get(f"/tasks/{task_id}/result").status_code == 409


def test_batch_stores_every_task():
    response = client.post("/tasks/batch", json=[make_task(), make_task()])

    assert response.status_code == 201
    assert len(response.json()) == 2
    assert len(tasks) == 2


def test_batch_with_one_invalid_task_stores_nothing():
    batch = [make_task(), make_task(max_money_budget=0)]

    response = client.post("/tasks/batch", json=batch)

    assert response.status_code == 422
    assert tasks == {}
