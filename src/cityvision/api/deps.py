from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Optional

from fastapi import Depends, Header, HTTPException, Request

from cityvision.api.security import decode_access_token
from cityvision.db.store import Store
from cityvision.domain.statuses import ADMIN_ROLES, OPERATOR_ROLES, VIEWER_ROLES
from cityvision.settings import Settings, get_settings
from cityvision.tenant import TENANT_ALL, reset_tenant_city, set_tenant_city


@dataclass(frozen=True)
class Principal:
    username: str
    role: str  # viewer | operator | admin | superadmin | anonymous
    city_id: Optional[str] = None
    via: str = "jwt"  # jwt | api_key | anonymous

    @property
    def is_authenticated(self) -> bool:
        return self.role != "anonymous"

    @property
    def is_cross_city(self) -> bool:
        """Staff who may query any city: superadmin, or the shared API key.

        The global CITYVISION_API_KEY is a break-glass cross-city credential.
        Prefer per-city JWTs; do not hand the shared key to a municipality.
        Identity is ``via``, not username — a municipal user named ``api_key``
        must not inherit this bypass.
        """
        return self.role == "superadmin" or self.via == "api_key"


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
                return _principal_from_token(payload)
    if cfg.api_key and x_api_key and x_api_key == cfg.api_key:
        return Principal(username="api_key", role="admin", city_id=None, via="api_key")
    return Principal(username="anonymous", role="anonymous", city_id=None, via="anonymous")


def _principal_from_token(payload: dict[str, Any]) -> Principal:
    """JWT proves identity (sub). City, role, and active come from the users row.

    Falls back to token claims only when the users table is unreachable (tests
    without PostGIS, or a transient outage with strict tenancy off).
    """
    cfg = get_settings()
    username = str(payload["sub"])
    token_role = str(payload.get("role") or "operator")
    token_city = payload.get("city_id")
    token_city_s = str(token_city) if token_city else None
    if token_city_s is None and token_role != "superadmin":
        token_city_s = cfg.default_city or None

    try:
        user = get_store().get_user(username)
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception:
        if cfg.strict_tenancy:
            return Principal(
                username="anonymous", role="anonymous", city_id=None, via="anonymous"
            )
        return Principal(username=username, role=token_role, city_id=token_city_s, via="jwt")

    if not user or not user.get("active", True):
        return Principal(username="anonymous", role="anonymous", city_id=None, via="anonymous")

    role = str(user.get("role") or token_role)
    city_id = user.get("city_id")
    city_s = str(city_id) if city_id else None
    if role == "superadmin":
        city_s = None
    elif city_s is None:
        city_s = cfg.default_city or None
    return Principal(username=str(user["username"]), role=role, city_id=city_s, via="jwt")


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
        if principal.via == "api_key" or principal.role in allowed_set:
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
    city_id: Optional[str] = None,
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
    if verify_media_token(resource, exp, sig, city_id=city_id):
        return
    raise HTTPException(status_code=401, detail="authentication required for media")


def resolve_city_id(
    principal: Optional[Principal] = None,
    requested_city_id: Optional[str] = None,
) -> Optional[str]:
    """Derive the effective city scope from who's asking, not what they asked for.

    When ``CITYVISION_STRICT_TENANCY`` is off, keeps the historical behaviour:
    an explicit query param wins, otherwise ``settings.default_city``.
    """
    cfg = get_settings()
    if not cfg.strict_tenancy:
        if requested_city_id:
            return requested_city_id
        return cfg.default_city or None

    if principal is None or principal.role == "anonymous":
        raise HTTPException(status_code=401, detail="authentication required")
    if principal.is_cross_city:
        return requested_city_id
    if principal.city_id is None:
        raise HTTPException(status_code=403, detail="user has no assigned city")
    if requested_city_id and requested_city_id != principal.city_id:
        raise HTTPException(status_code=403, detail="cannot access another city's data")
    return principal.city_id


def require_city_row(
    row: Optional[dict[str, Any]],
    principal: Principal,
    *,
    detail: str = "not found",
    signed_city_id: Optional[str] = None,
) -> dict[str, Any]:
    """404 if missing or (when strict) owned by another city. Avoids existence leaks."""
    if not row:
        raise HTTPException(status_code=404, detail=detail)
    if not get_settings().strict_tenancy:
        return row
    if principal.is_cross_city:
        return row
    if principal.role == "anonymous":
        # Signed-URL media: the HMAC already names this resource. When the
        # listing also bound a city, reject a token that does not match the row.
        if signed_city_id and row.get("city_id") and row.get("city_id") != signed_city_id:
            raise HTTPException(status_code=404, detail=detail)
        return row
    if row.get("city_id") != principal.city_id:
        raise HTTPException(status_code=404, detail=detail)
    return row


def optional_city_id(
    principal: Optional[Principal] = None,
    requested_city_id: Optional[str] = None,
) -> Optional[str]:
    """City filter for endpoints that historically listed everything.

    When strict tenancy is off, only an explicit query param filters; ``None``
    means no SQL city clause. When strict is on, same rules as resolve_city_id.
    """
    if not get_settings().strict_tenancy:
        return requested_city_id
    return resolve_city_id(principal, requested_city_id)


def tenant_guc_value(principal: Principal, requested_city_id: Optional[str] = None) -> str:
    """Value for ``SET LOCAL app.current_city_id`` for this request."""
    city = resolve_city_id(principal, requested_city_id)
    if city:
        return city
    if principal.is_cross_city:
        return TENANT_ALL
    return principal.city_id or TENANT_ALL


async def bind_tenant(
    request: Request,
    principal: Principal = Depends(get_principal),
):
    """SET the tenant ContextVar in the same context as the route (RLS).

    BaseHTTPMiddleware can lose ContextVars across call_next; this dependency
    is what actually scopes Store.connect() for an authenticated request.

    It must be *async*: FastAPI runs a sync generator dependency's setup and
    teardown in separate worker threads, each with a copied context, so the
    value never reached the route and the reset raised "created in a different
    Context". An async generator runs in the request task's own context, which
    sync routes then inherit when they are sent to the threadpool.
    """
    if not get_settings().strict_tenancy:
        yield
        return
    if principal.role == "anonymous":
        yield
        return
    requested = request.query_params.get("city_id")
    guc = tenant_guc_value(principal, requested)
    token = set_tenant_city(guc)
    try:
        yield
    finally:
        reset_tenant_city(token)
