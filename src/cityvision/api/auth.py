from __future__ import annotations

from typing import Callable, Optional

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from cityvision.settings import get_settings


class ApiKeyMiddleware(BaseHTTPMiddleware):
    """Optional API key gate. Disabled when CITYVISION_API_KEY is empty."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        settings = get_settings()
        if not settings.api_key:
            return await call_next(request)

        path = request.url.path
        if path == "/" or any(
            path == p or path.startswith(p.rstrip("/") + "/")
            for p in settings.auth_exempt_prefixes
            if p != "/"
        ):
            # dashboard + docs remain open; mutating API needs key
            if path.startswith("/api/"):
                pass
            else:
                return await call_next(request)

        if not path.startswith("/api/"):
            return await call_next(request)

        # GET health/kpis stay open for operator dashboard JS
        if request.method == "GET" and path in {"/api/kpis", "/health"}:
            return await call_next(request)
        # Edge device token auth is enforced in the edge router itself
        if path.startswith("/api/edge/") and (
            request.headers.get("x-edge-token")
            or (request.headers.get("authorization") or "").lower().startswith("bearer ")
        ):
            return await call_next(request)
        if request.method == "GET" and (
            path.startswith("/api/events")
            or path.startswith("/api/zones")
            or path.startswith("/api/storage")
            or path.startswith("/api/vehicles")
            or path.startswith("/api/cameras")
            or path.startswith("/api/routes")
            or path.startswith("/api/assets")
            or path.startswith("/api/runs")
            or path.startswith("/api/reviews")
            or path.startswith("/api/work-orders")
            or path.startswith("/api/jobs")
            or path.startswith("/api/users")
        ):
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
