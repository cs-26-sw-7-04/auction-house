"""Plug-and-play: components register under a name and are created from configuration.

    @solvers.register("my-solver")
    class MySolver: ...

or, from another package, through an entry point in the group
`auction_house.solvers` (see pyproject.toml). `AH_SOLVER__NAME=my-solver`
then selects it, and `AH_SOLVER__OPTIONS='{"x": 1}'` passes keyword arguments.
"""
from collections.abc import Callable
from importlib.metadata import entry_points
from typing import Any

from pydantic import BaseModel, Field

from auction_house import ports


class ComponentSpec(BaseModel):
    """Which component to use, and with what options."""
    name: str
    options: dict[str, Any] = Field(default_factory=dict)


class Registry[T]:
    def __init__(self, kind: str, port: type):
        self.kind, self.port = kind, port
        self._factories: dict[str, Callable[..., T]] = {}
        self._loaded = False

    def register(self, name: str) -> Callable[[Callable[..., T]], Callable[..., T]]:
        def decorator(factory: Callable[..., T]) -> Callable[..., T]:
            if name in self._factories:
                raise ValueError(f"{self.kind} {name!r} is already registered")
            self._factories[name] = factory
            return factory
        return decorator

    def names(self) -> list[str]:
        self._load_entry_points()
        return sorted(self._factories)

    def create(self, spec: ComponentSpec, **context: Any) -> T:
        """Create the component. `context` is for components built on others,
        e.g. an engine gets the `solver` it clears with."""
        self._load_entry_points()
        try:
            factory = self._factories[spec.name]
        except KeyError:
            raise ValueError(f"unknown {self.kind} {spec.name!r}; available: {', '.join(self.names())}") from None
        component = factory(**context, **spec.options)
        if not isinstance(component, self.port):
            raise TypeError(f"{self.kind} {spec.name!r} does not implement {self.port.__name__}")
        return component

    def _load_entry_points(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        for point in entry_points(group=f"auction_house.{self.kind}s"):
            self._factories.setdefault(point.name, point.load())


tasks = Registry[ports.TaskStore]("task_store", ports.TaskStore)
auctions = Registry[ports.AuctionStore]("auction_store", ports.AuctionStore)
bids = Registry[ports.BidPool]("bid_pool", ports.BidPool)
groupers = Registry[ports.Grouper]("grouper", ports.Grouper)
eligibility = Registry[ports.Eligibility]("eligibility_rule", ports.Eligibility)
solvers = Registry[ports.Solver]("solver", ports.Solver)
engines = Registry[ports.ClearingEngine]("engine", ports.ClearingEngine)
deployers = Registry[ports.Deployer]("deployer", ports.Deployer)
verifiers = Registry[ports.Verifier]("verifier", ports.Verifier)
ledgers = Registry[ports.Ledger]("ledger", ports.Ledger)
notifiers = Registry[ports.Notifier]("notifier", ports.Notifier)
