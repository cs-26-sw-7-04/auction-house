"""Notifiers: tell bidders about auctions. Today bidders poll `GET /auctions`;
a webhook or message-queue notifier would implement the same two methods."""
import logging

from auction_house import plugins
from auction_house.domain import Auction

log = logging.getLogger(__name__)


@plugins.notifiers.register("logging")
class LoggingNotifier:
    def auction_opened(self, auction: Auction) -> None:
        """:3"""
        log.info("auction %s open for %d task(s) until %s", auction.auction_id, len(auction.task_ids), auction.closes_at)

    def auction_closed(self, auction: Auction) -> None:
        """:3"""
        log.info("auction %s %s", auction.auction_id, auction.status)
