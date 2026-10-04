"""Durable local objects mirrored to private Cloud or Supabase object storage."""

from pathlib import Path
import httpx
from ..config import settings


class ObjectStorage:
    def enabled(self):
        return bool(settings.gcs_artifact_bucket or settings.supabase_storage_bucket)

    def gcs_enabled(self):
        return bool(settings.gcs_artifact_bucket)

    def gcs_bucket(self):
        # Application Default Credentials come from the Cloud Run service
        # account; credentials are never packaged into the image.
        from google.cloud import storage

        return storage.Client().bucket(settings.gcs_artifact_bucket)

    def url(self, key):
        return f"{settings.supabase_url}/storage/v1/object/{settings.supabase_storage_bucket}/{key}"

    def headers(self):
        return {
            "Authorization": f"Bearer {settings.supabase_service_role_key}",
            "apikey": settings.supabase_service_role_key,
        }

    def upload(self, key, path: Path, content_type="application/octet-stream"):
        if self.gcs_enabled():
            self.gcs_bucket().blob(key).upload_from_filename(
                path, content_type=content_type
            )
            return
        if not self.enabled():
            return
        if not settings.supabase_url or not settings.supabase_service_role_key:
            raise ValueError(
                "Supabase Storage requires server-side URL and service-role key"
            )
        response = httpx.post(
            self.url(key),
            headers={
                **self.headers(),
                "Content-Type": content_type,
                "x-upsert": "true",
            },
            content=path.read_bytes(),
            timeout=60,
        )
        response.raise_for_status()

    def restore(self, key, path: Path):
        if self.gcs_enabled():
            blob = self.gcs_bucket().blob(key)
            if not blob.exists():
                return False
            path.parent.mkdir(parents=True, exist_ok=True)
            temp = path.with_suffix(".download")
            blob.download_to_filename(temp)
            temp.replace(path)
            return True
        if not self.enabled():
            return False
        response = httpx.get(self.url(key), headers=self.headers(), timeout=60)
        if response.status_code == 404:
            return False
        response.raise_for_status()
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(".download")
        temp.write_bytes(response.content)
        temp.replace(path)
        return True


storage = ObjectStorage()
