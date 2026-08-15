from __future__ import annotations

from typing import Callable, Iterable, Optional

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from cityvision.settings import get_settings

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
        if path.startswith("/api/edge/") and (
            request.headers.get("x-edge-token")
            or (request.headers.get("authorization") or "").lower().startswith("bearer ")
        ):
            return await call_next(request)

        if request.method == "GET" and _matches(path, OPEN_READ_PREFIXES):
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


def _bearer(header: Optional[str]) -> Optional[str]:
    if not header:
        return None
    parts = header.split(" ", 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    return None
