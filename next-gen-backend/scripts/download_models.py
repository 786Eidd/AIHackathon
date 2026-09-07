# scripts/download_models.py

import os
from pathlib import Path

try:
    import oss2
except Exception:
    print("[download-models] oss2 is not installed. Skipping OSS download.")
    oss2 = None


def get_env(name: str) -> str:
    return os.getenv(name, "").strip()


def make_bucket():
    if oss2 is None:
        return None

    endpoint = get_env("OSS_ENDPOINT")
    bucket_name = get_env("OSS_BUCKET")
    access_key_id = get_env("OSS_ACCESS_KEY_ID")
    access_key_secret = get_env("OSS_ACCESS_KEY_SECRET")
    security_token = get_env("OSS_SECURITY_TOKEN")

    if not endpoint or not bucket_name:
        print("[download-models] OSS_ENDPOINT or OSS_BUCKET not configured.")
        return None

    if not access_key_id or not access_key_secret:
        print("[download-models] OSS credentials not configured.")
        return None

    if security_token:
        auth = oss2.StsAuth(
            access_key_id,
            access_key_secret,
            security_token,
        )
    else:
        auth = oss2.Auth(
            access_key_id,
            access_key_secret,
        )

    return oss2.Bucket(auth, endpoint, bucket_name)


def download_object(bucket, oss_key: str, local_path: Path) -> None:
    if not oss_key:
        return

    if local_path.exists():
        print(f"[download-models] Already exists: {local_path}")
        return

    try:
        exists = bucket.object_exists(oss_key)
    except Exception as e:
        print(f"[download-models] Failed to check object {oss_key}: {e}")
        return

    if not exists:
        print(f"[download-models] OSS object not found: {oss_key}")
        return

    local_path.parent.mkdir(parents=True, exist_ok=True)

    tmp_path = local_path.with_suffix(local_path.suffix + ".tmp")

    print(f"[download-models] Downloading oss://{bucket.bucket_name}/{oss_key}")
    print(f"[download-models] Destination: {local_path}")

    try:
        bucket.get_object_to_file(oss_key, str(tmp_path))
        os.replace(tmp_path, local_path)
        print(f"[download-models] Download complete: {local_path}")
    except Exception as e:
        print(f"[download-models] Download failed: {e}")


def main():
    bucket = make_bucket()

    if bucket is None:
        print("[download-models] OSS bucket is not available.")
        return

    face_store_oss_key = get_env("FACE_STORE_OSS_KEY")
    face_store_path = get_env("FACE_STORE_PATH") or "/app/storage/models/identity_store.pkl"

    weapon_model_oss_key = get_env("WEAPON_MODEL_OSS_KEY")
    weapon_model_path = get_env("WEAPON_MODEL_PATH") or "/app/storage/models/weapon_detector.pt"

    download_object(
        bucket,
        face_store_oss_key,
        Path(face_store_path),
    )

    download_object(
        bucket,
        weapon_model_oss_key,
        Path(weapon_model_path),
    )


if __name__ == "__main__":
    main()