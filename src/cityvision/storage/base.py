from __future__ import annotations

from typing import BinaryIO, Protocol, runtime_checkable


@runtime_checkable
class ObjectStore(Protocol):
    def put_file(self, key: str, src) -> str: ...

    def exists(self, key: str) -> bool: ...

    def open_read(self, key: str) -> BinaryIO: ...

    def url_path(self, key: str) -> str: ...
