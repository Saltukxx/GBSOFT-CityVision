from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

from fastapi import Depends, Header, HTTPException

from cityvision.api.security import decode_access_token
from cityvision.db.store import Store
from cityvision.domain.statuses import ADMIN_ROLES, OPERATOR_ROLES, VIEWER_ROLES
from cityvision.settings import Settings, get_settings


@dataclass(frozen=True)
class Principal:
    username: str
    role: str  # viewer | operator | admin | api_key | anonymous

    @property
    def is_authenticated(self) -> bool:
        return self.role != "anonymous"


@lru_cache(maxsize=1)
def get_store() -> Store:
    return Store()


def settings() -> Settings:
    return get_settings()


def resolve_principal(
    authorization: Optional[str] = None,
    x_api_key: Optional[str] = None,
) -> Principal:
    cfg = get_settings()
    if authorization:
        parts = authorization.split(" ", 1)
        if len(parts) == 2 and parts[0].lower() == "bearer":
            payload = decode_access_token(parts[1].strip())
            if payload and payload.get("sub"):
                return Principal(
                    username=str(payload["sub"]),
                    role=str(payload.get("role") or "operator"),
                )
    if cfg.api_key and x_api_key and x_api_key == cfg.api_key:
        return Principal(username="api_key", role="admin")
    return Principal(username="anonymous", role="anonymous")


def get_principal(
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> Principal:
    return resolve_principal(authorization, x_api_key)


def require_roles(*allowed: str):
    """FastAPI dependency factory: require one of the given roles when RBAC is on."""
    allowed_set = set(allowed)

    def _dep(principal: Principal = Depends(get_principal)) -> Principal:
        if not get_settings().rbac_enabled:
            return principal
        if principal.role == "api_key" or principal.role in allowed_set:
            return principal
        if principal.role == "anonymous":
            raise HTTPException(status_code=401, detail="authentication required")
        raise HTTPException(status_code=403, detail="insufficient role")

    return _dep


require_viewer = require_roles(*VIEWER_ROLES, "api_key")
require_operator = require_roles(*OPERATOR_ROLES, "api_key")
require_admin = require_roles(*ADMIN_ROLES, "api_key")


def check_media_access(
    resource: str,
    *,
    principal: Principal,
    exp: Optional[str] = None,
    sig: Optional[str] = None,
) -> None:
    """Authorize an evidence media read, or raise 401.

    Accepts a normal credential (JWT / API key) or a signed URL handed out by
    an authenticated listing endpoint, since ``<img>``/``<video>`` tags cannot
    send headers. A deployment with no credential configured at all stays open,
    matching the rest of the optional-auth design.
    """
    from cityvision.api.media_tokens import verify_media_token

    if not get_settings().auth_configured:
        return
    if principal.is_authenticated:
        return
    if verify_media_token(resource, exp, sig):
        return
    raise HTTPException(status_code=401, detail="authentication required for media")


def resolve_city_id(city_id: Optional[str] = None) -> Optional[str]:
    """Explicit city query wins; otherwise settings.default_city."""
    if city_id:
        return city_id
    return get_settings().default_city or None
