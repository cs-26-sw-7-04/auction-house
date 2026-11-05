"""Authentication and access to the house, as FastAPI dependencies.

Callers are identified by their API key, never by a field in a request body, so
one bidder cannot read or replace another's sealed bid."""
import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader

from auction_house import ports
from auction_house.config import Principal, Role, Settings
from auction_house.house import AuctionHouse

api_key = APIKeyHeader(name="X-API-Key", auto_error=False)


def get_house(request: Request) -> AuctionHouse:
    """:3"""
    return request.app.state.house


def get_settings(request: Request) -> Settings:
    """:3"""
    return request.app.state.settings


House = Annotated[AuctionHouse, Depends(get_house)]


def get_announcer(house: House) -> ports.Announcer:
    """The configured notifier, if it lets bidders subscribe."""
    notifier = house.c.notifier
    if not isinstance(notifier, ports.Announcer):
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "announcements are not enabled")
    return notifier


Announcer = Annotated[ports.Announcer, Depends(get_announcer)]


def _principal(key: str | None, settings: Settings) -> Principal | None:
    found = None
    for known, principal in settings.api_keys.items():  # no early exit: constant-time per key
        if key is not None and secrets.compare_digest(known, key):
            found = principal
    return found


def require(role: Role):
    """Dependency that yields the caller's id, if the caller has `role`."""
    def dependency(
        key: Annotated[str | None, Security(api_key)],
        settings: Annotated[Settings, Depends(get_settings)],
    ) -> str:
        principal = _principal(key, settings)
        if principal is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or missing API key")
        if principal.role != role:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"This needs the {role} role")
        return principal.id
    return dependency


Submitter = Annotated[str, Depends(require("submitter"))]
Bidder = Annotated[str, Depends(require("bidder"))]
Operator = Depends(require("operator"))
