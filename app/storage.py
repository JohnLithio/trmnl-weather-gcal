"""Token storage with Google Secret Manager for persistence in Cloud Run."""

import json
import os
from datetime import datetime, timezone

from app.config import DATA_DIR, TOKEN_FILE

# Secret Manager configuration
GCP_PROJECT = os.getenv("GCP_PROJECT", "")
SECRET_NAME = "trmnl-google-token"


def _use_secret_manager() -> bool:
    """Check if we should use Secret Manager (when running in GCP)."""
    return bool(GCP_PROJECT)


def _get_secret_client():
    """Get Secret Manager client (lazy import to avoid issues in local dev)."""
    from google.cloud import secretmanager

    return secretmanager.SecretManagerServiceClient()


def ensure_data_dir() -> None:
    """Ensure the data directory exists (for local file storage)."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def save_token(refresh_token: str) -> None:
    """Save the Google refresh token."""
    data = {
        "refresh_token": refresh_token,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    if _use_secret_manager():
        _save_to_secret_manager(json.dumps(data))
    else:
        # Local file storage
        ensure_data_dir()
        TOKEN_FILE.write_text(json.dumps(data, indent=2))


def load_token() -> str | None:
    """Load the Google refresh token. Returns None if not found."""
    if _use_secret_manager():
        data_str = _load_from_secret_manager()
        if not data_str:
            return None
        try:
            data = json.loads(data_str)
            return data.get("refresh_token")
        except (json.JSONDecodeError, KeyError):
            return None
    else:
        # Local file storage
        if not TOKEN_FILE.exists():
            return None
        try:
            data = json.loads(TOKEN_FILE.read_text())
            return data.get("refresh_token")
        except (json.JSONDecodeError, KeyError):
            return None


def delete_token() -> None:
    """Delete the stored token."""
    if _use_secret_manager():
        # For Secret Manager, we save a placeholder (empty payloads not allowed)
        _save_to_secret_manager('{"deleted": true}')
    else:
        if TOKEN_FILE.exists():
            TOKEN_FILE.unlink()


def is_authenticated() -> bool:
    """Check if we have a stored refresh token."""
    return load_token() is not None


# Secret Manager helpers


def _save_to_secret_manager(data: str) -> None:
    """Save data to Secret Manager by adding a new version."""
    client = _get_secret_client()
    parent = f"projects/{GCP_PROJECT}/secrets/{SECRET_NAME}"

    # Add new secret version
    client.add_secret_version(
        request={
            "parent": parent,
            "payload": {"data": data.encode("utf-8")},
        }
    )
    print(f"Saved token to Secret Manager: {SECRET_NAME}")


def _load_from_secret_manager() -> str | None:
    """Load the latest secret version from Secret Manager."""
    try:
        client = _get_secret_client()
        name = f"projects/{GCP_PROJECT}/secrets/{SECRET_NAME}/versions/latest"

        response = client.access_secret_version(request={"name": name})
        return response.payload.data.decode("utf-8")
    except Exception as e:
        print(f"Failed to load from Secret Manager: {e}")
        return None
