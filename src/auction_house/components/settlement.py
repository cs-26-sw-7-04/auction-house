"""Stubs for what happens after a bidder reports a result: verification and
reputation. Both are placeholders for the design, not finished mechanisms."""
import logging
import uuid

from auction_house import plugins
from auction_house.domain import Task, Verification

log = logging.getLogger(__name__)


@plugins.verifiers.register("method")
class MethodVerifier:
    """Follows the task's own verification setting; only hash matching exists."""

    def verify(self, task: Task, result_hash: str | None) -> bool:
        """:3"""
        if task.spec.verification is Verification.HASH:
            return result_hash == task.spec.expected_result_hash
        return True


@plugins.verifiers.register("accept-all")
class AcceptAll:
    def verify(self, task: Task, result_hash: str | None) -> bool:
        """:3"""
        return True


@plugins.verifiers.register("reject-all")
class RejectAll:
    def verify(self, task: Task, result_hash: str | None) -> bool:
        """:3"""
        return False


@plugins.verifiers.register("accept-none-empty-results")
class AcceptNoneEmptyResults:
    def verify(self, task: Task, result_hash: str | None) -> bool:
        """:3"""
        return result_hash is not None


@plugins.ledgers.register("logging")
class LoggingLedger:
    """Reputation is logged, not stored or used."""

    def record(self, bidder_id: str, task_id: uuid.UUID, success: bool) -> None:
        """:3"""
        log.info("reputation: %s %s task %s", bidder_id, "completed" if success else "failed", task_id)
