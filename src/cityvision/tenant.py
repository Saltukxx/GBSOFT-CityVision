"""Per-request tenant city, applied as Postgres ``app.current_city_id``.

HTTP code sets this from the authenticated principal when strict tenancy is on.
Workers set it from ``jobs.city_id`` after claiming. Edge routes set it from
the device and reset it when the request ends. Unset context → Store uses ``*``.
"""

from __future__ import annotations

from contextvars import ContextVar, Token
from typing import Optional

TENANT_ALL = "*"

_current_city: ContextVar[Optional[str]] = ContextVar(
    "cityvision_tenant_city", default=None
)


def get_tenant_city() -> Optional[str]:
    return _current_city.get()


def set_tenant_city(city_id: Optional[str]) -> Token:
    return _current_city.set(city_id)


def reset_tenant_city(token: Token) -> None:
    _current_city.reset(token)
