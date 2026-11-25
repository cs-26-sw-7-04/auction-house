"""Which tasks are sold together, and who may bid on them."""
from collections.abc import Sequence

from auction_house import plugins
from auction_house.domain import Task


@plugins.groupers.register("batch")
class BatchGrouper:
    """Oldest first, at most `size` tasks per auction."""

    def __init__(self, size: int = 32): # TODO: make this configurable
        if size < 1:
            raise ValueError("size must be at least 1")
        self.size = size

    def plan(self, pending: Sequence[Task]) -> list[list[Task]]:
        """:3"""
        ordered = sorted(pending, key=lambda t: t.submitted_at)
        return [ordered[i:i + self.size] for i in range(0, len(ordered), self.size)]


@plugins.eligibility.register("all")
class AllEligible:
    def is_eligible(self, bidder_id: str, task: Task) -> bool:
        """:3"""
        return True
