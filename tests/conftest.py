"""Pytest defaults: disable RBAC so existing API smokes stay open locally."""

from __future__ import annotations

import os

import pytest

# Apply before Settings are constructed in tests
os.environ.setdefault("CITYVISION_RBAC", "0")
os.environ.setdefault("CITYVISION_JOB_INLINE", "1")


@pytest.fixture(autouse=True)
def _isolate_dotenv(monkeypatch):
    """Never read the developer's .env during tests.

    Settings fall back to .env whenever an env var is unset *or empty*, so
    without this a local .env silently decides whether auth is configured.
    """
    import cityvision.settings as settings_mod

    monkeypatch.setattr(settings_mod, "_read_env_file_value", lambda key: None)
    yield


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    from cityvision.settings import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
