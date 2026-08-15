"""Short-lived signed URLs for evidence media.

Browsers load evidence stills and clips through plain ``<img>`` / ``<video>``
tags, which cannot carry an Authorization header. So the listing endpoints —
which *are* authenticated — hand out a URL carrying an expiry and an HMAC over
the resource identity. The media route accepts that signature as an
alternative to a bearer token or API key.
"""

from __future__ import annotations

import hmac
import time
from hashlib import sha256
from typing import Optional
from urllib.parse import quote

from cityvision.settings import get_settings


def _sign(resource: str, expires_at: int, secret: str) -> str:
    msg = f"{resource}\n{expires_at}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), msg, sha256).hexdigest()[:32]


def sign_media_params(resource: str, ttl_sec: Optional[int] = None) -> str:
    """Query string (``exp=…&sig=…``) granting access to ``resource``.

    Empty when no signing secret is configured — in that deployment the media
    routes are open anyway, so an unsigned URL is the correct output.
    """
    settings = get_settings()
    secret = settings.media_url_secret
    if not secret:
        return ""
    expires_at = int(time.time()) + int(ttl_sec or settings.media_url_ttl_sec)
    return f"exp={expires_at}&sig={_sign(resource, expires_at, secret)}"


def signed_media_url(path: str, resource: str, ttl_sec: Optional[int] = None) -> str:
    params = sign_media_params(resource, ttl_sec)
    if not params:
        return path
    joiner = "&" if "?" in path else "?"
    return f"{path}{joiner}{params}"


def verify_media_token(resource: str, exp: Optional[str], sig: Optional[str]) -> bool:
    """True when ``sig`` is a live signature over ``resource``."""
    settings = get_settings()
    secret = settings.media_url_secret
    if not secret or not exp or not sig:
        return False
    try:
        expires_at = int(exp)
    except (TypeError, ValueError):
        return False
    if expires_at < int(time.time()):
        return False
    return hmac.compare_digest(_sign(resource, expires_at, secret), sig)


def storage_resource(key: str) -> str:
    return f"storage:{key}"


def media_resource(media_id: int) -> str:
    return f"media:{media_id}"


def run_video_resource(run_id: int) -> str:
    return f"run-video:{run_id}"


def storage_url(key: str, ttl_sec: Optional[int] = None) -> str:
    return signed_media_url(
        f"/api/storage/{quote(key)}", storage_resource(key), ttl_sec
    )


def media_url(media_id: int, ttl_sec: Optional[int] = None) -> str:
    return signed_media_url(
        f"/api/media/{media_id}", media_resource(int(media_id)), ttl_sec
    )


def run_video_url(run_id: int, ttl_sec: Optional[int] = None) -> str:
    return signed_media_url(
        f"/api/runs/{run_id}/annotated", run_video_resource(int(run_id)), ttl_sec
    )
