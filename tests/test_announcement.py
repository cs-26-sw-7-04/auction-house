"""Business-logic tests of announcements: who is told what, and when."""
import asyncio
import datetime

import pytest

from auction_house.bootstrap import build_house
from auction_house.config import Settings
from auction_house.domain import TaskSpec, utcnow
from auction_house.plugins import ComponentSpec


def spec() -> TaskSpec:
    return TaskSpec(image="registry/job:1", deadline=utcnow() + datetime.timedelta(hours=1), max_budget=100)


@pytest.fixture
def house():
    # One task per auction, so every submitted task opens its own auction.
    settings = Settings(
        _env_file=None,
        bundler=ComponentSpec(name="batch", options={"size": 1}),
        notifier=ComponentSpec(name="broadcast", options={"queue_size": 1}),
    )
    return build_house(settings)


def open_auction(house):
    house.submit_task("s", spec())
    (auction,) = house.open_auctions()
    return auction


def test_every_subscriber_is_told_when_an_auction_opens(house):
    async def scenario():
        with house.c.notifier.subscribe("alice") as alice, house.c.notifier.subscribe("bob") as bob:
            auction = open_auction(house)
            return auction, await asyncio.wait_for(alice.get(), 1), await asyncio.wait_for(bob.get(), 1)

    auction, for_alice, for_bob = asyncio.run(scenario())
    assert for_alice == for_bob
    assert (for_alice.event, for_alice.auction_id, for_alice.closes_at) == (
        "auction_opened", auction.auction_id, auction.closes_at,
    )


def test_an_announcement_carries_no_bids_or_outcome(house):
    async def scenario():
        with house.c.notifier.subscribe("alice") as alice:
            open_auction(house)
            return await asyncio.wait_for(alice.get(), 1)

    heard = asyncio.run(scenario())
    assert set(heard.model_dump()) == {"event", "auction_id", "status", "closes_at"}


def test_a_listener_that_falls_behind_keeps_only_the_newest_and_does_not_slow_the_house(house):
    async def scenario():
        with house.c.notifier.subscribe("alice") as alice:
            auctions = [open_auction(house) for _ in range(3)]  # alice reads none of them
            await asyncio.sleep(0)  # let the announcements be delivered
            return auctions, await asyncio.wait_for(alice.get(), 1)

    auctions, heard = asyncio.run(scenario())
    assert heard.auction_id == auctions[-1].auction_id


def test_nobody_is_told_after_leaving(house):
    async def scenario():
        with house.c.notifier.subscribe("alice") as alice:
            pass
        open_auction(house)
        await asyncio.sleep(0)
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(alice.get(), 0.05)

    asyncio.run(scenario())
