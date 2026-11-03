"""The HTTP surface: roles, sealed bids, and the whole flow end to end."""
import datetime

import pytest
from fastapi.testclient import TestClient

from auction_house.api import create_app
from auction_house.config import Principal, Settings
from auction_house.plugins import ComponentSpec

KEYS = {
    "k-sub": Principal(role="submitter", id="sub"),
    "k-sub2": Principal(role="submitter", id="sub2"),
    "k-alice": Principal(role="bidder", id="alice"),
    "k-bob": Principal(role="bidder", id="bob"),
    "k-op": Principal(role="operator", id="op"),
}
SUB, SUB2, ALICE, BOB, OP = ({"X-API-Key": k} for k in KEYS)


@pytest.fixture
def client():
    settings = Settings(_env_file=None, api_keys=KEYS, bundler=ComponentSpec(name="batch", options={"size": 8}))
    with TestClient(create_app(settings)) as client:
        yield client


def submit(client, budget=100) -> str:
    deadline = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)).isoformat()
    response = client.post("/tasks", headers=SUB, json={"image": "demo:1", "deadline": deadline, "max_budget": budget})
    assert response.status_code == 201
    return response.json()["task_id"]


def test_whole_flow_and_sealing(client):
    task_id = submit(client)
    (auction,) = client.post("/operator/auctions", headers=OP).json()
    auction_id = auction["auction_id"]

    # The public view offers the task but hides its budget, its image and any bids.
    public = client.get(f"/auctions/{auction_id}").json()
    assert [t["task_id"] for t in public["tasks"]] == [task_id]
    assert "max_budget" not in str(public) and "demo:1" not in str(public) and "outcome" not in public

    bid = {"capacity": 1, "unit_price": 10}
    assert client.put(f"/auctions/{auction_id}/bid", json=bid, headers=ALICE).status_code == 204
    assert client.put(f"/auctions/{auction_id}/bid", json={"capacity": 1, "unit_price": 30}, headers=BOB).status_code == 204
    assert client.get(f"/auctions/{auction_id}/bid", headers=ALICE).json()["unit_price"] == 10
    assert client.get(f"/auctions/{auction_id}/bid", headers=BOB).json()["unit_price"] == 30

    cleared = client.post(f"/operator/auctions/{auction_id}/clear?force=true", headers=OP).json()
    assert [(a["bidder_id"], a["payment"]) for a in cleared["outcome"]["awards"]] == [("alice", 30)]

    assert client.get("/assignments", headers=BOB).json() == []
    (mine,) = client.get("/assignments", headers=ALICE).json()
    assert mine["tasks"][0]["spec"]["image"] == "demo:1"

    assert client.get(f"/tasks/{task_id}", headers=SUB).json()["status"] == "executing"
    assert client.post(f"/assignments/{task_id}/result", json={}, headers=ALICE).json()["status"] == "completed"
    assert client.get(f"/tasks/{task_id}", headers=SUB).json()["status"] == "completed"


def test_roles_and_ownership_are_enforced(client):
    task_id = submit(client)
    auction_id = client.post("/operator/auctions", headers=OP).json()[0]["auction_id"]
    bid = {"capacity": 1, "unit_price": 1}

    assert client.put(f"/auctions/{auction_id}/bid", json=bid).status_code == 401
    assert client.put(f"/auctions/{auction_id}/bid", json=bid, headers={"X-API-Key": "nope"}).status_code == 401
    assert client.put(f"/auctions/{auction_id}/bid", json=bid, headers=SUB).status_code == 403
    assert client.post("/operator/auctions", headers=ALICE).status_code == 403
    assert client.get(f"/operator/auctions/{auction_id}", headers=ALICE).status_code == 403
    assert client.get(f"/tasks/{task_id}", headers=SUB2).status_code == 404
    assert client.get(f"/auctions/{auction_id}/bid", headers=ALICE).status_code == 404  # no bid yet


def test_rule_violations_map_to_http_codes(client):
    assert client.post("/tasks", headers=SUB, json={"image": "x", "deadline": "2000-01-01T00:00:00Z", "max_budget": 1}).status_code == 422
    auction_id = (submit(client), client.post("/operator/auctions", headers=OP).json()[0]["auction_id"])[1]
    assert client.post(f"/operator/auctions/{auction_id}/clear", headers=OP).status_code == 409  # window open
    assert client.get("/auctions/00000000-0000-0000-0000-000000000000").status_code == 404
