from __future__ import annotations

from pathlib import Path
from typing import BinaryIO, Optional


class S3ObjectStore:
    """S3 / MinIO object storage via boto3."""

    def __init__(
        self,
        *,
        endpoint_url: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        region: str = "us-east-1",
    ):
        import boto3
        from botocore.client import Config

        self.bucket = bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
            config=Config(signature_version="s3v4"),
        )
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        try:
            self._client.head_bucket(Bucket=self.bucket)
        except Exception:
            try:
                self._client.create_bucket(Bucket=self.bucket)
            except Exception:
                pass

    def put_file(self, key: str, src: Path) -> str:
        key = key.lstrip("/")
        extra: dict = {}
        suffix = Path(src).suffix.lower()
        if suffix in {".jpg", ".jpeg"}:
            extra["ContentType"] = "image/jpeg"
        elif suffix == ".png":
            extra["ContentType"] = "image/png"
        elif suffix == ".mp4":
            extra["ContentType"] = "video/mp4"
        elif suffix == ".json":
            extra["ContentType"] = "application/json"
        elif suffix == ".jsonl":
            extra["ContentType"] = "application/x-ndjson"
        if extra:
            self._client.upload_file(str(src), self.bucket, key, ExtraArgs=extra)
        else:
            self._client.upload_file(str(src), self.bucket, key)
        return key

    def put_bytes(self, key: str, data: bytes, *, content_type: Optional[str] = None) -> str:
        key = key.lstrip("/")
        extra: dict = {}
        if content_type:
            extra["ContentType"] = content_type
        self._client.put_object(Bucket=self.bucket, Key=key, Body=data, **extra)
        return key

    def download_to(self, key: str, dest: Path) -> Path:
        key = key.lstrip("/")
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        self._client.download_file(self.bucket, key, str(dest))
        return dest

    def exists(self, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self.bucket, Key=key.lstrip("/"))
            return True
        except Exception:
            return False

    def open_read(self, key: str) -> BinaryIO:
        key = key.lstrip("/")
        try:
            obj = self._client.get_object(Bucket=self.bucket, Key=key)
        except Exception as exc:
            raise FileNotFoundError(key) from exc
        return obj["Body"]

    def url_path(self, key: str) -> str:
        return f"/api/storage/{key.lstrip('/')}"

    def content_type(self, key: str) -> Optional[str]:
        try:
            meta = self._client.head_object(Bucket=self.bucket, Key=key.lstrip("/"))
            return meta.get("ContentType")
        except Exception:
            return None
