from __future__ import annotations

from typing import Callable, Iterable, Optional

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from cityvision.settings import get_settings
from cityvision.tenant import reset_tenant_city, set_tenant_city

# Read-only endpoints the operator dashboard polls without a credential.
# Evidence media (/api/storage, /api/media) is deliberately *not* here — it is
# personal data and is gated in the media routes themselves.
OPEN_READ_PREFIXES: tuple[str, ...] = (
    "/api/events",
    "/api/zones",
    "/api/vehicles",
    "/api/cameras",
    "/api/routes",
    "/api/assets",
    "/api/runs",
    "/api/reviews",
    "/api/work-orders",
    "/api/jobs",
    "/api/users",
)

ALWAYS_OPEN_PATHS: frozenset[str] = frozenset({"/api/kpis", "/health"})

# Evidence media. The middleware cannot evaluate these: browsers fetch them
# from <img>/<video> tags that carry no Authorization header, so access is
# granted by a signed URL query string instead. check_media_access() in the
# route does the real enforcement — passing through here is not "open".
MEDIA_PREFIXES: tuple[str, ...] = ("/api/storage", "/api/media")

# Device-facing edge routes. /api/edge/devices is the human admin registry
# and must go through normal JWT/API-key tenancy — not this bypass.
_EDGE_DEVICE_PREFIXES: tuple[str, ...] = (
    "/api/edge/upload",
    "/api/edge/uploads",
    "/api/edge/heartbeat",
    "/api/edge/video",
)


def _matches(path: str, prefixes: Iterable[str]) -> bool:
    """Exact match, or a path segment prefix. "/" only ever matches itself."""
    for p in prefixes:
        if p == "/":
            if path == "/":
                return True
            continue
        if path == p or path.startswith(p.rstrip("/") + "/"):
            return True
    return False


class ApiKeyMiddleware(BaseHTTPMiddleware):
    """Optional API key gate. Disabled when CITYVISION_API_KEY is empty."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        settings = get_settings()
        if not settings.api_key:
            return await call_next(request)

        path = request.url.path

        # Dashboard shell, docs, static assets and the login endpoint itself
        # are open — login must be reachable to obtain a JWT at all.
        if _matches(path, settings.auth_exempt_prefixes):
            return await call_next(request)

        if not path.startswith("/api/"):
            return await call_next(request)

        if path in ALWAYS_OPEN_PATHS:
            return await call_next(request)

        # Edge device tokens are verified by the edge router's dependency.
        if _is_edge_device_request(request):
            return await call_next(request)

        # Strict tenancy closes anonymous dashboard reads; TenantMiddleware
        # then requires a principal so city scope can be derived from it.
        if (
            not settings.strict_tenancy
            and request.method == "GET"
            and _matches(path, OPEN_READ_PREFIXES)
        ):
            return await call_next(request)

        if request.method == "GET" and _matches(path, MEDIA_PREFIXES):
            return await call_next(request)

        provided = request.headers.get("x-api-key") or _bearer(request.headers.get("authorization"))
        if provided == settings.api_key:
            return await call_next(request)
        # Also accept valid JWT when configured
        if settings.jwt_secret and request.headers.get("authorization"):
            from cityvision.api.security import decode_access_token

            token = _bearer(request.headers.get("authorization"))
            if token and decode_access_token(token):
                return await call_next(request)
        return JSONResponse({"detail": "unauthorized"}, status_code=401)


class TenantMiddleware(BaseHTTPMiddleware):
    """When strict tenancy is on, require a principal on /api/* and SET the city GUC.

    Signed media URLs and edge-device tokens stay reachable without a JWT —
    those routes enforce their own credentials.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        settings = get_settings()
        if not settings.strict_tenancy:
            return await call_next(request)

        path = request.url.path
        if _matches(path, settings.auth_exempt_prefixes):
            return await call_next(request)
        if path == "/health":
            return await call_next(request)
        if not path.startswith("/api/"):
            return await call_next(request)
        if request.method == "GET" and _matches(path, MEDIA_PREFIXES):
            return await call_next(request)
        if (
            request.method == "GET"
            and path.startswith("/api/runs/")
            and path.endswith("/annotated")
        ):
            return await call_next(request)
        if _is_edge_device_request(request):
            return await call_next(request)

        from fastapi import HTTPException as FastAPIHTTPException

        from cityvision.api.deps import resolve_principal, tenant_guc_value

        principal = resolve_principal(
            request.headers.get("authorization"),
            request.headers.get("x-api-key"),
        )
        if principal.role == "anonymous":
            return JSONResponse({"detail": "authentication required"}, status_code=401)
        try:
            guc = tenant_guc_value(principal, request.query_params.get("city_id"))
        except FastAPIHTTPException as exc:
            return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
        token = set_tenant_city(guc)
        try:
            return await call_next(request)
        finally:
            reset_tenant_city(token)


def _is_edge_device_request(request: Request) -> bool:
    """True when this looks like field hardware presenting an edge token.

    A valid human JWT on these paths is *not* treated as a device credential —
    those callers go through normal tenancy. Garbage Bearer values still reach
    ``require_edge_device``, which 401s them.
    """
    path = request.url.path
    if not _matches(path, _EDGE_DEVICE_PREFIXES):
        return False
    if request.headers.get("x-edge-token"):
        return True
    token = _bearer(request.headers.get("authorization"))
    if not token:
        return False
    if get_settings().jwt_secret:
        from cityvision.api.security import decode_access_token

        if decode_access_token(token):
            return False
    return True


def _bearer(header: Optional[str]) -> Optional[str]:
    if not header:
        return None
    parts = header.split(" ", 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    return None
