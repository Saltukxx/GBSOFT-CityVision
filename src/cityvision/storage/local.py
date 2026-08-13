from __future__ import annotations

import shutil
from pathlib import Path
from typing import BinaryIO


class LocalObjectStore:
    """Filesystem-backed object storage."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def put_file(self, key: str, src: Path) -> str:
        dest = self._path(key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        return key

    def put_bytes(self, key: str, data: bytes, *, content_type: str | None = None) -> str:
        dest = self._path(key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return key

    def download_to(self, key: str, dest: Path) -> Path:
        src = self.resolve(key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        return dest

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def open_read(self, key: str) -> BinaryIO:
        path = self.resolve(key)
        return path.open("rb")

    def resolve(self, key: str) -> Path:
        path = self._path(key)
        if not path.is_file():
            raise FileNotFoundError(key)
        path.resolve().relative_to(self.root.resolve())
        return path

    def url_path(self, key: str) -> str:
        return f"/api/storage/{key}"

    def _path(self, key: str) -> Path:
        clean = key.lstrip("/").replace("..", "")
        return self.root / clean
