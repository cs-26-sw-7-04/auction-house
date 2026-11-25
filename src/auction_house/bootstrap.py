"""Composition root: turns settings into a wired-up `AuctionHouse`."""
from auction_house import (  # noqa: F401  (importing `components` registers the built-ins)
    components,
    plugins,
)
from auction_house.config import Settings
from auction_house.house import AuctionHouse, Components


def build_house(settings: Settings) -> AuctionHouse:
    solver = plugins.solvers.create(settings.solver)
    return AuctionHouse(
        Components(
            tasks=plugins.tasks.create(settings.task_store),
            auctions=plugins.auctions.create(settings.auction_store),
            bids=plugins.bids.create(settings.bid_pool),
            grouper=plugins.groupers.create(settings.grouper),
            eligibility=plugins.eligibility.create(settings.eligibility),
            engine=plugins.engines.create(settings.engine, solver=solver),
            deployer=plugins.deployers.create(settings.deployer),
            verifier=plugins.verifiers.create(settings.verifier),
            ledger=plugins.ledgers.create(settings.ledger),
            notifier=plugins.notifiers.create(settings.notifier),
        ),
        bidding_window=settings.bidding_window,
        max_rounds=settings.max_rounds,
    )
