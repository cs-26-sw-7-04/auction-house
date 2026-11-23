"""The HTTP surface: roles, sealed bids, and the whole flow end to end."""
import datetime
import uuid

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
    settings = Settings(
        _env_file=None,
        api_keys=KEYS,
        grouper=ComponentSpec(name="batch", options={"size": 8}),
        solver=ComponentSpec(name="vcg_combinatorial", options={"algorithm": "2"}), # COMB_FAST_PIVOTS
        verifier=ComponentSpec(name="method"),
    )
    with TestClient(create_app(settings)) as client:
        yield client


def submit(client, budget=100) -> str:
    deadline = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)).isoformat()
    response = client.post("/tasks", headers=SUB, json={"image": "demo:1", "deadline": deadline, "max_budget": budget})
    assert response.status_code == 201
    return response.json()["task_id"]


def bid_url(auction_id: str) -> str:
    return f"/auctions/{auction_id}/bid"


def bundles(task_id: str, price: int) -> dict:
    return {"bundles": [{"tasks": [task_id], "price": price}]}


def test_whole_flow_and_sealing(client):
    task_id = submit(client)
    (auction,) = client.post("/operator/auctions", headers=OP).json()
    auction_id = auction["auction_id"]

    # The public view offers the task but hides its budget, its image and any bids.
    public = client.get(f"/auctions/{auction_id}").json()
    assert [t["task_id"] for t in public["tasks"]] == [task_id]
    assert "max_budget" not in str(public) and "demo:1" not in str(public) and "outcome" not in public

    assert client.put(bid_url(auction_id), json=bundles(task_id, 10), headers=ALICE).status_code == 204
    assert client.put(bid_url(auction_id), json=bundles(task_id, 30), headers=BOB).status_code == 204
    assert client.get(bid_url(auction_id), headers=ALICE).json()["bundles"][0]["price"] == 10
    assert client.get(bid_url(auction_id), headers=BOB).json()["bundles"][0]["price"] == 30

    cleared = client.post(f"/operator/auctions/{auction_id}/clear?force=true", headers=OP).json()
    assert [(a["bidder_id"], a["payment"]) for a in cleared["outcome"]["awards"]] == [("alice", 30)]

    assert client.get("/assignments", headers=BOB).json() == []
    (mine,) = client.get("/assignments", headers=ALICE).json()
    assert mine["task_ids"] == [task_id]
    assert mine["award"]["payment"] == 30

    assert client.get(f"/tasks/{task_id}", headers=SUB).json()["status"] == "executing"
    assert client.post(f"/assignments/{task_id}/result", json={}, headers=ALICE).json()["status"] == "completed"
    assert client.get(f"/tasks/{task_id}", headers=SUB).json()["status"] == "completed"


def test_roles_and_ownership_are_enforced(client):
    task_id = submit(client)
    auction_id = client.post("/operator/auctions", headers=OP).json()[0]["auction_id"]
    url, bid = bid_url(auction_id), bundles(task_id, 1)

    assert client.put(url, json=bid).status_code == 401
    assert client.put(url, json=bid, headers={"X-API-Key": "nope"}).status_code == 401
    assert client.put(url, json=bid, headers=SUB).status_code == 403
    assert client.post("/operator/auctions", headers=ALICE).status_code == 403
    assert client.get(f"/operator/auctions/{auction_id}", headers=ALICE).status_code == 403
    assert client.get(f"/tasks/{task_id}", headers=SUB2).status_code == 404
    assert client.get(url, headers=ALICE).status_code == 404  # no bid yet
    assert client.get("/operator/tasks", headers=ALICE).status_code == 403
    assert client.get("/operator/auctions", headers=SUB).status_code == 403


def test_rule_violations_map_to_http_codes(client):
    assert client.post("/tasks", headers=SUB, json={"image": "x", "deadline": "2000-01-01T00:00:00Z", "max_budget": 1}).status_code == 422
    task_id = submit(client)
    auction_id = client.post("/operator/auctions", headers=OP).json()[0]["auction_id"]
    assert client.post(f"/operator/auctions/{auction_id}/clear", headers=OP).status_code == 409  # window open
    assert client.get("/auctions/00000000-0000-0000-0000-000000000000").status_code == 404
    # a bid on a task that is not in the auction
    assert client.put(bid_url(auction_id), json=bundles(str(uuid.uuid4()), 1), headers=ALICE).status_code == 422
    assert client.put(bid_url(auction_id), json=bundles(task_id, 1), headers=ALICE).status_code == 204


def test_the_operator_can_export_every_task_and_auction(client):
    task_id = submit(client)
    assert [t["task_id"] for t in client.get("/operator/tasks", headers=OP).json()] == [task_id]
    assert client.get("/operator/auctions", headers=OP).json() == []
    auction_id = client.post("/operator/auctions", headers=OP).json()[0]["auction_id"]
    client.put(bid_url(auction_id), json=bundles(task_id, 10), headers=ALICE)
    client.post(f"/operator/auctions/{auction_id}/clear?force=true", headers=OP)
    (auction,) = client.get("/operator/auctions", headers=OP).json()
    assert auction["outcome"]["awards"][0]["bidder_id"] == "alice"
