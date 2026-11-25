"""Broadcast notifier: the house is the subject, subscribed bidders are the observers."""
import asyncio
import logging
import threading
from collections.abc import Generator
from contextlib import contextmanager

from auction_house import plugins
from auction_house.domain import Announcement, Auction

log = logging.getLogger(__name__)


class _Subscription:
    """One listener. It is created on the event loop that serves the listener, while
    the house publishes from other threads, so `push` hands the message to that loop."""

    def __init__(self, bidder_id: str, size: int):
        self.bidder_id = bidder_id
        self._loop = asyncio.get_running_loop()
        self._queue: asyncio.Queue[Announcement] = asyncio.Queue(size)

    async def get(self) -> Announcement:
        return await self._queue.get()

    def push(self, announcement: Announcement) -> None:
        self._loop.call_soon_threadsafe(self._put, announcement)

    def _put(self, announcement: Announcement) -> None:
        # A listener that cannot keep up loses its oldest message instead of slowing
        # the house. Announcements are hints; `GET /auctions` stays the source of truth.
        if self._queue.full():
            self._queue.get_nowait()
        self._queue.put_nowait(announcement)


@plugins.notifiers.register("broadcast")
class BroadcastNotifier:
    """Tells every subscribed bidder when an auction opens or closes.

    Publishing never blocks and never raises, so the house is not slowed or broken
    by a slow or dead listener. Subscriptions live in this process only."""

    def __init__(self, queue_size: int = 100):
        self._queue_size = queue_size
        self._subscriptions: set[_Subscription] = set()
        self._lock = threading.Lock()

    @contextmanager
    def subscribe(self, bidder_id: str) -> Generator[_Subscription]:
        """Listen until the context exits. Must be called on the event loop that
        will read the announcements."""
        subscription = _Subscription(bidder_id, self._queue_size)
        with self._lock:
            self._subscriptions.add(subscription)
        try:
            yield subscription
        finally:
            with self._lock:
                self._subscriptions.discard(subscription)

    def auction_opened(self, auction: Auction) -> None:
        self._publish("auction_opened", auction)

    def auction_closed(self, auction: Auction) -> None:
        self._publish("auction_closed", auction)

    def _publish(self, event: str, auction: Auction) -> None:
        # Only these fields are announced: never the bids or the outcome.
        announcement = Announcement(
            event=event, auction_id=auction.auction_id, status=auction.status, closes_at=auction.closes_at,
        )
        with self._lock:
            subscriptions = list(self._subscriptions)
        for subscription in subscriptions:
            try:
                subscription.push(announcement)
            except Exception:  # e.g. the listener's loop is closed; never let it reach the house
                log.exception("announcing to %s failed", subscription.bidder_id)
