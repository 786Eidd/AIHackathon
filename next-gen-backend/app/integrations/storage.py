# app/integrations/storage.py

import shutil
from pathlib import Path
from typing import Optional

import oss2

from app.core.config import settings


class StorageClient:
    def __init__(self):
        self.settings = settings
        self.bucket = None

        if (
            settings.storage_backend == "oss"
            and settings.oss_endpoint
            and settings.oss_bucket
            and settings.oss_access_key_id
            and settings.oss_access_key_secret
        ):
            auth = oss2.Auth(
                settings.oss_access_key_id,
                settings.oss_access_key_secret,
            )
            self.bucket = oss2.Bucket(
                auth,
                settings.oss_endpoint,
                settings.oss_bucket,
            )

        Path(settings.local_storage_dir).mkdir(parents=True, exist_ok=True)

    def _local_path(self, key: str) -> Path:
        return Path(self.settings.local_storage_dir) / key

    def _cache_path(self, key: str) -> Path:
        return Path(self.settings.local_storage_dir) / "cache" / key

    def save_bytes(self, key: str, data: bytes) -> None:
        if self.bucket:
            self.bucket.put_object(key, data)
            return

        path = self._local_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def save_fileobj(self, key: str, fileobj) -> None:
        if self.bucket:
            self.bucket.put_object(key, fileobj)
            return

        path = self._local_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "wb") as f:
            shutil.copyfileobj(fileobj, f)

    def save_file(self, key: str, local_path: str | Path) -> None:
        local_path = Path(local_path)

        if self.bucket:
            self.bucket.put_object_from_file(key, str(local_path))
            return

        path = self._local_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)

        if local_path.resolve() != path.resolve():
            shutil.copyfile(local_path, path)

    def download_to_cache(self, key: str) -> Path:
        if not self.bucket:
            return self._local_path(key)

        cache_path = self._cache_path(key)
        cache_path.parent.mkdir(parents=True, exist_ok=True)

        if not cache_path.exists():
            self.bucket.get_object_to_file(key, str(cache_path))

        return cache_path

    def get_local_path(self, key: str) -> Path:
        return self.download_to_cache(key)

    def exists(self, key: str) -> bool:
        if self.bucket:
            return bool(self.bucket.object_exists(key))

        return self._local_path(key).exists()

    def access_reference(self, key: str) -> Optional[str]:
        """
        Returns a reference usable by Qwen-VL.

        For OSS:
            returns signed HTTP URL

        For local:
            returns file:// URI
        """
        if self.bucket:
            if not self.bucket.object_exists(key):
                return None

            return self.bucket.sign_url(
                "GET",
                key,
                self.settings.artifact_url_expires,
            )

        path = self._local_path(key)
        if path.exists():
            return f"file://{path.resolve()}"

        return None