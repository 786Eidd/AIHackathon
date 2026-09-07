# scripts/upload_models_to_oss.py

import os
from pathlib import Path

try:
    import oss2
except Exception:
    print("[upload-models] oss2 is not installed. Please run: pip install oss2")
    raise


def get_env(name: str) -> str:
    return os.getenv(name, "").strip()


def find_local_file(name: str) -> Path:
    candidates = [
        Path("/app/storage/models") / name,
        Path("storage/models") / name,
        Path(name),
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return candidates[1]


def make_bucket():
    endpoint = get_env("OSS_ENDPOINT")
    bucket_name = get_env("OSS_BUCKET")
    access_key_id = get_env("OSS_ACCESS_KEY_ID")
    access_key_secret = get_env("OSS_ACCESS_KEY_SECRET")
    security_token = get_env("OSS_SECURITY_TOKEN")

    if not endpoint or not bucket_name:
        raise ValueError("OSS_ENDPOINT and OSS_BUCKET must be set.")

    if not access_key_id or not access_key_secret:
        raise ValueError("OSS_ACCESS_KEY_ID and OSS_ACCESS_KEY_SECRET must be set.")

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


def upload_file(bucket, local_path: Path, oss_key: str) -> None:
    if not local_path.exists():
        print(f"[upload-models] Local file not found: {local_path}")
        return

    print(f"[upload-models] Uploading {local_path} to oss://{bucket.bucket_name}/{oss_key}")
    bucket.put_object_from_file(oss_key, str(local_path))
    print("[upload-models] Upload complete.")


def main():
    bucket = make_bucket()

    local_identity = find_local_file("identity_store.pkl")
    local_weapon = find_local_file("weapon_detector.pt")

    identity_oss_key = get_env("FACE_STORE_OSS_KEY") or "models/identity_store.pkl"
    weapon_oss_key = get_env("WEAPON_MODEL_OSS_KEY") or "models/weapon_detector.pt"

    upload_file(bucket, local_identity, identity_oss_key)
    upload_file(bucket, local_weapon, weapon_oss_key)


if __name__ == "__main__":
    main()