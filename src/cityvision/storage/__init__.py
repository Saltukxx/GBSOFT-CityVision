from __future__ import annotations

from functools import lru_cache
from typing import Union

from cityvision.settings import get_settings
from cityvision.storage.local import LocalObjectStore
from cityvision.storage.s3 import S3ObjectStore

ObjectStoreImpl = Union[LocalObjectStore, S3ObjectStore]


@lru_cache(maxsize=1)
def get_object_store() -> ObjectStoreImpl:
    settings = get_settings()
    if settings.s3_endpoint:
        return S3ObjectStore(
            endpoint_url=settings.s3_endpoint,
            access_key=settings.s3_access_key,
            secret_key=settings.s3_secret_key,
            bucket=settings.s3_bucket,
            region=settings.s3_region,
        )
    return LocalObjectStore(settings.object_store_dir)
